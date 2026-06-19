"""Optional migrate before app start. Run: python -m scripts.maybe_migrate_deploy"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from scripts._bootstrap import ROOT, bootstrap


def main() -> int:
    bootstrap()
    raw = (os.getenv("ALEMBIC_MIGRATE_ON_START") or "").strip().lower()
    enabled = raw in {"1", "true", "yes", "on"}
    if not enabled:
        return 0

    alembic_ini = ROOT / "alembic.ini"
    if not alembic_ini.is_file():
        print(f"Alembic config not found at {alembic_ini}")
        return 1

    print("ALEMBIC_MIGRATE_ON_START enabled — running alembic upgrade head…")
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env=os.environ.copy(),
            check=True,
        )
    except subprocess.CalledProcessError:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
