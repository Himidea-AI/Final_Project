"""
SimulatorDashboard 15 섹션 Playwright 스크린샷 캡처.

사용 전 제약:
  1) backend 기동 (uvicorn localhost:8000) — 실 시뮬에 필수
  2) frontend 기동 (vite localhost:3000)
  3) Python Playwright 설치:
       pip install playwright && python -m playwright install chromium

실행:
  python frontend/scripts/capture_sections.py [--headed] [--port 3000] [--timeout 300]

출력: frontend/screenshots/
  00-integrated-full.png                전체 풀페이지
  01-command-bar.png ~ 15-report-footer.png   섹션별 element

Auth: localStorage에 fake 'spotter_auth' 주입으로 ProtectedRoute 우회
(현 AuthContext가 localStorage만 확인하므로 JWT 검증 없음).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PwTimeout, sync_playwright

# Windows cp949 콘솔에서 emoji 출력 시 UnicodeEncodeError — UTF-8로 강제.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 스크립트 위치 기준 repo root → 어느 디렉터리에서 실행해도 screenshots 경로 고정
_SCRIPT_DIR = Path(__file__).resolve().parent  # frontend/scripts
_FRONTEND_DIR = _SCRIPT_DIR.parent  # frontend
_REPO_ROOT = _FRONTEND_DIR.parent  # mapo-franchise-simulator
_DEFAULT_OUTPUT = _FRONTEND_DIR / "screenshots"

SECTIONS: list[tuple[str, str]] = [
    ("01", "command-bar"),
    ("02", "headline"),
    ("03", "primary-kpis"),
    ("04", "scorecard"),
    ("05", "map"),
    ("06", "indicator-grid"),
    ("07", "quarterly-forecast"),
    ("08", "scenarios"),
    ("09", "shap"),
    ("10", "timeline"),
    ("11", "agent-attribution"),
    ("12", "district-rankings"),
    ("13", "insights-grid"),
    ("14", "decision-memo"),
    ("15", "report-footer"),
]

FAKE_AUTH = {
    "user": {
        "id": "playwright-qa",
        "company_name": "SPOTTER QA",
        "contact_name": "Playwright",
        "email": "qa@spotter.test",
        "phone": "01000000000",
        "position": "qa",
        "store_count": "1",
        "plan": "master",
        "role": "master",
    },
    "brand": None,
    # JWT 없는 로컬 캡처용 — simulation-history 등 Bearer 요구 엔드포인트는 401로 떨어짐.
    # 필요 시 backend jwt_auth.create_access_token으로 오프라인 토큰 발급 후 여기 주입.
    "token": None,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=3000, help="Vite dev port")
    ap.add_argument(
        "--timeout", type=int, default=300, help="시뮬 결과 렌더 대기 최대 초 (기본 300)"
    )
    ap.add_argument(
        "--output",
        default=str(_DEFAULT_OUTPUT),
        help=f"PNG 저장 디렉터리 (기본: {_DEFAULT_OUTPUT})",
    )
    ap.add_argument("--headed", action="store_true", help="브라우저 창 보이기 (디버깅용)")
    ap.add_argument(
        "--skip-full", action="store_true", help="00-integrated-full.png 스킵 (용량 절감)"
    )
    args = ap.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,  # retina — 썸네일 품질 확보
        )
        # Auth localStorage는 페이지 로드 전 세팅되어야 AuthProvider 초기 렌더에 반영됨
        auth_json = json.dumps(FAKE_AUTH, ensure_ascii=False)
        context.add_init_script(
            f"window.localStorage.setItem('spotter_auth', {json.dumps(auth_json)});"
        )

        page = context.new_page()
        url = f"http://localhost:{args.port}/simulator"
        print(f"[INFO] GET {url}")
        try:
            page.goto(url, wait_until="networkidle", timeout=60_000)
        except PwTimeout:
            print("[ERR] /simulator 로드 실패 — frontend dev서버가 떠 있는지 확인")
            browser.close()
            return 2

        # RUN SIMULATION 버튼 (App.tsx:3131) 탐색 + 클릭
        print("[INFO] RUN SIMULATION 버튼 클릭")
        try:
            run_btn = page.get_by_role("button", name="RUN SIMULATION").first
            run_btn.wait_for(state="visible", timeout=30_000)
            run_btn.click()
        except Exception as e:
            print(f"[ERR] RUN SIMULATION 버튼 클릭 실패: {e}")
            err_path = out_dir / "error-no-button.png"
            page.screenshot(path=str(err_path), full_page=True)
            print(f"[DEBUG] {err_path} 저장 — 현재 화면 확인")
            browser.close()
            return 3

        # IntegratedReport 렌더 대기 — #section-01 = CommandBar
        print(f"[INFO] IntegratedReport 렌더 대기 (최대 {args.timeout}s)...")
        try:
            page.wait_for_selector("#section-01", state="visible", timeout=args.timeout * 1000)
        except PwTimeout:
            print(f"[ERR] 결과 타임아웃 ({args.timeout}s). backend 로그 확인 권장")
            err_path = out_dir / "error-timeout.png"
            page.screenshot(path=str(err_path), full_page=True)
            print(f"[DEBUG] {err_path} 저장")
            browser.close()
            return 4

        try:
            page.wait_for_selector("#section-15", state="visible", timeout=30_000)
        except PwTimeout:
            print("[WARN] #section-15 미등장 — 일부 섹션만 캡처될 수 있음")

        # Recharts/kakao 같은 lazy 렌더를 위해 천천히 스크롤해서 viewport 통과
        print("[INFO] 페이지 하단까지 슬로우 스크롤 (lazy 렌더 트리거)")
        page.evaluate(
            """
            async () => {
              const step = 400;
              const total = document.documentElement.scrollHeight;
              for (let y = 0; y < total; y += step) {
                window.scrollTo(0, y);
                await new Promise(r => setTimeout(r, 180));
              }
              window.scrollTo(0, 0);
              await new Promise(r => setTimeout(r, 500));
            }
            """
        )

        saved: list[Path] = []

        if not args.skip_full:
            full_path = out_dir / "00-integrated-full.png"
            page.screenshot(path=str(full_path), full_page=True)
            saved.append(full_path)
            print(f"[OK] {full_path.name}")

        for num, slug in SECTIONS:
            sel = f"#section-{num}"
            try:
                el = page.locator(sel)
                el.scroll_into_view_if_needed()
                page.wait_for_timeout(250)
                out_path = out_dir / f"{num}-{slug}.png"
                el.screenshot(path=str(out_path))
                saved.append(out_path)
                print(f"[OK] {out_path.name}")
            except Exception as e:
                print(f"[WARN] {sel} 캡처 실패: {e}")

        browser.close()

        print()
        print(f"✅ 완료 — {len(saved)}장 / {out_dir.resolve()}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
