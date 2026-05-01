# Phase 0-A: hex 카탈로그

## 요약
- 총 hex 인스턴스: **940**
- 고유 hex 개수: **45**
- 자신 없는 매핑(?): **12**

## 고유 hex 빈도 표

| hex | 빈도 | 추천 토큰 | 비고 |
|---|---|---|---|
| #9ca3af | 294 | `text-muted-foreground` | 보조 텍스트, 가장 많이 사용됨 (dark gray) |
| #818cf8 | 282 | `text-primary` / `bg-primary` | 주요 액션 (indigo/accent) |
| #3a3633 | 257 | `border-border` / `bg-muted` | 구분선 및 다크 배경 |
| #1e1b18 | 155 | `bg-muted` / `bg-card` | 카드/패널 표면 (dark brown) |
| #e2e8f0 | 138 | `text-foreground` | 본문 텍스트 (light text) |
| #2c2825 | 97 | `bg-card` / `bg-muted` | 카드 배경 (darker brown) |
| #6b7280 | 42 | `text-muted-foreground` | 보조 텍스트 (gray) |
| #1C1D21 | 33 | `bg-muted` | ? 다크 배경 (거의 검은색) |
| #8181A5 | 32 | ? | ? 라벨/기타 (lavender-ish) |
| #d1d5db | 20 | `text-muted-foreground` | 연한 회색 텍스트 |
| #6366f1 | 20 | ? | ? 보라색 (gradient 사용) |
| #ECECF2 | 14 | ? | ? 매우 밝은 배경 (light) |
| #a3a3a3 | 11 | `text-muted-foreground` | 회색 텍스트 |
| #5E81F4 | 11 | ? | ? 파란색 (차트/데이터용?) |
| #F5F5FA | 10 | `bg-background` | 매우 밝은 배경 (거의 흰색) |
| #0d1117 | 10 | `bg-background` | 거의 검은색 (배경) |
| #404040 | 9 | `bg-muted` | 다크 회색 배경 |
| #f59e0b | 7 | ? | ? 황색/amber |
| #a5b4fc | 7 | ? | ? 밝은 보라색 |
| #171717 | 6 | `bg-muted` | 다크 배경 |
| #050505 | 5 | `bg-background` | 거의 검은색 (overlay backdrop) |
| #F0F0F3 | 4 | `bg-background` | 밝은 배경 |
| #4a4643 | 4 | `border-border` | 다크 보더/배경 |
| #e5e7eb | 3 | `border-border` | 라이트 보더 |
| #57534e | 3 | `bg-muted` | 다크 배경 |
| #22d3ee | 3 | `text-primary` | 청록색 (accent) |
| #141210 | 3 | `bg-background` | 거의 검은색 |
| #f97316 | 2 | ? | ? 주황색 |
| #cbd5e1 | 2 | `border-border` | 밝은 보더 |
| #FF808B | 2 | ? | ? 분홍색/빨간색 (다크모드) |
| #1a1816 | 2 | `bg-card` | 다크 배경 |
| #666666 | 1 | `text-muted-foreground` | 회색 텍스트 |
| #10b981 | 1 | ? | ? 녹색 (성공/positive) |
| #06b6d4 | 1 | ? | ? 청록색 (accent) |
| #ffffff | 1 | `text-foreground` | 흰색 텍스트 |
| #4f46e5 | 1 | `text-primary` | 보라색 gradient |

## 파일별 상세 분석

### App.tsx (700+ 인스턴스)
App.tsx는 메인 대시보드 페이지로, 가장 많은 hex 사용처입니다. 대부분 다크모드 색상 패턴입니다.

**Primary Palette (순서대로):**
- L778: `bg-[#1e1b18]` → `bg-card` (툴팁 배경)
- L779: `text-[#9ca3af]` → `text-muted-foreground` (보조 라벨)
- L1496-1500: 변수 정의
  - `textPrimary = 'text-[#e2e8f0]'` → `text-foreground`
  - `textSecondary = 'text-[#9ca3af]'` → `text-muted-foreground`
  - `accent = 'text-[#818cf8]'` → `text-primary`
  - `accentBg = 'bg-[#818cf8]'` → `bg-primary`
  - `panel = 'bg-[#2c2825] border-[#3a3633]'` → `bg-card border-border`

