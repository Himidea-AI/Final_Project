# Emerging District UX 재설계 — Design Spec

작성일: 2026-05-04
담당: B2 (수지니) — 모델·백엔드·프론트 통합 변경
관련 컴포넌트: `models/emerging_district/*`, `frontend/.../EmergingSignalCard.tsx`

## 배경

`/dashboard/predict?sub=emerging_district` 탭의 "동별 상권 조기감지 신호" 카드가 두 가지 문제를 안고 있다.

1. **사용자 친화도 부족** — `이상도`, `0~1 정규화`, `정상 상권` 등 통계 용어가 그대로 노출되어 자영업자 사용자가 의미를 이해하기 어렵다. 카드 자체가 (동명/신호/점수)만 표시되어 빈 느낌이다.
2. **`consecutive_anomaly_quarters` 메트릭의 의미 불일치** — `models/emerging_district/predict.py`의 `_count_consecutive_anomalies`가 8분기 sliding window의 평균 재구성오차를 카운트해 "분기 수"가 아니라 "윈도우 수"를 셈. 인접 윈도우가 7분기를 공유해 단일 이상 분기가 카운트를 부풀리고, summary 문구 "최근 N분기 연속 이상 감지"와 의미가 어긋난다. 실제 운용에서 "거의 다 0"으로 관측됨.
3. **백엔드가 보내지만 UI가 사용하지 않는 정보** — `models/interface.py:644-682`에서 4-tier fallback (`predict_fallback.py`)이 `tier`, `raw`, `summary`를 함께 송출하는데, 프론트 `EmergingSignal` 타입에 미선언이라 카드에 노출되지 않음. tier별 신뢰도 차이(공식 데이터 vs AI 판정 vs 보조 신호)는 사용자에게 의사결정 단서가 됨.
4. **타입 드리프트** — `SimulationOutput.emerging_signal`은 `EmergingSignal | null` 강타입, `DistrictPredictionResult.emerging_signal`은 `Record<string, unknown> | null` 약타입으로 일관성 결여.

## 목표

- 카드 모든 표기를 사용자 친화 한국어로 정비 (통계 용어 제거).
- `consecutive_anomaly_quarters`를 진짜 분기 단위 메트릭으로 재정의 (per-quarter MSE 기반).
- 백엔드가 이미 송출 중인 `tier`/`raw`/`summary`를 UI에 노출 — 카드의 빈 느낌 해소 + "왜 이 신호?" 근거 제공.
- 타입 드리프트 해결 — `EmergingSignal` 강타입 1곳으로 통일.

비목표:
- autoencoder 가중치 재학습 (수행하지 않음, forward 재실행만).
- `predict_fallback.py`의 4-tier 분류 로직 자체 변경 (summary 문구만 정비).
- `models/interface.py` / `backend/src/main.py` 변경 (dict 통과 그대로).

## 변경 파일 (5개)

| 레이어 | 파일 | 변경 내용 |
|---|---|---|
| 모델 | `models/emerging_district/predict.py` | `_count_consecutive_anomalies` per-quarter 재정의, EmergingResult 무변경 (필드 의미만 수정) |
| 모델 | `models/emerging_district/train.py` | per-quarter MSE 분포의 95th percentile 산출 → `meta["quarter_threshold"]` 저장 |
| 모델 | `models/emerging_district/predict_fallback.py` | 5 tier 모두 summary 한국어 정비 (raw 코드 제거) |
| 타입 | `frontend/src/types/index.ts` | `EmergingSignal`에 `tier`, `raw` 추가 + `DistrictPredictionResult.emerging_signal` 강타입화 |
| UI | `frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx` | 라벨 단어 정비 + tier 배지 + raw evidence chip + summary 한 줄 + 카드 영역 재구성 |

## 백엔드 상세

### `predict.py` — `_count_consecutive_anomalies` per-quarter 재정의

**현행 (line 106-138)**:

```python
for i in range(len(feat_scaled) - window_size, -1, -1):
    seq = feat_scaled[i : i + window_size]
    ...
    err = float(((recon - x_t) ** 2).mean().item())  # 8분기 평균
    if err > threshold:
        count += 1
    else:
        break
```

**변경 후**:

분기별 MSE 산출 — 각 분기 t에 대해 그 분기를 마지막으로 하는 윈도우 `[t-7, ..., t]`를 forward, 결과의 마지막 timestep 위치 (`recon[:, -1, :]`)와 입력의 마지막 timestep (`x_t[:, -1, :]`)의 MSE만 측정. 이 MSE를 `meta["quarter_threshold"]`와 비교해 0/1 anomaly flag 산출. 시퀀스 끝에서부터 거꾸로 연속된 1의 개수가 `consecutive_anomaly_quarters`.

