from __future__ import annotations

import os
from pathlib import Path


def app_dir() -> Path:
    override = os.environ.get("KILN_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".local" / "share" / "kiln"


def db_path() -> Path:
    return app_dir() / "kiln.db"


def log_root() -> Path:
    return app_dir() / "logs"


def lock_root() -> Path:
    return app_dir() / "locks"


def ensure_app_dirs() -> None:
    for path in (app_dir(), log_root(), lock_root()):
        path.mkdir(parents=True, exist_ok=True)