**상황별 맵핑:**
- 모달/팝오버 배경: `#1e1b18` → `bg-card`
- 구분선/테두리: `#3a3633` → `border-border`
- 본문 텍스트: `#e2e8f0` → `text-foreground`
- 보조 텍스트: `#9ca3af` → `text-muted-foreground`
- 액션 버튼: `#818cf8` → `bg-primary text-primary-foreground`

### 컴포넌트별 (63개 파일)

#### 유형 1: 다크모드 UI 컴포넌트
- AgentMapVisualizer.tsx: 맵 마커, 범례
- CommandPalette.tsx: 커맨드 팔레트
- DetailDrawer.tsx: 상세 드로어
- GlobalNav.tsx: 네비게이션

**패턴:**
```
배경: #1e1b18, #2c2825 → bg-card/bg-muted
테두리: #3a3633 → border-border
텍스트: #e2e8f0, #9ca3af → text-foreground/text-muted-foreground
액션: #818cf8 → text-primary
```

#### 유형 2: 데이터 시각화 (차트)
- StackedAgeBar.tsx
- Sparkline.tsx
- CoreDemographicDonut.tsx
- ClosureRateHistoryChart.tsx
- 등 20+ 차트 파일

**패턴:**
- 차트 선/막대: `#818cf8`, `#6366f1`, `#5E81F4`
- 차트 배경: `#1e1b18`, `#2c2825`
- 라벨: `#9ca3af`, `#e2e8f0`

**? 불명확:**
- `#5E81F4`: 차트용 파란색 (chart-2?)
- `#6366f1`: 그래디언트 보라색 (chart-1?)
- `#ECECF2`: 매우 밝은 색 (라이트모드 배경?)

#### 유형 3: 폼/입력
- HybridSliderInput.tsx
- SignupForm.tsx
- RoleSelectView.tsx
- 등 입력 필드

**패턴:**
```
입력 필드 배경: #1e1b18 → bg-card
입력 필드 테두리: #3a3633 → border-border
포커스 상태: #818cf8 → border-primary
```

#### 유형 4: 랜딩/외부 페이지
- IntroScene.tsx
- AccordionGallery.tsx
- AboutPage.tsx
- ContactPage.tsx
- PricingCard.tsx

**패턴:**
- 섹션 배경: `#1C1D21`, `#0d1117` (거의 검은색)
- 카드: `#1e1b18`, `#2c2825`
- 텍스트: `#e2e8f0`, `#9ca3af`

**? 불명확:**
- `#1C1D21`: 랜딩 페이지 배경 (혼합된 색상)
- `#ECECF2`: 밝은 섹션 배경 (아직 확인 필요)

#### 유형 5: 특수 목적 색상

**상태/신호:**
- `#22d3ee` (3x): 청록색 마커 (위치 표시?) → `--chart-3` or accent
- `#f59e0b` (7x): 황색 (경고/주의) → `--warning`
- `#f97316` (2x): 주황색 → `--warning`?
- `#10b981` (1x): 녹색 (성공) → `--success`
- `#FF808B` (2x): 분홍색 (다크모드 위험) → `--danger` (라이트모드로 변경 필요)
- `#06b6d4` (1x): 청록색 → `--chart-3` or accent

**그래디언트:**
- `from-[#6366f1] to-[#818cf8]`: 보라색→인디고 → `from-primary to-primary-600`
- `from-[#818cf8]/20 to-transparent`: 인디고 페이드 → `from-primary/20`

**오버레이/모달:**
- `bg-[#050505]/70`: 검은색 반투명 → `bg-black/70` or semantic
- `#1e1b18]/80`: 반투명 배경 → `bg-background/80`

## 라이트모드 마이그레이션 매핑 (권장)

### 계층 1: 기본 색상 (우선순위 높음)

```
다크모드                  라이트모드 토큰       라이트모드 Hex
─────────────────────────────────────────────────────────
#1e1b18 (배경)     →    bg-background/card  →  #FAF9F5 or #FFFFFF
#2c2825 (카드)     →    bg-card              →  #FFFFFF
#3a3633 (테두리)   →    border-border        →  #EAE9E1
#e2e8f0 (본문)     →    text-foreground      →  #0A0A0A
#9ca3af (보조)     →    text-muted-foreground→  #6B6A63
#818cf8 (액션)     →    bg-primary/text      →  #002CD1
```