```python
quarter_threshold = meta.get("quarter_threshold", meta["threshold"])  # 호환

for i in range(len(feat_scaled) - window_size, -1, -1):
    seq = feat_scaled[i : i + window_size]
    x_t = torch.from_numpy(seq).unsqueeze(0).to(_dev)
    with torch.no_grad():
        recon = model(x_t)
    last_err = float(((recon[:, -1, :] - x_t[:, -1, :]) ** 2).mean().item())
    if last_err > quarter_threshold:
        count += 1
    else:
        break
```

의미: "윈도우 시퀀스의 마지막 분기가 평소 패턴과 얼마나 다른가" 1분기 단위로 평가. 윈도우 1분기씩 뒤로 미는 점은 동일하나 비교는 **마지막 분기 한 timestep만**이라 분기와 1:1 대응.

이 함수는 `predict()` 본문(line 213)에서 호출되며 `EmergingResult.consecutive_anomaly_quarters` 필드 값으로 그대로 들어간다. 기존 호출자(`models/interface.py:644-682`) 무변경.

### `predict.py` — `_anomaly_score` 무변경

`anomaly_score`는 가장 최근 8분기 윈도우의 평균 재구성오차 / threshold (line 78-81, 200-208). UI에서 0~100으로 정규화 표시. 의미는 그대로 둠 — "최근 8분기 패턴 전체가 평소와 얼마나 다른가" → 사용자에겐 "평소 대비 변화" 단일 점수로 충분.

### `train.py` — `quarter_threshold` 산출

학습 직후 `train_errors` 산출 후(line 144), 동일 train 윈도우들에 대해 forward를 한 번 더 실행해 마지막 timestep MSE 분포를 추출하고 95th percentile을 `quarter_threshold`로 산출.

```python
# train.py line 145 직후 추가
qerrs: list[np.ndarray] = []
with torch.no_grad():
    for i in range(0, len(X_tr_t), 128):
        batch = X_tr_t[i : i + 128]
        recon_b = model(batch)
        qerr = ((recon_b[:, -1, :] - batch[:, -1, :]) ** 2).mean(dim=-1).cpu().numpy()
        qerrs.append(qerr)
quarter_errors = np.concatenate(qerrs)
quarter_threshold = float(np.percentile(quarter_errors, cfg["threshold_percentile"]))

# meta dict에 추가 (line 162 근처)
meta["quarter_threshold"] = quarter_threshold
```

가중치는 `best_state` 그대로 사용 — **재학습 X**. `models/emerging_district/weights/autoencoder_meta.pkl`만 재기록.

### `predict_fallback.py` — 5 tier summary 정비

각 tier별 summary 문자열을 사용자 친화 한국어로 교체. dong_code/industry_code raw 코드는 제거 (UI 카드 헤더에 한국어로 이미 표시됨).

| tier | 변경 전 | 변경 후 |
|---|---|---|
| change_ix (line 252) | `f"{dong_code} {industry_code}: 서울시 공식 stage={cix} → {signal_ko}"` | `f"서울시 상권변화지표 기준 — {signal_ko}"` |
| classifier (line 265-268) | `f"{dong_code} {industry_code}: ML classifier 예측 stage={cls_stage} (신뢰 {prob*100:.0f}%, F1=0.87) → {signal_ko}"` | `f"AI 모델 판정 — {signal_ko} (신뢰도 {prob*100:.0f}%)"` |
| b1_trend (line 282-284) | `f"{dong_code} {industry_code}: B1 신호 — 지하철 {sg:+.1%}, 20-30대 전입 {mr:+.1%} → {signal}"` | `f"지하철 {sg:+.1%} · 20·30대 유입 {mr:+.1%} — {signal_ko} 신호"` |
| slope (line 297-300) | `f"{dong_code} {industry_code}: slope baseline — 매출 slope={ss:+.1f}, 점포 slope={sts:+.1f} → {signal}"` | `f"최근 3분기 매출 {sales_verb} · 점포수 {store_verb} — {signal_ko} 신호"`<br>(slope 부호별 동사: `> 0.5` → "상승", `< -0.5` → "하락", 그 외 → "유지" — 0.5 임계는 frontend chip 부호 임계와 일치) |
| none (line 310) | `f"{dong_code} {industry_code}: 데이터 부재 — normal 가정"` | `"데이터 검증 중 — 안정 상권으로 가정"` |

`signal_ko` 매핑은 신규 모듈 상수로 추가:

```python
_SIGNAL_KO = {"emerging": "신흥 상권", "declining": "쇠퇴 상권", "normal": "안정 상권"}
```

(predict.py에 있는 `_SIGNAL_KO`는 `"normal": "정상"`이므로 본 작업에서 `"안정 상권"`으로 통일.)

