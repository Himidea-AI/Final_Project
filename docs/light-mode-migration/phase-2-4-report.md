# Phase 2 영역 ④ 보고 — Nav/공용/랜딩

**작업자**: subagent-4 (Nav/공용/랜딩/HQ/JoinUs/auth)
**기준 룰**: `docs/light-mode-migration/conversion-rules.md` (1~14)
**노란 띠 인벤토리**: `docs/light-mode-migration/yellow-inventory-B.md`

## 통계

- **치환 hex 인스턴스**: 약 470건 (Tailwind 임의값 클래스 + Canvas2D / SVG inline literal 포함)
- **영향 파일**: 27개 (영역 ④ 안에서 실제 변경됨)
- **`dark:` prefix 폐기**: 0건 (전 영역 검색 결과 `dark:` 없음 — Phase 0-C 확인된 대로)
- **unmapped (보고)**: 0건 (룰 14개 표 + ABM POI §11 + 경쟁사 마커 매핑으로 100% 커버)

## 파일별 변경 요약

| 파일 | 주 변경 |
|---|---|
| `src/components/GlobalNav.tsx` | bg-card/border-border/text-muted-foreground 치환, shadow #818cf8→var(--primary), amber→warning |
| `src/components/BrandLogo.tsx` | bg-primary/text-primary, bg-card/border-border |
| `src/components/Toast.tsx` | success/error/info → text-success/danger/primary 토큰 |
| `src/components/CommandPalette.tsx` | bg-[#3a3633]→border, text-[#3a3633]→text-border, 모달 backdrop bg-black/70 |
| `src/components/DetailDrawer.tsx` | bg-card/border-border 풀세트, amber→warning 배지 |
| `src/components/AgentMapVisualizer.tsx` | bg-background, decor-cyan vacancy 마커, **경쟁사 marker rose→danger·orange→warning** (#FF3800 / #FF7940 hex8 alpha 보존) |
| `src/components/AbmPersonaMap.tsx` | **§11 ABM POI 4색 (Rose→danger·Amber→warning·Blue→primary·Stone→muted-foreground)**, Canvas2D ctx.fillStyle 67건은 token hex literal 보존 (CSS var 미지원), bg-[#1a2535]/[#070708]/[#111113] → background/card |
| `src/components/PersonaCard.tsx` | amber-* → warning |
| `src/components/VacancySpotMarker.tsx` | Kakao SDK 인자 #E45756 → #FF3800 (var(--danger) 토큰 hex), CustomOverlay HTML 안 background → var(--danger) |
| `src/components/VacancyStatsPanel.tsx` | amber-* → warning |
| `src/components/SimulationHistory/HistoryFilter.tsx` | bg-[#3a3633]/40 → bg-muted/40, ring-[#818cf8]/40 → ring-primary/40 |
| `src/components/SimulationHistory/HistoryCard.tsx` | yellow signal badge → warning |
| `src/components/SimulationHistory/ActivityDashboard.tsx` | text-amber-400 → text-warning |
| `src/components/TokenBurnrate/TokenBurnrateSection.tsx` | amber-* → warning (배너) |
| `src/components/ui/HybridSliderInput.tsx` | bg-[#404040]/[#3a3633] → border/border, placeholder, shadow rgba 토큰값(0,44,209)으로 보정 |
| `src/pages/landing/IntroScene.tsx` | text-[#3a3633] → text-border (8건) |
| `src/pages/landing/AccordionGallery.tsx` | bg-[#3a3633]→bg-muted, gradient from-[#1e1b18]/[#a3a3a3] → from-card/muted-foreground, amber → warning |
| `src/pages/landing/AboutPage.tsx` | text-[#3a3633] → text-border, decoration-[#3a3633] → decoration-border |
| `src/pages/landing/ContactPage.tsx` | conic-gradient #818cf8/#a5b4fc → var(--primary), text-[#1e1b18] (호버 텍스트) → text-primary-foreground |
| `src/pages/JoinUs/JoinUsPage.tsx` | border-[#2c2825]→border-border, gradient text-[#1e1b18] → success-foreground |
| `src/pages/JoinUs/components/SignupForm.tsx` | text-[#a5b4fc]→text-primary/60, border-[#9ca3af]→border-muted-foreground, amber gradient→warning gradient, amber-400→warning |
| `src/pages/JoinUs/components/RoleSelectView.tsx` | text-[#404040]→text-muted-foreground/60 |
| `src/pages/JoinUs/components/PricingCard.tsx` | conic-gradient #818cf8/#a5b4fc→var(--primary), text-[#a5b4fc]→text-primary, group-hover:text-[#1e1b18]→primary-foreground |
| `src/pages/JoinUs/components/ManagerSignupForm.tsx` | bg-[#3a3633]→bg-muted, gradient emerald→success, amber-400→warning |
| `src/pages/JoinUs/components/PlanBadge.tsx` | text-[#a5b4fc]→text-primary/60 |
| `src/pages/JoinUs/components/EnterpriseContactForm.tsx` | text-[#a5b4fc]→text-primary/60 |
| `src/pages/LoginPage.tsx` | bg-[#3a3633]→bg-border (디바이더), amber-* sessionExpired 알림→warning |
| `src/pages/HQCommandCenter.tsx` | 26건 처리 — text-[#1e1b18]→primary-foreground (CTA), bg-[#3a3633]→bg-muted, amber-* (CreditCard·Token 배너 4종)→warning, conic-gradient→var(--primary), bg-[#050505]/80→bg-black/80 |
| `src/pages/ManagerDetail.tsx` | amber-* → warning |
| `src/pages/SimulationHistoryDetail.tsx` | bg-[#0C0B0A]→bg-background, amber-500 PDF CTA→warning. **PDF html2canvas의 `backgroundColor: '#ffffff'` 는 PDF 인쇄용으로 §14 보존 정책에 따라 유지** |

## 룰 §11 ABM POI 4색 매핑 (AbmPersonaMap.tsx)

| 원본 | 토큰 | 토큰 hex (Canvas 용) |
|---|---|---|
| `#FB7185` Rose / `#f43f5e` / `#E45756` | `var(--danger)` | `#FF3800` |
| `#FBBF24` / `#FCD34D` Amber | `var(--warning)` | `#FF7940` |
| `#60A5FA` / `#818CF8` / `#4F46E5` Blue | `var(--primary)` | `#002CD1` |
| `#9CA3AF` / `#6b7280` Stone | `text-muted-foreground` | `#6B6A63` |

(Canvas2D ctx.fillStyle / SVG `fill=`/`stroke=` 는 CSS 변수 미지원 → 토큰의 라이트값 hex 리터럴로 치환)

## 추가 매핑 (룰 §11 외)

- `#34D399` resident → `#00BA7A` (success)
- `#F472B6` visitor → `#FF0070` (decor-hot-pink)
- `#22D3EE` ext_commuter → `#00E0D1` (decor-cyan)
- `#A78BFA` ext_visitor → `#B35CFF` (chart-4 vibrant-purple)
- `#86EFAC` light green → `#00BA7A` (success)
- `#1F2937` / `#111827` / `#0f172a` 흑색계 텍스트 → `#0a0a0a` (foreground)

## 처리 보존 (§14)

- `bg-black/70` 모달 backdrop — 기존
- `stroke="#000"` 순수 검은 SVG 외곽선 — 기존 보존 (벡터 외곽 강조)
- `HiddenPDFTemplate.tsx` — Q6 결정대로 **수정 금지**, 건드리지 않음
- `SimulationHistoryDetail.tsx:53` PDF `backgroundColor: '#ffffff'` — html2canvas PDF 인쇄용 흰 배경 유지

## tsc / prettier 결과

- `npx prettier --write` (영역 ④ 38개 파일): **PASS** (11개 파일 재포맷)
- `npx tsc --noEmit` (전역): **PASS** (exit 0)

## 비고

- `dark:` prefix 검색 결과 전 src/ 에서 0건 — Phase 0-C 확인된 대로.
- 영역 외 파일 (App.tsx, SimulationResult/**, dashboard/**, simulation/**, PDF/HiddenPDFTemplate.tsx, reference/**, *.test.tsx) **수정하지 않음**.
- AgentMapVisualizer 의 vacancy cyan 마커 (`#06b6d4`/`#22d3ee`) 는 룰 §13 decor-cyan 으로 매핑 — vacancy = "기회" 시그널이라 §11 4색 (위험/주의/선호/기본) 어디에도 안 맞아 큰면적 장식 토큰 사용.

---
작성: 2026-04-30 | subagent-4 | 영역 ④ Nav/공용/랜딩
