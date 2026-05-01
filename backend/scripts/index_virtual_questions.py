"""
Virtual Questions 벡터 인덱스 구축 — numpy 파일로 저장

virtual_questions.json → vq_embeddings.npz (벡터 + 매핑)
검색 시: 쿼리 vs vq_embeddings 유사도 → 원본 청크 반환
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VQ_PATH = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "virtual_questions.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "vq_index.npz"


def main():
    from sentence_transformers import SentenceTransformer

    print("[1] 모델 로딩...")
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    with open(VQ_PATH, encoding="utf-8") as f:
        vq_data = json.load(f)

    # 질문 + chunk_idx 매핑
    questions = []
    chunk_indices = []
    sources = []
    articles = []

    for item in vq_data:
        for q in item.get("questions", []):
            questions.append(q)
            chunk_indices.append(item["chunk_idx"])
            sources.append(item["source"])
            articles.append(item["article"])

    print(f"[2] 질문: {len(questions)}개 → 임베딩 생성...")
    t0 = time.perf_counter()
    embeddings = model.encode(questions, batch_size=128, show_progress_bar=True)
    elapsed = time.perf_counter() - t0
    print(f"    완료: {elapsed:.1f}초")

    # npz로 저장
    np.savez_compressed(
        OUTPUT_PATH,
        embeddings=embeddings,
        chunk_indices=np.array(chunk_indices),
    )

    # 매핑 JSON도 저장 (source, article 참조용)
    mapping_path = OUTPUT_PATH.with_suffix(".json")
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(
            [{"q": q, "chunk_idx": ci, "source": s, "article": a}
             for q, ci, s, a in zip(questions, chunk_indices, sources, articles)],
            f, ensure_ascii=False,
        )

    print(f"[3] 저장:")
    print(f"    벡터: {OUTPUT_PATH} ({embeddings.shape})")
    print(f"    매핑: {mapping_path}")


if __name__ == "__main__":
    main()