`tier`, `raw`, `signal` 필드 자체는 무변경 — 4-tier 분류 로직은 그대로.

## 프론트엔드 상세

### `types/index.ts` — `EmergingSignal` 확장

```typescript
export interface EmergingSignal {
  dong_code: string;
  industry_code: string;
  anomaly_score: number;
  signal: 'emerging' | 'declining' | 'normal';
  consecutive_anomaly_quarters: number;
  summary: string;
  tier: 'change_ix' | 'classifier' | 'b1_trend' | 'slope' | 'none';   // 신규
  raw: Record<string, number | string>;                               // 신규
  is_mock?: boolean;
}
```

`DistrictPredictionResult.emerging_signal`(line 443-465 근방)도 `EmergingSignal | null` 강타입으로 통일. 기존 `as unknown as EmergingSignal` 캐스팅(`PredictEmergingDistrictTab.tsx:54`) 제거 가능.

### `EmergingSignalCard.tsx` — 카드 재구성

**라벨 단어 사전 (코드 내 문자열 일괄 교체):**

| 위치 | 기존 | 변경 |
|---|---|---|
| `SIGNAL_STYLES.normal.label` (line 39) | `"정상 상권"` | `"안정 상권"` |
| KPI 박스 라벨 (line 110) | `"이상도 점수"` | `"평소 대비 변화"` |
| 게이지 라벨 (line 119) | `"이상도 (0~1 정규화)"` | (좌우 라벨로 분리) `"낮음"` / `"평소와 다른 정도"` / `"높음"` |
| 게이지 단위 표시 (line 122) | `signal.anomaly_score.toFixed(2)` | (그대로 유지 — 보조 정보) |

**신규 영역 — 헤더 tier 배지:**

`signal.tier`에 따라 헤더 우측 (현 mock 배지 자리)에 다음 중 하나 렌더:

| tier | 배지 텍스트 | 색 클래스 | 의미 |
|---|---|---|---|
| `change_ix` | `공식 데이터` | `text-success bg-success/10 border-success/20` | 서울시 공식 stage 직접 조회 |
| `classifier` | `AI 판정` | `text-primary bg-primary/10 border-primary/20` | F1=0.87 모델 예측 |
| `b1_trend` | `보조 신호` | `text-warning bg-warning/10 border-warning/20` | 지하철·인구 추세 |
| `slope` | `보조 신호` | `text-warning bg-warning/10 border-warning/20` | 최근 3분기 추세 |
| `none` | `데이터 검증 중` | `text-warning bg-warning/10 border-warning/20` | 데이터 부재 (= is_mock) |

`is_mock` 배지는 별도 렌더하지 않음 — `tier === "none"`이 `is_mock === true`와 1:1 대응이므로 tier 배지로 흡수.

**신규 영역 — summary 한 줄:**

게이지 아래(현 line 133 직후) 추가:

```tsx
<p className="text-xs text-foreground tracking-tight">{signal.summary}</p>
```

**신규 영역 — raw evidence chip (tier별 동적):**

summary 직후 영역. tier별 chip 렌더:

| tier | chip 내용 |
|---|---|
| `change_ix` | **chip 미렌더** — summary "서울시 상권변화지표 기준 — {신호}" 만으로 사용자 친화도 충분, stage 코드(LH/HH/HL/LL) 노출은 통계 용어 회피 원칙에 반함 |
| `classifier` | `신뢰도 {raw.confidence * 100}%` 막대 (작은 progress bar, primary 색) |
| `b1_trend` | 두 칸 chip: `지하철 {raw.subway_growth:+.1%}` · `청년 {raw.migration_2030_rate:+.1%}` |
| `slope` | 부호 chip: `매출 {↑/↓/→}` · `점포수 {↑/↓/→}` — sales_slope/store_slope 부호별, 임계 `abs(slope) < 0.5` 면 `→`(평탄), 양수면 ↑, 음수면 ↓ |
| `none` | 미렌더 |

raw 키 누락 시 해당 chip 미렌더 (옵셔널 체크).

**카드 영역 재구성 (최종):**

```
┌─────────────────────────────────────────┐
│ 합정동                       [공식 데이터] │
├──────────────────┬──────────────────────┤
│  ✨ 신흥 상권      │        77            │
│  상권 신호         │ / 100 평소 대비 변화 │
├──────────────────┴──────────────────────┤
│ 낮음 ─────────●────────────── 높음        │
│ (평소와 다른 정도)                        │
├─────────────────────────────────────────┤
│ 서울시 상권변화지표 기준 — 신흥 상권      │
├─────────────────────────────────────────┤
│ stage LH 단계                             │
└─────────────────────────────────────────┘
```

