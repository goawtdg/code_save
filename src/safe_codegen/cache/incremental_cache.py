from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..config import get_settings
from ..graph.state import IncrementalCache, ModuleVersionEntry


def _modules_dir() -> Path:
    settings = get_settings()
    base = Path(settings.data_dir)
    return base / "modules"


def _module_path(module_name: str) -> Path:
    return _modules_dir() / f"{module_name}.json"


def load_module_history(module_name: str) -> List[ModuleVersionEntry]:
    """Load full version history for a given module."""

    path = _module_path(module_name)
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [ModuleVersionEntry(**entry) for entry in data]  # type: ignore[list-item]


def save_version(
    module_name: str,
    content: str,
    score: float,
    summary: str = "",
    request_hash: str | None = None,
) -> ModuleVersionEntry:
    """Append a new version entry for a module and persist it."""

    history = load_module_history(module_name)
    version = len(history) + 1
    entry: ModuleVersionEntry = {
        "module": module_name,
        "version": version,
        "content": content,
        "score": score,
        "summary": summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_hash": request_hash,
    }

    history.append(entry)

    path = _module_path(module_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    return entry


def rollback(module_name: str, target_version: int) -> Optional[ModuleVersionEntry]:
    """Return a specific version entry for a module without mutating history.

    Higher-level code can decide how to apply the rollback (e.g. re-materialize
    that version into the working codebase).
    """

    history = load_module_history(module_name)
    for entry in history:
        if entry.get("version") == target_version:
            return entry
    return None


def load_incremental_cache() -> IncrementalCache:
    """Load all module histories into a single IncrementalCache structure."""

    modules_dir = _modules_dir()
    if not modules_dir.exists():
        return {}

    cache: IncrementalCache = {}
    for file in modules_dir.glob("*.json"):
        module_name = file.stem
        cache[module_name] = load_module_history(module_name)
    return cache


def load_best_cached_version(
    module_name: str,
    min_score: float,
    request_hash: str | None = None,
) -> Optional[ModuleVersionEntry]:
    """Return the best cached version for a module that meets the minimum score.

    If request_hash is provided, prefer entries that match it; otherwise consider
    all versions. This is used to short-circuit Layer 2 when a suitable version
    already exists, saving LLM calls and tokens.
    """
    history = load_module_history(module_name)
    best: Optional[ModuleVersionEntry] = None
    for entry in history:
        if entry.get("score", 0.0) < min_score:
            continue
        # When request_hash is set, only consider entries that match it.
        if request_hash is not None and entry.get("request_hash") != request_hash:
            continue
        if best is None or entry.get("score", 0.0) > best.get("score", 0.0):
            best = entry
    return best


