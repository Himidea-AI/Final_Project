"""Step 2: Seoul-wide 학습 → Mapo 결측 예측 (Transfer Learning).

비교:
  A. Seoul ExtraTrees (Mapo 제외 학습 → Mapo 예측)
  B. Seoul FT-Transformer (딥러닝)
  C. Seoul TabPFN (Pre-trained transformer)

Baseline: Mapo-only ExtraTrees (MNAR WAPE 13.35%)

목표: "서울 전체 데이터로 학습한 모델이 마포 결측 예측에 더 좋은가?" 확인.
"""

from __future__ import annotations

import os
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import f1_score, r2_score
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")
REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
engine = create_engine(os.environ["POSTGRES_URL"])


def load_data():
    sql = text("""
        SELECT q.quarter, q.dong_code, q.dong_name, q.industry_code, q.industry_name,
               s.monthly_sales,
               q.store_count, q.open_count, q.close_count, q.closure_rate, q.franchise_count
        FROM seoul_district_stores q
        LEFT JOIN seoul_district_sales s USING (quarter, dong_code, industry_code)
    """)
    with engine.connect() as c:
        df = pd.read_sql(sql, c)
    anchor = pd.read_csv(REPO_ROOT / "validation" / "results" / "phase1b_anchor_series.csv").rename(
        columns={"qkey": "quarter", "수치값": "kosis_index"}
    )
    anchor = anchor.groupby("quarter", as_index=False)["kosis_index"].mean()
    df = df.merge(anchor[["quarter", "kosis_index"]], on="quarter", how="left")
    df["kosis_index"] = df["kosis_index"].fillna(df["kosis_index"].mean())
    df["sales_per_store"] = df["monthly_sales"] / df["store_count"].clip(lower=1)
    df["gu_code"] = df["dong_code"].str[:5]
    return df