부모 컨테이너(`PredictEmergingDistrictTab.tsx`)는 무변경 — outer chrome (`bg-card border rounded-3xl`) 그대로.

## 데이터 플로우

```
predict_fallback.predict_emerging_4tier
    summary 정비됨, tier/raw 그대로
        +
autoencoder.predict
    consecutive 의미 재정의됨 (per-quarter)
        ↓
models/interface.py:644 emerging_result dict 조립 (무변경)
    {signal, anomaly_score, consecutive_anomaly_quarters,
     summary, tier, raw, is_mock, dong_code, industry_code}
        ↓
backend/src/main.py 직렬화 (무변경)
        ↓
/predict response (Pydantic dict | None 통과)
        ↓
frontend EmergingSignal 강타입 (tier/raw 추가됨)
        ↓
EmergingSignalCard 재구성된 레이아웃 렌더
```

## 에러 처리 / 호환성

| 상황 | 동작 |
|---|---|
| autoencoder 데이터 부족 (`len(group) < window_size`) | 기존 mock fallback (predict.py:189) 유지 |
| `quarter_threshold` meta 누락 (구버전 학습 가중치) | `meta["threshold"]` fallback — 분기 단위 의미는 약해지지만 동작 보장 |
| `tier === "none"` | summary "데이터 검증 중", raw chip 미렌더, 헤더 배지 "데이터 검증 중" |
| `raw` 키 누락 | chip별 옵셔널 체크, 누락 시 해당 chip 미렌더 |
| 구버전 백엔드 응답 (`tier`/`raw` 필드 없음) | 프론트에서 옵셔널 처리 (`tier ?? "none"`, `raw ?? {}`), 카드 동작 유지 |
| signal === "normal" + consecutive=0 | summary "안정 상권 패턴" 또는 fallback summary 사용, 카드 정상 렌더 |

## 테스트

### 백엔드 — `tests/test_emerging_district.py` (신규)

- per-quarter consecutive 의미 검증
  - 합성 시계열 (16분기 정상 + 마지막 1분기 outlier) → consecutive=1
  - 마지막 2분기 outlier → consecutive=2
  - 모든 분기 정상 → consecutive=0
  - 마지막 1분기 정상, 그 직전 3분기 outlier → consecutive=0 (break 정상 동작)
- `quarter_threshold` meta 누락 시 `threshold` fallback 동작
- `predict_fallback.predict_emerging_4tier` 5 tier summary 한국어 단언 (각 tier 진입 조건 mock 후 summary 부분 문자열 검사)
- tier별 raw 키 단언 (change_ix/classifier/b1_trend/slope)

테스트 패턴은 `tests/test_sensitivity.py` 참고 — `monkeypatch`, `tmp_path`, `caplog` + 합성 데이터 stub. `_lookup_change_ix`/`_classifier_predict`/`_lookup_b1_trend`/`_lookup_slope` 각각 monkeypatch로 None/특정 dict 강제하여 tier 분기 검증.

### 프론트 — `EmergingSignalCard.test.tsx` (신규)

- 5 tier별 헤더 배지 텍스트/클래스 단언
- summary 한 줄 표시 단언
- tier별 raw chip 렌더 단언 (b1_trend → 지하철/청년 chip 2개, slope → 매출/점포수 부호 chip)
- raw 키 누락 시 해당 chip 미렌더 단언
- `signal === null` placeholder 분기 (line 61-71) 무변경 단언
- `is_mock` 배지 별도 미렌더 단언 (tier 배지로 흡수)

테스트 라이브러리: vitest + @testing-library/react. 패턴은 `BulletChart.test.tsx`/`EntrySignalLight.test.tsx` 참고.

### 회귀

기존 테스트 그대로 PASS:
- `pytest tests/test_sensitivity.py` (26개)
- `pytest tests/` 전체

## 마이그레이션

1. 코드 변경 (5개 파일).
2. `python -m models.emerging_district.train` 1회 실행 — 가중치 재학습 X, forward 재실행으로 `quarter_threshold` 산출 후 `autoencoder_meta.pkl` 갱신. 약 1분.
3. uvicorn 재시작 (모듈 전역 `_cache` 비우기).
4. frontend rebuild + 배포.

롤백:
- `autoencoder_meta.pkl`을 git history에서 복원 → 자동으로 `quarter_threshold` 누락 fallback 경로로 동작.
- 코드 revert로 UI 원복.

## 향후 작업 (out of scope)

- `is_mock` 정의 확장 (autoencoder 실패 시도 반영)
- 4-tier 자체 정확도 개선 (change_ix DB 갱신, classifier 재학습)
- 마포 외 동 지원 (현 classifier가 마포 한정)
