from __future__ import annotations

import os

from safe_codegen.graph.builder import InitialStateConfig, build_graph


def test_graph_smoke_run() -> None:
    # Ensure we use the mock backend so tests do not call external APIs.
    os.environ["SAFE_CODEGEN_BACKEND"] = "mock"

    app = build_graph()
    initial_state = InitialStateConfig(
        user_request="Create a safe, minimal HTTP API service.",
        foundation_codebase="",
    ).to_state()

    final_state = app.invoke(initial_state, config={"configurable": {"thread_id": "test-smoke"}})

    assert "status" in final_state
    assert final_state["status"] in {"success", "failed", "pending"}
    assert "scores" in final_state
    scores = final_state["scores"]
    assert 0.0 <= scores.get("foundation", 0.0) <= 1.0
    assert 0.0 <= scores.get("module", 0.0) <= 1.0
    assert 0.0 <= scores.get("global_score", 0.0) <= 1.0

