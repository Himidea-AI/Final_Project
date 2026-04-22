# frontend/scripts

## capture_sections.py — §01 ~ §15 Playwright 스크린샷

SimulatorDashboard 통합 리포트의 15 섹션을 개별 PNG로 저장.

### 준비 (1회)

```bash
# Python Playwright 설치 (이미 있으면 스킵)
pip install playwright
python -m playwright install chromium
```

### 실행

**사전 조건**: backend(`uvicorn src.main:app --port 8000`) + frontend(`npm run dev`) 모두 기동 중

```bash
# 레포 루트에서
python frontend/scripts/capture_sections.py

# 디버깅 (브라우저 창 보이기)
python frontend/scripts/capture_sections.py --headed

# 타임아웃 조정 (기본 300s)
python frontend/scripts/capture_sections.py --timeout 600

# 풀페이지 스킵 (섹션별 15장만)
python frontend/scripts/capture_sections.py --skip-full
```

### 출력

`frontend/screenshots/` 디렉터리에:

```
00-integrated-full.png       전체 풀페이지 (--skip-full 없을 때)
01-command-bar.png           §01
02-headline.png              §02
03-primary-kpis.png          §03
04-scorecard.png             §04
05-map.png                   §05
06-indicator-grid.png        §06
07-quarterly-forecast.png    §07
08-scenarios.png             §08
09-shap.png                  §09
10-timeline.png              §10
11-agent-attribution.png     §11
12-district-rankings.png     §12
13-insights-grid.png         §13
14-decision-memo.png         §14
15-report-footer.png         §15
```

### 구동 원리

1. Chromium 1440×900 @2x 뷰포트 기동 (headless 기본)
2. `localStorage.spotter_auth`에 fake master user 주입 → `ProtectedRoute` 우회
   (현 `AuthContext`가 localStorage만 검증하고 JWT 서명 확인은 없음)
3. `/simulator` 이동 → "RUN SIMULATION" 버튼 클릭
4. 기본 선택값(업종: 커피-음료, 동: 마포구 16동 전체)으로 실 시뮬 실행
5. `#section-01` 렌더 완료까지 대기 (최대 5분, 실 LLM·DB 호출)
6. 페이지 하단까지 슬로우 스크롤 → Recharts/Kakao lazy 렌더 트리거
7. 각 `#section-NN` element screenshot + 전체 풀페이지 캡처

### 트러블슈팅

| 증상 | 원인 / 대응 |
|------|------|
| `[ERR] /simulator 로드 실패` | frontend dev서버(`npm run dev`)가 `:3000` 아닌 포트면 `--port` 지정 |
| `[ERR] RUN SIMULATION 버튼 클릭 실패` | 로그인 우회 실패. fake auth user role/필드 변경되었으면 `FAKE_AUTH` 수정 |
| `[ERR] 결과 타임아웃` | backend `/simulate` 500 또는 지연. uvicorn 콘솔 traceback 확인 |
| `error-*.png` 파일 생성됨 | 해당 시점 화면 캡처 — 어느 단계에서 멈췄는지 진단용 |
| 섹션별 이미지가 레거시 뷰 | `viewMode !== 'integrated'` — App.tsx 토글 기본값 확인 |

### 설정 변경 지점

- 뷰포트: `capture_sections.py` 내 `viewport={"width": 1440, "height": 900}`
- 해상도: `device_scale_factor=2` (@2x 레티나)
- Fake auth 필드: 상단 `FAKE_AUTH` dict
- 섹션 순서/slug: 상단 `SECTIONS` 리스트 — `IntegratedReport.tsx`의 `id="section-NN"`과 1:1
