# Phase 0-C: 다크모드 의존성 전수 인벤토리

## 요약

**현황: 다크모드 코드 미구현 상태**

| 항목 | 결과 |
|------|------|
| `dark:` Tailwind prefix | 0건 (0파일) |
| `isDark` state/props | 0건 |
| SkyThemeToggle import | 0건 |
| 직접 DOM 토글 코드 | 0건 |
| tailwind.config darkMode 설정 | 없음 |

**주요 발견:**
- 다크모드 토글 코드는 **주석으로만 존재** (App.tsx)
- 실제 구현부는 전혀 없음
- Tailwind `darkMode` 옵션 미설정
- 정리 작업 불필요 (이미 라이트모드 단일)
- 단, `index.css :root` 색상값은 다크톤이므로 라이트 값으로 변경 필요

---

## 상세 조사 결과

### 1. tailwind.config.js

**파일 경로:** `/frontend/tailwind.config.js`

**결과: darkMode 옵션 없음**

```javascript
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: { ... },
      colors: { ... },
      borderRadius: { ... },
    },
  },
  plugins: [],
};
```

- `darkMode` 설정 항목 없음
- CSS 변수 기반 색상 체계만 정의
- Tailwind `dark:` 프리픽스 미활성화 상태

---

### 2. index.css

**파일 경로:** `/frontend/src/index.css`

**결과: .dark 선택자 및 @media 분기 없음**

**현재 구조:**
```css
@layer base {
  :root {
    --background: #0c0b0a;        /* 다크 배경 */
    --foreground: #e2e8f0;        /* 라이트 전경 */
    --card: #1a1a1a;              /* 다크 카드 */
    --card-foreground: #e2e8f0;
    --primary: #818cf8;
    --secondary: #292524;
    /* ... 11개 변수 ... */
  }
}
```

