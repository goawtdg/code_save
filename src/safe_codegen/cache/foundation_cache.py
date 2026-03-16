from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..config import get_settings
from ..graph.state import FoundationContract


def _foundation_path() -> Path:
    settings = get_settings()
    base = Path(settings.data_dir)
    return base / "foundation.json"


def load_foundation() -> Optional[FoundationContract]:
    """Load the immutable foundation contract if it exists."""

    path = _foundation_path()
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return FoundationContract(**data)  # type: ignore[arg-type]


def save_foundation(contract: FoundationContract, overwrite: bool = False) -> bool:
    """Persist the foundation contract to disk.

    If `overwrite` is False and a foundation file already exists, the function
    will return False and leave the existing file untouched (immutable-by-default).
    """

    path = _foundation_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and not overwrite:
        return False

    with path.open("w", encoding="utf-8") as f:
        json.dump(contract, f, ensure_ascii=False, indent=2)
    return True

