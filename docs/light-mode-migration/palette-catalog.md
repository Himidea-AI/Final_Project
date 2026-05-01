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

### Point — 브랜드/포인트 (2)
주된 액션·강조. 사용 빈도 가장 높음.

| 이름            | Hex       | CSS 변수                  | 역할                                                              |
| --------------- | --------- | ------------------------- | ----------------------------------------------------------------- |
| Starburst Pink  | `#FF78B9` | `--color-starburst-pink`  | 장식 only (`--decor-starburst-pink`) — 작은 마커/얇은 선/텍스트 X |
| **Deep Blue**   | `#002CD1` | `--color-deep-blue`       | **브랜드 primary** (`--primary`, `--ring`, `--chart-1`)           |

> **Deep Blue가 brand primary**. 이전 인디고(`#6366f1` / `#818cf8`)는 다크모드 잔재. 모든 indigo RGB 값(`99,102,241` / `129,140,248`)은 `0,44,209`로 치환 완료.

### Geometric — 데이터/상태 (5)
차트·상태·KPI. 라이트 배경에서 충분한 컨트라스트(≥ 4.5:1) 확보된 색만 들어감.

| 이름              | Hex       | CSS 변수                | 역할                                                  |
| ----------------- | --------- | ----------------------- | ----------------------------------------------------- |
| Vivid Red         | `#FF3800` | `--color-vivid-red`     | `--destructive`, `--danger`, `--chart-2`              |
| Bright Cyan       | `#00E0D1` | `--color-bright-cyan`   | 장식 only (`--decor-cyan`) — 라이트에서 1.2:1, 얇은 선/텍스트 X |
| Sunshine Yellow   | `#FFDE00` | `--color-sunshine-yellow` | 장식 only (`--decor-yellow`) — 1.3:1, 큰 면적만       |
| Teal Green        | `#00BA7A` | `--color-teal-green`    | `--success`, `--chart-3`                              |
| Hot Pink          | `#FF0070` | `--color-hot-pink`      | 장식 only (`--decor-hot-pink`) — 큰 면적/배지         |

### Shapes — 보조/장식 (3)
보조 강조·세그먼트.

| 이름            | Hex       | CSS 변수                | 역할                                  |
| --------------- | --------- | ----------------------- | ------------------------------------- |
| Soft Orange     | `#FF7940` | `--color-soft-orange`   | `--warning`                           |
| Light Pink      | `#FFB6D0` | `--color-light-pink`    | 장식 only (`--decor-light-pink`)      |
| Vibrant Purple  | `#B35CFF` | `--color-vibrant-purple`| `--chart-4` (4동 비교 차트)           |

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
--color-starburst-pink: #ff78b9;
--color-deep-blue: #002cd1;
--color-vivid-red: #ff3800;
--color-bright-cyan: #00e0d1;
--color-sunshine-yellow: #ffde00;
--color-teal-green: #00ba7a;
--color-hot-pink: #ff0070;
--color-soft-orange: #ff7940;
--color-light-pink: #ffb6d0;
--color-vibrant-purple: #b35cff;
```

---

## 변경 시 동기화 체크리스트

새 색 추가/기존 색 수정 시:

- [ ] `frontend/src/index.css` `--color-*` 변수 정의
- [ ] (필요 시) `--decor-*` / `--chart-*` / status alias (`--success` 등) 갱신
- [ ] `frontend/tailwind.config.js` `colors` 매핑 갱신 (chart, decor, status alias)
- [ ] 이 문서(`palette-catalog.md`) 업데이트
- [ ] `docs/light-mode-migration/conversion-rules.md`에 새 색 → 토큰 매핑 추가