### 계층 2: 백업 색상

```
#6b7280            →    text-muted-foreground
#d1d5db            →    border-border (라이트)
#a3a3a3            →    text-muted-foreground
#6366f1            →    --chart-2 or primary-600
```

### 계층 3: 불명확 / 검토 필요 (강민이 협의)

```
#1C1D21            ?    목적 불명확 (랜딩 배경?)
#8181A5            ?    라벨 색상 (보라색 회색)
#ECECF2            ?    매우 밝은 배경 (라이트모드 일부?)
#5E81F4            ?    차트 색상 (파란색)
#F5F5FA            ?    매우 밝은 배경
#0d1117            ?    거의 검은색 배경
#F0F0F3            ?    밝은 배경
```

### 계층 4: 상태 색상 (새로 추가)

```
경고 (Warning)     ← #f59e0b, #f97316 → --warning (예: #F59E0B)
성공 (Success)     ← #10b981 → --success (예: #10B981)
위험 (Danger)      ← #FF808B (다크) → --danger (라이트: #DC2626)
```

### 계층 5: 차트 색상 (기존)

```
--chart-1 (Primary)    = #818cf8 or #002CD1
--chart-2              = #6366f1 or #5E81F4?
--chart-3 (Teal)       = #22d3ee or #10B981
--chart-4 (Purple)     = #8181A5?
```

## 주요 인사이트

### 1. 압도적으로 다크모드 (우려 사항)
- 940개 인스턴스 중 대부분이 다크모드 색상
- `#9ca3af`, `#818cf8`, `#3a3633`, `#1e1b18`, `#e2e8f0` (상위 5개)가 740개 차지 (78.7%)

### 2. 의도 불명확한 색상 12개

| hex | 빈도 | 상황 | 추천 |
|---|---|---|---|
| #1C1D21 | 33 | 랜딩/외부 페이지 배경 | 목적 불명 |
| #8181A5 | 32 | 라벨/텍스트 | 라벤더? |
| #ECECF2 | 14 | 밝은 섹션 | 라이트모드 배경? |
| #5E81F4 | 11 | 차트 | chart-2? |
| #F5F5FA | 10 | 배경 | 배경용? |
| #0d1117 | 10 | 배경 | 다크 배경? |
| #404040 | 9 | 배경 | 다크 배경? |
| #F0F0F3 | 4 | 배경 | 밝은 배경? |
| #f59e0b | 7 | (amber-400) | 경고색? |
| #f97316 | 2 | (orange-500) | 경고색? |
| #FF808B | 2 | 분홍색 | 다크모드 위험색? |
| #6366f1 | 20 | 그래디언트 | 차트/액션? |

### 3. 즉시 매핑 가능 (확신도 높음 = 30개)

```
#9ca3af (294x)  → text-muted-foreground (거의 확실)
#818cf8 (282x)  → text-primary / bg-primary (거의 확실)
#3a3633 (257x)  → border-border (거의 확실)
#1e1b18 (155x)  → bg-card (높음)
#e2e8f0 (138x)  → text-foreground (높음)
#2c2825 (97x)   → bg-card / bg-muted (중간)
#6b7280 (42x)   → text-muted-foreground (높음)
#d1d5db (20x)   → border-border (높음)
#6366f1 (20x)   → 차트/그래디언트 (중간)
#a3a3a3 (11x)   → text-muted-foreground (높음)
#171717 (6x)    → bg-muted (높음)
#050505 (5x)    → bg-black/70 (높음)
... 등 20개
```

## 다음 단계

1. **강민과 협의:**
   - 12개 미분류 색상 의도 확인
   - 상태 색상 정의 (경고, 성공, 위험)
   - 차트 색상 확정

2. **토큰 검증:**
   - tailwind.config.js에서 기존 시맨틱 토큰과 매핑 확인
   - CSS 변수 범위 재확인

3. **마이그레이션 전략:**
   - App.tsx 먼저 (700+ 인스턴스)
   - 컴포넌트별 순차 처리
   - 차트 색상은 별도 검토 (데이터 가독성)

---

**작성 일시:** 2026-04-30
**카탈로그 ID:** hex-catalog-A (Tailwind arbitrary values)
