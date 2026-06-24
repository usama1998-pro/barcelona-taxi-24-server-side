from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Coroutine
from typing import TypeVar

T = TypeVar("T")


def run_coroutine_sync(coro: Coroutine[object, object, T], *, timeout: float = 120) -> T:
    """
    Run an async coroutine from sync code.

    Uses asyncio.run when no loop is active (CLI scripts). When called from a
    running loop (e.g. FastAPI async route → sync service), runs the coroutine
    in a worker thread so asyncio.run is not nested.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result(timeout=timeout)
