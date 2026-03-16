from __future__ import annotations

import os
from pathlib import Path

from safe_codegen.cache.foundation_cache import load_foundation, save_foundation
from safe_codegen.cache.incremental_cache import (
    load_incremental_cache,
    load_module_history,
    rollback,
    save_version,
)
from safe_codegen.graph.state import FoundationContract


def test_foundation_cache_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SAFE_CODEGEN_DATA_DIR", str(tmp_path))

    contract: FoundationContract = {
        "summary": "Test foundation",
        "assumptions": [],
        "safety_constraints": [],
        "known_risks": [],
    }

    saved = save_foundation(contract, overwrite=False)
    assert saved is True

    # Second save without overwrite should be ignored.
    saved_again = save_foundation(contract, overwrite=False)
    assert saved_again is False

    loaded = load_foundation()
    assert loaded is not None
    assert loaded["summary"] == "Test foundation"


def test_incremental_cache_versioning(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SAFE_CODEGEN_DATA_DIR", str(tmp_path))

    entry1 = save_version("mod_a", "print('v1')", 0.5)
    entry2 = save_version("mod_a", "print('v2')", 0.9)

    history = load_module_history("mod_a")
    assert len(history) == 2
    assert history[0]["version"] == 1
    assert history[1]["version"] == 2

    rollback_entry = rollback("mod_a", 1)
    assert rollback_entry is not None
    assert rollback_entry["content"] == "print('v1')"

    cache = load_incremental_cache()
    assert "mod_a" in cache
    assert len(cache["mod_a"]) == 2

