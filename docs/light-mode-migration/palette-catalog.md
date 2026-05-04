# SPOTTER Light Mode — 공식 12색 팔레트 (Single Source of Truth)

> **이 문서가 진실.** `frontend/src/index.css`의 `--color-*` 변수와 1:1 동기화돼야 합니다. 새 색이 필요하면 먼저 이 12색 안에서 매핑하세요. 외부에서 색을 가져오지 않습니다.

원본 출처: 디자인 팀에서 `Colorful Geometric Shapes` 팔레트로 확정 (2026-04-30, Phase 1 토큰 정의 commit `84b7fd4`).

---

## 4 그룹

### Base — 인프라 (2)
페이지 배경/본문. 의미 없는 중립.

| 이름             | Hex       | CSS 변수             | 역할                                                                  |
| ---------------- | --------- | -------------------- | --------------------------------------------------------------------- |
| Background Cream | `#F8F7E8` | `--color-cream`      | **페이지 바닥** (`--background`), `--accent`/`--decor-cream` 별칭 유지 |
| Text Black       | `#000000` | `--color-text-black` | 본문 텍스트 (alias: `--foreground`)                                  |

### Point — 브랜드/포인트 (5)
주된 액션·강조 + Deep Blue Sequential 4-tier (4동 ranking 비교 / quarter ordinal / 시간 시퀀스).

| 이름                  | Hex       | CSS 변수                  | 역할                                                                       |
| --------------------- | --------- | ------------------------- | -------------------------------------------------------------------------- |
| Console Pink          | `#EB367F` | `--color-starburst-pink`  | 장식 only (`--decor-starburst-pink`) — 토큰명 historical                   |
| **Deep Blue (Main)**  | `#002CD1` | `--color-deep-blue`       | **브랜드 primary** (`--primary`, `--ring`, `--chart-1`, `--rank-1`) — 1위  |
| Electric Blue (Sub 1) | `#3D62FF` | `--color-electric-blue`   | Sequential 2단계 (`--rank-2`) — 4동 비교 2위                               |
| Sky Blue (Sub 2)      | `#87A5FF` | `--color-sky-blue`        | Sequential 3단계 (`--rank-3`) — 4동 비교 3위                               |
| Ice Blue (Sub 3)      | `#C2D1FF` | `--color-ice-blue`        | Sequential 4단계 (`--rank-4`) — 4동 비교 4위 (outlier, dashed 라인 권장)   |

> **Deep Blue가 brand primary**. 이전 인디고(`#6366f1` / `#818cf8`)는 다크모드 잔재. 모든 indigo RGB 값(`99,102,241` / `129,140,248`)은 `0,44,209`로 치환 완료.

#### Deep Blue Sequential 4-tier (`--rank-1` ~ `--rank-4`)

- **용도**: 4동 ranking 비교 / quarter ordinal (Q1~Q4) / 시간 시퀀스 — categorical 다른 hue로 분리한 chart-2~4 와 의미 구분.
- **이유**: 4동 ranking 은 ordinal (winner→4위) 의미라 monochromatic gradient 가 정합. categorical(chart-1~4) 은 의미 분리, sequential(rank-1~4) 은 순위 강도.
- **Stroke hierarchy (LineChart)**:
  - 1위 (Winner) : stroke 3px / dot r=5 / solid
  - 2~3위        : stroke 2.5px / dot r=4 / solid
  - 4위 (Ice)    : stroke 3px / dot r=4 / **dashed `6 3`** — Ice Blue 1.3:1 contrast 를 형태 채널로 보완
- **BarChart**: fill 만 적용 (dash 의미 없음). Bar 면적이 크니까 Ice Blue 도 가독성 확보. 통일감 우선.
- **Ice Blue (1.3:1)** 는 WCAG fail — LineChart 에선 stroke 3px + dashed 또는 큰 면적 fill only. 작은 마커 / 얇은 선 / 텍스트 사용 금지.

### Geometric — 데이터/상태 (5)
차트·상태·KPI. 라이트 배경에서 충분한 컨트라스트(≥ 4.5:1) 확보된 색만 들어감.