**다크모드 흔적:**
- `:root` 변수 값이 모두 다크톤
- `.dark` 선택자 없음
- `@media (prefers-color-scheme: dark)` 분기 없음
- 스크롤바 스타일 (#3a3633 어두운 톤)

---

### 3. index.html

**파일 경로:** `/frontend/index.html`

**결과: 다크모드 관련 마크업 없음**

```html
<!doctype html>
<html lang="ko" style="overflow:hidden;height:100%;margin:0;background:#1e1b18">
  <body style="overflow:hidden;height:100%;margin:0;background:#1e1b18">
    <div id="root"></div>
  </body>
</html>
```

- inline style에 다크 배경색만 지정
- `data-theme`, `dark` 클래스 속성 없음

---

### 4. App.tsx 다크모드 관련 내용

**파일 경로:** `/frontend/src/App.tsx` (4432줄)

#### 4.1 주석으로만 존재하는 구조 (라인 30-32)

```typescript
 * [테마 시스템]
 *   - CSS Variables (index.css) + Tailwind darkMode:"class"
 *   - isDark state → <div className="dark"> 토글
 *   - SkyThemeToggle 컴포넌트로 Light/Dark 전환
 *   - 시맨틱 클래스: bg-background, text-foreground, bg-card, text-primary 등
```

#### 4.2 주석으로만 존재하는 상태 (라인 4307-4313)

```typescript
   [글로벌 상태]
   - isDark: Light/Dark 테마 토글 (SkyThemeToggle 연결)
   - isTransitioning: 씬 전환 시 800ms 암전 오버레이
   - isAppLoaded: 프리로더 완료 여부

   [글로벌 헤더]
   - 인트로 제외 모든 씬에 공통 표시
   - 좌: 로고+BACK / 우: SkyThemeToggle + GlobalLimelightNav
```

#### 4.3 실제 코드 검색 결과

| 항목 | 검색 | 결과 |
|------|------|------|
| `isDark` 변수 | `const [isDark, setIsDark]` | ❌ 없음 |
| `className="dark"` | 토글 렌더링 | ❌ 없음 |
| `SkyThemeToggle` import | 컴포넌트 호출 | ❌ 없음 |
| `document.documentElement.classList` | DOM 토글 | ❌ 없음 |

---

### 5. 전체 src/ 컴포넌트 검색 결과

**검색 범위:** `/frontend/src/**/*.{tsx,ts}` (figma-crm-kit 제외)

#### 5.1 Tailwind `dark:` prefix

```bash
$ grep -rn "dark:" src/ --include="*.tsx" --include="*.ts"
# 결과: 0건
```

**결론:** Tailwind `dark:` 프리픽스 사용처 없음

#### 5.2 isDark 관련 props/state

```bash
$ grep -rn "isDark|setIsDark|darkMode" src/ --include="*.tsx"
# 결과: App.tsx의 주석 2개 제외 0건
```

**결론:**
- isDark prop 주고받기 없음
- darkMode enum/type 없음

#### 5.3 SkyThemeToggle

```bash
$ grep -rn "SkyThemeToggle" src/
# 결과: App.tsx의 주석 2개
```

**결론:**
- SkyThemeToggle 컴포넌트 정의 파일 없음
- import 사용처 없음

#### 5.4 DOM API / localStorage

```bash
$ grep -rn "classList.add.*dark|localStorage.*theme|prefers-color-scheme" src/
# 결과: 0건
```

**결론:**
- document API를 통한 다크 클래스 토글 없음
- localStorage 테마 저장 코드 없음
- 시스템 `prefers-color-scheme` 감지 없음

---

## 다크 잔재 정리 체크리스트

| 항목 | 현황 | 조치 |
|------|------|------|
| tailwind.config.js `darkMode` 옵션 | 없음 ✓ | 제거 불필요 |
| index.css `.dark` 선택자 | 없음 ✓ | 제거 불필요 |
| index.css `@media (prefers-color-scheme: dark)` | 없음 ✓ | 제거 불필요 |
| SkyThemeToggle 컴포넌트 정의 | 없음 ✓ | 삭제 불필요 |
| App.tsx `isDark` state | 없음 ✓ | 제거 불필요 |
| 전체 `dark:` prefix | 0건 ✓ | 정리 불필요 |
| App.tsx 주석 (다크모드 언급) | 있음 | **정리 권장** |

---

## 다음 단계 (라이트모드 단일 전환)

### Phase 1: Color Token Migration

`index.css :root` 변수를 다크톤에서 라이트톤으로 교체:

```css
@layer base {
  :root {
    /* 현재 (다크톤) */
    --background: #0c0b0a;      /* → #ffffff (또는 #fafaf8) */
    --foreground: #e2e8f0;      /* → #1a1a1a */
    --card: #1a1a1a;            /* → #ffffff */
    --card-foreground: #e2e8f0; /* → #1a1a1a */
    /* ... 나머지 색상 반전 ... */
  }
}
```

### Phase 2: Comment Cleanup

App.tsx에서 다크모드 관련 주석 제거:
- 라인 30-32: 테마 시스템 설명 업데이트
- 라인 4307-4313: 글로벌 상태 설명 업데이트

### Phase 3: Validation

- Figma/디자인 시스템과 색상 대응 확인
- 모든 페이지 라이트모드 렌더링 테스트
- 접근성(대비도) 검증

---

## 파일 목록

| 파일 | 경로 | 역할 | 상태 |
|------|------|------|------|
| tailwind.config.js | `/frontend/` | Tailwind 설정 | ✓ 다크모드 코드 없음 |
| index.css | `/frontend/src/` | 색상 토큰 정의 | ⚠ 값만 다크톤 (코드 없음) |
| index.html | `/frontend/` | HTML 진입점 | ✓ 다크모드 마크업 없음 |
| App.tsx | `/frontend/src/` | 글로벌 레이아웃 | ⚠ 주석만 언급 |

---

## 결론

SPOTTER frontend의 다크모드는 **설계 단계의 주석으로만 존재**하며, 실제 구현 코드는 전혀 없습니다. 따라서:

1. **다크모드 폐기 작업 불필요** — 이미 제거된 상태
2. **라이트모드 전환 작업** = `index.css :root` 색상값 변경 + 주석 정리만 필요
3. **우선순위** → Color Token Migration (Phase 1)

마이그레이션 시 타이밍:
- [ ] `index.css` 색상값 라이트톤으로 교체
- [ ] App.tsx 관련 주석 업데이트 또는 제거
- [ ] QA: 전체 페이지 라이트모드 확인
- [ ] 디자인 시스템과 색상 대응 검증

---

**생성일:** 2026-04-30
**조사 범위:** `/frontend/src/` + `tailwind.config.js` + `index.html`
**검색 도구:** grep, glob (figma-crm-kit 제외)
