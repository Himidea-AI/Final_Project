"""S-5 Parent-child chunking — same (source, article) 청크들을 합쳐 parent_text 생성.

전제:
- chunks.json 그대로 유지 (child = 검색 임베딩 단위).
- parent = 같은 (source, article) chunk_id들의 text 합친 것.
- 검색 결과 반환 시 retriever가 chunk_id → parent_text 치환.

출력:
- `data/legal/processed/parent_articles.json` = {chunk_id: parent_text}

DB 변경 없음. 임베딩 재계산 없음.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

CHUNKS_PATH = Path(__file__).parent / "processed" / "chunks.json"
OUT_PATH = Path(__file__).parent / "processed" / "parent_articles.json"


def main() -> None:
    print(f"chunks.json: {CHUNKS_PATH}")
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"총 청크: {len(chunks)}")

    # (source, article) 그룹핑
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in chunks:
        meta = c.get("metadata", {})
        src = meta.get("source") or "?"
        art = meta.get("article") or ""
        # article 비어있으면 chunk_id 자체가 parent — 단독 그룹
        key = (src, art) if art else (src, meta.get("chunk_id", ""))
        groups[key].append(c)

    # parent_text = 그룹 내 text 합치기 (chunk_id 순서 안정)
    parent_map: dict[str, str] = {}
    multi_member = 0
    for key, members in groups.items():
        members_sorted = sorted(members, key=lambda x: x["metadata"].get("chunk_id", ""))
        parent_text = "\n".join(m["text"] for m in members_sorted)
        # 너무 큰 parent는 cap (3K chars — main LLM 토큰 보호)
        if len(parent_text) > 3000:
            parent_text = parent_text[:3000] + "…"
        for m in members_sorted:
            cid = m["metadata"].get("chunk_id")
            if cid:
                parent_map[cid] = parent_text
        if len(members_sorted) > 1:
            multi_member += 1

    print(f"그룹 수: {len(groups)} (다중 멤버: {multi_member})")
    print(f"chunk_id → parent_text 매핑: {len(parent_map)}")

    avg_len = sum(len(v) for v in parent_map.values()) // max(1, len(parent_map))
    print(f"parent_text 평균 길이: {avg_len} chars")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(parent_map, f, ensure_ascii=False)
    print(f"saved → {OUT_PATH}")


if __name__ == "__main__":
    main()