| 이름              | Hex       | CSS 변수                | 역할                                                  |
| ----------------- | --------- | ----------------------- | ----------------------------------------------------- |
| Danger Coral      | `#FB565B` | `--color-vivid-red`     | `--destructive`, `--danger`, `--chart-2` (토큰명 historical) |
| Bright Cyan       | `#00E0D1` | `--color-bright-cyan`   | 장식 only (`--decor-cyan`) — 라이트에서 1.2:1, 얇은 선/텍스트 X |
| Sunshine Yellow   | `#FFDE00` | `--color-sunshine-yellow` | 장식 only (`--decor-yellow`) — 1.3:1, 큰 면적만       |
| Success Emerald   | `#008B00` | `--color-teal-green`    | `--success`, `--chart-3` (토큰명 historical)          |
| Hot Pink          | `#FF0070` | `--color-hot-pink`      | 장식 only (`--decor-hot-pink`) — 큰 면적/배지         |

### Shapes — 보조/장식 (3)
보조 강조·세그먼트.

| 이름            | Hex       | CSS 변수                | 역할                                  |
| --------------- | --------- | ----------------------- | ------------------------------------- |
| Warning Amber   | `#FFBA00` | `--color-soft-orange`   | `--warning` (토큰명 historical)       |
| Light Pink      | `#FFB6D0` | `--color-light-pink`    | 장식 only (`--decor-light-pink`)      |
| Console Purple  | `#7928CA` | `--color-vibrant-purple`| `--chart-4` (4동 비교 차트, 토큰명 historical) |

---

## 사용 규칙

1. **장식(`--decor-*`)으로 선언된 5색**(Starburst Pink, Bright Cyan, Sunshine Yellow, Hot Pink, Light Pink)은 **큰 면적의 장식·헤더 띠·배지에만**. 라이트 배경에서 컨트라스트 1.2~1.5:1 → 작은 마커, 얇은 선, 텍스트 색으로 사용 금지.
2. **데이터 자리**(차트 라인/텍스트/아이콘/얇은 보더)에 들어가도 되는 색은 4색뿐: Deep Blue, Vivid Red, Teal Green, Vibrant Purple — `--chart-1~4`.
3. **새 컴포넌트는 무조건 위 12색 안에서 매핑**. Tailwind 기본 팔레트(`bg-blue-500`, `text-rose-400` 등) 또는 임의 hex 사용 금지. 외부 디자인 차용 시 가장 가까운 12색으로 변환 후 사용.
4. **System A**(`--background`, `--card`, `--muted`, `--border`, `--foreground`, `--muted-foreground`)는 의미 없는 중립 인프라 6색. 의미 있는 색은 무조건 System B(이 12색)에서.

---

## 빠른 참조

```css
/* frontend/src/index.css — :root */
--color-cream: #f8f7e8;
--color-text-black: #000000;
--color-starburst-pink: #eb367f;   /* Console Pink (2026-05-03 hex 교체) */
--color-deep-blue: #002cd1;        /* Main — 1위 / primary */
--color-electric-blue: #3d62ff;    /* Sub 1 — 2위 (Sequential 4-tier) */
--color-sky-blue: #87a5ff;         /* Sub 2 — 3위 */
--color-ice-blue: #c2d1ff;         /* Sub 3 — 4위 outlier */
--color-vivid-red: #fb565b;        /* Danger Coral (2026-05-03 hex 교체) */
--color-bright-cyan: #00e0d1;
--color-sunshine-yellow: #ffde00;
--color-teal-green: #008b00;       /* Success Emerald */
--color-hot-pink: #ff0070;
--color-soft-orange: #ffba00;      /* Warning Amber */
--color-light-pink: #ffb6d0;
--color-vibrant-purple: #7928ca;   /* Console Purple */

/* ranking alias — 4동 비교 차트 ordinal 매핑 */
--rank-1: var(--color-deep-blue);
--rank-2: var(--color-electric-blue);
--rank-3: var(--color-sky-blue);
--rank-4: var(--color-ice-blue);
```

---

## 변경 시 동기화 체크리스트

새 색 추가/기존 색 수정 시:

- [ ] `frontend/src/index.css` `--color-*` 변수 정의
- [ ] (필요 시) `--decor-*` / `--chart-*` / status alias (`--success` 등) 갱신
- [ ] `frontend/tailwind.config.js` `colors` 매핑 갱신 (chart, decor, status alias)
- [ ] 이 문서(`palette-catalog.md`) 업데이트
- [ ] `docs/light-mode-migration/conversion-rules.md`에 새 색 → 토큰 매핑 추가