def build_features(df):
    X = pd.DataFrame(index=df.index)
    X["store_count"] = df["store_count"].fillna(df["store_count"].median())
    X["log_store_count"] = np.log1p(X["store_count"])
    X["kosis_index"] = df["kosis_index"]
    X["log_kosis"] = np.log(df["kosis_index"])
    X["franchise_ratio"] = df["franchise_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["open_ratio"] = df["open_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["closure_rate"] = df["closure_rate"].fillna(0).astype(float)
    X["q_of_year"] = df["quarter"] % 10
    X["year"] = df["quarter"] // 10
    for ind in sorted(df["industry_code"].unique()):
        X[f"ind_{ind}"] = (df["industry_code"] == ind).astype(int)
    for gu in sorted(df["gu_code"].unique()):
        X[f"gu_{gu}"] = (df["gu_code"] == gu).astype(int)
    alive = df[df["monthly_sales"].notna()]
    ds = alive.groupby("dong_code")["store_count"].mean()
    dt = alive.groupby("dong_code")["store_count"].sum()
    X["dong_avg_store"] = df["dong_code"].map(ds).fillna(ds.mean())
    X["dong_total_store"] = df["dong_code"].map(dt).fillna(dt.mean())
    co = df.groupby(["dong_code", "industry_code"])["store_count"].mean()
    X["combo_avg_store"] = df.set_index(["dong_code", "industry_code"]).index.map(co.to_dict())
    X["combo_avg_store"] = X["combo_avg_store"].fillna(co.mean())
    return X


def score_full(actual, pred):
    abs_err = np.abs(actual - pred)
    wape = float(abs_err.sum() / actual.sum() * 100)
    r2 = float(r2_score(actual, pred))
    r = float(pearsonr(actual, pred)[0])
    rmsle = float(np.sqrt(np.mean((np.log1p(actual) - np.log1p(pred)) ** 2)))
    mape = float(np.mean(abs_err / actual) * 100)
    q = np.quantile(actual, [0.25, 0.5, 0.75])

    def tier(v):
        return "L" if v < q[0] else "ML" if v < q[1] else "MH" if v < q[2] else "H"

    a_t = np.array([tier(v) for v in actual])
    p_t = np.array([tier(v) for v in pred])
    f1_tier = float(f1_score(a_t, p_t, average="macro"))
    log_ratio = np.abs(np.log10(pred.clip(min=1e3)) - np.log10(actual.clip(min=1e3)))
    oom_2x = float((log_ratio <= 0.3).mean() * 100)
    return {
        "wape": wape,
        "r2": r2,
        "r": r,
        "rmsle": rmsle,
        "mape": mape,
        "f1_tier": f1_tier,
        "oom_2x": oom_2x,
        "n": int(len(actual)),
    }


# ───────── 모델 A: ExtraTrees ─────────
def train_et(X_tr, y_tr):
    TUNED = dict(
        n_estimators=300,
        max_depth=35,
        min_samples_leaf=1,
        min_samples_split=2,
        max_features=1.0,
        criterion="squared_error",
        bootstrap=False,
        random_state=42,
        n_jobs=-1,
    )
    m = ExtraTreesRegressor(**TUNED)
    m.fit(X_tr, y_tr)
    return m


def predict_et(m, X_te, store_te):
    return np.expm1(m.predict(X_te)) * np.maximum(store_te, 1)


# ───────── 모델 B: FT-Transformer (from scratch) ─────────
class FTTransformer:
    def __init__(self, n_features, d_token=32, n_heads=4, n_layers=3, dropout=0.1):
        import torch
        import torch.nn as nn

        self.torch = torch
        self.nn = nn
        self.n_features = n_features
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        class Model(nn.Module):
            def __init__(self):
                super().__init__()
                # feature tokenizer: 각 피처 → d_token 차원
                self.tokenizer = nn.Parameter(torch.randn(n_features, d_token) * 0.1)
                self.bias = nn.Parameter(torch.zeros(n_features, d_token))
                self.cls_token = nn.Parameter(torch.randn(1, d_token) * 0.1)
                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=d_token,
                    nhead=n_heads,
                    dim_feedforward=d_token * 2,
                    dropout=dropout,
                    batch_first=True,
                    activation="gelu",
                )
                self.encoder = nn.TransformerEncoder(encoder_layer, n_layers)
                self.head = nn.Sequential(nn.LayerNorm(d_token), nn.Linear(d_token, 1))

            def forward(self, x):
                # x: (B, n_features)
                # tokenize: (B, n_features, d_token)
                tokens = x.unsqueeze(-1) * self.tokenizer.unsqueeze(0) + self.bias.unsqueeze(0)
                cls = self.cls_token.expand(x.size(0), -1, -1)
                tokens = torch.cat([cls, tokens], dim=1)
                out = self.encoder(tokens)
                return self.head(out[:, 0]).squeeze(-1)  # CLS token

        self.Model = Model
        self.model = Model().to(self.device)

    def fit(self, X_tr, y_tr, epochs=50, batch_size=2048, lr=1e-3):
        torch = self.torch
        nn = self.nn
        X_tensor = torch.tensor(X_tr.values.astype(np.float32), device=self.device)
        y_tensor = torch.tensor(y_tr.astype(np.float32), device=self.device)
        opt = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-4)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
        n = X_tensor.size(0)
        for ep in range(epochs):
            self.model.train()
            perm = torch.randperm(n, device=self.device)
            total_loss = 0.0
            for i in range(0, n, batch_size):
                idx = perm[i : i + batch_size]
                pred = self.model(X_tensor[idx])
                loss = nn.functional.mse_loss(pred, y_tensor[idx])
                opt.zero_grad()
                loss.backward()
                opt.step()
                total_loss += loss.item() * idx.size(0)
            sched.step()
            if (ep + 1) % 10 == 0:
                print(f"    epoch {ep + 1}/{epochs}  loss={total_loss / n:.4f}", flush=True)

    def predict(self, X_te):
        torch = self.torch
        X_tensor = torch.tensor(X_te.values.astype(np.float32), device=self.device)
        self.model.eval()
        with torch.no_grad():
            return self.model(X_tensor).cpu().numpy()


def predict_ft(model, X_te, store_te):
    log_sps = model.predict(X_te)
    return np.expm1(log_sps) * np.maximum(store_te, 1)


