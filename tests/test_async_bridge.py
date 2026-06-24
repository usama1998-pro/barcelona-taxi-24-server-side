from __future__ import annotations

import asyncio

from app.lib.async_bridge import run_coroutine_sync


async def _answer() -> int:
    await asyncio.sleep(0)
    return 42


def test_run_coroutine_sync_without_active_loop() -> None:
    assert run_coroutine_sync(_answer()) == 42


def test_run_coroutine_sync_from_running_loop() -> None:
    async def wrapped() -> int:
        return run_coroutine_sync(_answer())

    assert asyncio.run(wrapped()) == 42
