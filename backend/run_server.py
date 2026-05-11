"""Backend uvicorn 진입점 — Windows ProactorEventLoop 차단 wrapper.

uvicorn 의 `--reload` 모드가 worker process 를 별도로 띄우면서 자체 loop
정책을 적용하기 전에 ``WindowsSelectorEventLoopPolicy`` 를 강제 적용한다.
psycopg 3 async 가 ProactorEventLoop 와 충돌해 legal RAG specialist 가
``InterfaceError`` 로 0건 반환되는 증상 해결.

사용:
    cd backend
    python run_server.py
"""

from __future__ import annotations

import asyncio
import sys


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        # uvicorn 은 default loop="auto" → Windows 에서 asyncio default policy 사용.
        # 위에서 정책을 SelectorEventLoopPolicy 로 바꿨으므로 worker 도 그대로 사용.

    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # loop="asyncio" 명시 — uvloop fallback 차단 (Windows 무관하지만 명시).
        loop="asyncio",
    )


if __name__ == "__main__":
    main()
