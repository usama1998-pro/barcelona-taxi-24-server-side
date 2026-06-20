from __future__ import annotations

import os
from pathlib import Path


CHUNK_SIZE = 64 * 1024


def read_tail_lines(file_path: str, max_lines: int) -> list[str]:
    path = Path(file_path)
    if max_lines < 1 or not path.exists() or path.stat().st_size == 0:
        return []

    with path.open("rb") as handle:
        file_size = path.stat().st_size
        position = file_size
        leftover = b""
        collected: list[str] = []

        while position > 0 and len(collected) < max_lines:
            read_size = min(CHUNK_SIZE, position)
            position -= read_size
            handle.seek(position)
            chunk = handle.read(read_size) + leftover
            parts = chunk.splitlines(keepends=False)
            leftover = parts.pop(0) if parts else b""

            for line in reversed(parts):
                text = line.decode("utf-8", errors="replace")
                if text == "" and not collected:
                    continue
                collected.append(text)
                if len(collected) >= max_lines:
                    break

        if leftover and len(collected) < max_lines:
            collected.append(leftover.decode("utf-8", errors="replace"))

    return list(reversed(collected))
