"""
MiniLM 법률 도메인 파인튜닝 — Triplet Loss

입력: data/legal/processed/train_triplets.jsonl (1,030개)
출력: models/legal-minilm-finetuned/

sentence-transformers의 TripletLoss로 학습.
학습 후 벤치마크 비교를 위해 원본 모델은 유지.
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

TRIPLETS_PATH = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "train_triplets.jsonl"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "models" / "legal-minilm-finetuned"
BASE_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def main():
    print(f"[1] 모델 로딩: {BASE_MODEL}")
    model = SentenceTransformer(BASE_MODEL)

    # 트리플렛 로드
    print("[2] 학습 데이터 로딩...")
    examples = []
    with open(TRIPLETS_PATH, encoding="utf-8") as f:
        for line in f:
            t = json.loads(line)
            examples.append(InputExample(texts=[t["query"], t["pos"], t["neg"]]))

    print(f"    {len(examples)}개 트리플렛")

    # DataLoader
    train_dataloader = DataLoader(examples, shuffle=True, batch_size=16)
    train_loss = losses.TripletLoss(model=model)

    # 학습
    epochs = 3
    print(f"[3] 파인튜닝 시작 (epochs={epochs}, batch_size=16)")
    t0 = time.perf_counter()

    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=epochs,
        warmup_steps=int(len(train_dataloader) * 0.1),
        show_progress_bar=True,
        output_path=str(OUTPUT_DIR),
    )

    elapsed = time.perf_counter() - t0
    print(f"\n[4] 학습 완료: {elapsed:.0f}초")
    print(f"    저장: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
