---
name: spotter-single-source
description: Enforces single source of truth for SPOTTER constant mappings — Mapo-gu 동 codes, CS business category codes, and similar lookup tables. Use when adding, modifying, or referencing any mapping from Korean neighborhood names to codes, business types to CS codes, or any constant dictionary. Triggers when Claude sees hardcoded strings like "11440660", "CS100006", dict literals with Korean neighborhood names (서교동, 합정동, 망원동), or any new _MAP / _CODE_MAP / _DICT variable being created.
---

# SPOTTER Single Source of Truth

Prevent the class of bug where two mapping dictionaries coexist with different values. This caused 15 of 16 Mapo-gu 동 codes to be silently wrong (서교동 = `"11440600"` vs `"11440660"`), making TCN predictions analyze completely different neighborhoods than the user actually requested. Q1 revenue shifted from ₩17억 to ₩308억 after the fix — showing how different "right" and "wrong" data can be while both looking plausible.

## Canonical Sources — Use These Only

### 동 (행정동) codes
- **Single source**: `backend/app/services/dong_resolver.py`
- **Entry point**: `resolve_dong_code(dong_name: str) -> str`
- **Underlying dict**: `MAPO_DONG_MAP`

**Never** create:
- New `_MAPO_DONG_CODE_MAP` or similar variables elsewhere in the codebase
- Underscore-prefixed local 동 mappings in individual node/service files
- Inline dict literals like `{"서교동": "11440660", "합정동": "11440680", ...}`

### Business category codes (CS / 골목상권)
- **Single source**: `backend/app/constants/business_categories.py`
- All 8+ categories must stay covered: 치킨, 제과점, 중식, 일식, 양식, 패스트푸드, 분식, 카페 (+ any others added later)
- Missing categories cause silent fallback to wrong data — user sees confident results for the wrong business type

**Known historical bugs — do NOT recreate**:
- 치킨 was mapped to `CS100006` (a fast-food code) → caused 골목상권 queries to return fast-food data
- 제과점 was mapped to `CS100011` (a code that does not exist in the source data)
- 중식 / 일식 / 양식 / 패스트푸드 / 분식 were missing entirely → added during the 4/16 audit

## Workflow When You See a Mapping

1. **Search first**: before writing any new dict, run:
   ```bash
   grep -rn "11440" backend/
   grep -rn "CS1000" backend/
   grep -rn "서교동\|합정동\|망원동" backend/
   ```
2. **If a canonical source exists**: add new entries there, never elsewhere. Import and reuse.
3. **If no canonical source exists**: create one in `backend/app/constants/` or `backend/app/services/` and migrate all existing callers in the same PR.

## Red Flags — Stop and Verify

- A second dict with Korean 동 names as keys anywhere outside `dong_resolver.py`
- Code that does `dong_code = "11440" + ...` or hardcodes a specific 동 code
- CS code strings like `"CS100006"` appearing in business-logic files instead of the constants file
- A function that maps `business_type` → code without importing from the canonical source
- Comments like `# TODO: sync with dong_resolver` near a mapping — this is the smell of a duplicate in progress
- Any PR that adds a 동 or CS mapping in more than one file

## Why This Matters

When mappings drift, the system returns confident numbers for the WRONG neighborhood or WRONG business category. Users do not detect silent errors. A single source of truth is the only way to keep TCN predictions pointing at the data the user actually asked about.