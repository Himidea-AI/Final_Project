---
name: spotter-schema-sync
description: Enforces SPOTTER frontend-backend schema alignment for the /simulate endpoint. Use when modifying /simulate payloads, SimulationInput/SimulationOutput/SimResult types, frontend/src/types/index.ts, backend Pydantic schemas in backend/app/schemas/, or any code that sends data between the React frontend and FastAPI backend. Triggers when Claude sees field name mismatches like radius_m vs commercial_radius, hardcoded business_type: 'cafe', empty brand_name, or duplicate /analyze + /simulate calls.
---

# SPOTTER Schema Sync

Prevent frontend-backend payload drift. The IM3-144 bug — where 7 fields were silently mismatched between `types/index.ts` and backend Pydantic models — must not recur.

## Core Rules

1. **Single endpoint**: `/simulate` is the only simulation entry point. `/analyze` was deprecated. Never call both from one flow.

2. **Field name alignment** (snake_case on BOTH sides — do not convert to camelCase in frontend state):
   - `commercial_radius` (not `radius_m`)
   - `store_area`
   - `target_price_range`
   - `operating_hours`
   - `business_type` (from UI selection, NEVER hardcoded to `'cafe'`)
   - `brand_name` (from `user.company_name`, NEVER empty string)
   - `dong_code` (resolved via `dong_resolver.py`, never hardcoded inline)

3. **Payload must match 9-field schema exactly**. Check `backend/app/schemas/simulation.py` before modifying `runSimulation()` in frontend.

4. **Response type chain**: `SimulationOutput` (backend) → `SimResult` (frontend state). Both must share identical snake_case keys. The 18-field response populates 14 state fields plus optionals.

## Workflow When Modifying

- **Adding a frontend field?** → Grep `backend/app/schemas/` for the corresponding Pydantic model and add it there first. Then update `types/index.ts`.
- **Renaming a field?** → Search both frontend (`frontend/src/types/`, `frontend/src/api/`) AND backend schemas. Rename together in one commit.
- **Changing types?** → Verify `SimulationOutput` and `SimResult` still match field-by-field. Diff them side-by-side if unsure.

## Red Flags — Stop and Verify

- Any dict literal with `'cafe'`, `''`, or other hardcoded business values in a request payload
- `business_type` or `brand_name` passed as a string constant instead of reading from state/context
- Two different field names for the same concept (e.g., `radius_m` in frontend, `commercial_radius` in backend)
- A request to `/analyze` — this endpoint was removed; use `/simulate`
- A new optional field added to frontend without a matching backend default

## Reference Commit

IM3-144 fixed all 7 schema mismatches in one commit. Check that commit message for the canonical payload shape. When in doubt, diff the current `runSimulation()` call against that commit.