# ───────── 모델 C: TabPFN (subsample ensemble) ─────────
def train_predict_tabpfn(X_tr, y_tr, X_te, store_te, n_samples=1000, n_ensembles=15):
    """TabPFN 2.0.9 CPU 기본 제약: 1000 샘플 이하. subsample ensemble로 확장."""
    try:
        from tabpfn import TabPFNRegressor
    except ImportError:
        print("    tabpfn not installed, skipping")
        return None
    rng = np.random.default_rng(42)
    preds_list = []
    print(f"    subsample {n_samples} × {n_ensembles} ensemble 시작...")
    for i in range(n_ensembles):
        idx = rng.choice(len(X_tr), size=min(n_samples, len(X_tr)), replace=False)
        m = TabPFNRegressor(device="cpu", n_estimators=4, random_state=42 + i)
        m.fit(X_tr.iloc[idx].values.astype(np.float32), y_tr[idx].astype(np.float32))
        preds_list.append(m.predict(X_te.values.astype(np.float32)))
        if (i + 1) % 3 == 0:
            print(f"      {i + 1}/{n_ensembles} 완료", flush=True)
    log_sps = np.mean(preds_list, axis=0)
    return np.expm1(log_sps) * np.maximum(store_te, 1)


# ───────── 메인 ─────────
def main():
    print("=== Step 2: Seoul-wide 학습 → Mapo 결측 예측 ===\n")
    t0 = time.time()
    df = load_data()
    X = build_features(df)
    print(f"[data] total={len(df):,}  alive={df['monthly_sales'].notna().sum():,}")
    print(f"[features] {X.shape[1]}\n")

    alive_mask = df["monthly_sales"].notna()
    mapo_mask = df["gu_code"] == "11440"
    store = df["store_count"].values.astype(float)
    actual = df["monthly_sales"].values
    y_sps = np.log1p(df["sales_per_store"].values)

    # Train: Seoul alive 제외 Mapo
    train_mask = alive_mask & ~mapo_mask
    train_idx = df[train_mask].index.values
    # Validation: Mapo alive 작은 셀 (MNAR-mimic)
    missing_q95 = df.loc[~alive_mask & mapo_mask, "store_count"].quantile(0.95)
    mapo_alive_mask = alive_mask & mapo_mask
    val_mask = mapo_alive_mask & (df["store_count"] <= missing_q95)
    val_idx = df[val_mask].index.values
    # Test: Mapo missing
    test_mask = mapo_mask & ~alive_mask
    test_idx = df[test_mask].index.values

    print("[split]")
    print(f"  Train (Seoul 제외 Mapo): {len(train_idx):,}")
    print(f"  Val (Mapo MNAR-mimic)  : {len(val_idx):,}")
    print(f"  Test (Mapo missing)    : {len(test_idx):,}")
    print()

    results = {}

    # ─── A. Seoul ExtraTrees ───
    print("─── A. Seoul ExtraTrees (Mapo 제외 학습) ───")
    ta = time.time()
    m_a = train_et(X.iloc[train_idx], y_sps[train_idx])
    pred_val = predict_et(m_a, X.iloc[val_idx], store[val_idx])
    m = score_full(actual[val_idx], pred_val)
    print(
        f"  Val (Mapo MNAR): WAPE={m['wape']:.2f}% r={m['r']:.3f} R²={m['r2']:.3f} F1={m['f1_tier']:.3f}  [{time.time() - ta:.0f}s]"
    )
    results["Seoul_ET"] = {"val": m}
    # Test 예측 저장
    pred_test_a = predict_et(m_a, X.iloc[test_idx], store[test_idx])

    # ─── B. Seoul FT-Transformer ───
    print("\n─── B. Seoul FT-Transformer ───")
    tb = time.time()
    ft = FTTransformer(n_features=X.shape[1], d_token=32, n_heads=4, n_layers=3)
    ft.fit(X.iloc[train_idx], y_sps[train_idx], epochs=40, batch_size=2048, lr=1e-3)
    pred_val_b = predict_ft(ft, X.iloc[val_idx], store[val_idx])
    m = score_full(actual[val_idx], pred_val_b)
    print(
        f"  Val (Mapo MNAR): WAPE={m['wape']:.2f}% r={m['r']:.3f} R²={m['r2']:.3f} F1={m['f1_tier']:.3f}  [{time.time() - tb:.0f}s]"
    )
    results["Seoul_FT"] = {"val": m}
    pred_test_b = predict_ft(ft, X.iloc[test_idx], store[test_idx])

    # ─── C. Seoul TabPFN ───
    print("\n─── C. Seoul TabPFN (subsample ensemble) ───")
    tc = time.time()
    pred_val_c = train_predict_tabpfn(X.iloc[train_idx], y_sps[train_idx], X.iloc[val_idx], store[val_idx])
    if pred_val_c is not None:
        m = score_full(actual[val_idx], pred_val_c)
        print(
            f"  Val (Mapo MNAR): WAPE={m['wape']:.2f}% r={m['r']:.3f} R²={m['r2']:.3f} F1={m['f1_tier']:.3f}  [{time.time() - tc:.0f}s]"
        )
        results["Seoul_TabPFN"] = {"val": m}
        pred_test_c = train_predict_tabpfn(X.iloc[train_idx], y_sps[train_idx], X.iloc[test_idx], store[test_idx])
    else:
        pred_test_c = None

    # ─── 요약 ───
    print("\n" + "=" * 60)
    print("=== 최종 비교 (Mapo MNAR-mimic validation) ===")
    print("=" * 60)
    print(f"{'모델':30s} {'WAPE':>8s} {'r':>8s} {'RMSLE':>8s} {'F1':>8s} {'OoM 2x':>8s}")
    baseline = {"wape": 13.35, "r": 0.965, "rmsle": 0.327, "f1_tier": 0.838, "oom_2x": 95.72}
    print(
        f"{'Mapo ExtraTrees (기존)':30s} {baseline['wape']:>8.2f} {baseline['r']:>8.3f} {baseline['rmsle']:>8.3f} {baseline['f1_tier']:>8.3f} {baseline['oom_2x']:>8.2f}"
    )
    for name, res in results.items():
        v = res["val"]
        print(
            f"{name:30s} {v['wape']:>8.2f} {v['r']:>8.3f} {v['rmsle']:>8.3f} {v['f1_tier']:>8.3f} {v['oom_2x']:>8.2f}"
        )
    print()

    best = min([("Mapo_ET_baseline", 13.35)] + [(k, v["val"]["wape"]) for k, v in results.items()], key=lambda x: x[1])
    print(f"🏆 최고: {best[0]}  WAPE {best[1]:.2f}%")

    # 저장
    out_md = REPO_ROOT / "docs" / "sales-imputation" / "step2_transfer_learning.md"
    md = []
    md.append("# Step 2: Seoul-wide Transfer Learning 실험\n")
    md.append("**목적:** 서울 전체 데이터로 학습한 모델이 마포 결측 예측에 유리한가?\n")
    md.append(f"- Train: Seoul alive 제외 Mapo ({len(train_idx):,} cells)")
    md.append(f"- Validate: Mapo MNAR-mimic ({len(val_idx):,} 작은 셀)")
    md.append(f"- Test: Mapo missing ({len(test_idx)} cells)")
    md.append("")
    md.append("## 결과\n")
    md.append("| 모델 | WAPE | Pearson r | RMSLE | F1 4-tier | OoM 2x |")
    md.append("|:-----|----:|--:|--:|--:|--:|")
    md.append("| **Mapo-only ExtraTrees (기존)** | **13.35%** | 0.965 | 0.327 | 0.838 | 95.72% |")
    for name, res in results.items():
        v = res["val"]
        md.append(
            f"| {name} | {v['wape']:.2f}% | {v['r']:.3f} | {v['rmsle']:.3f} | {v['f1_tier']:.3f} | {v['oom_2x']:.2f}% |"
        )
    md.append("")
    md.append(f"**🏆 최고:** `{best[0]}` WAPE {best[1]:.2f}%\n")
    out_md.write_text("\n".join(md), encoding="utf-8")
    print(f"\n[saved] {out_md}")

    print(f"\n총 소요: {time.time() - t0:.0f}s ({(time.time() - t0) / 60:.1f}min)")


if __name__ == "__main__":
    main()
