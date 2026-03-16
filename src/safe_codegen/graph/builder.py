from __future__ import annotations

from typing import Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from ..config import Settings, get_settings
from .state import GraphState, InitialStateConfig
from .nodes import (
    layer1_foundation_validation,
    layer1_router,
    layer2_module_generation,
    layer2_module_validation,
    layer2_router,
    layer3_global_convergence,
    mark_failure,
)


def build_graph(settings: Optional[Settings] = None, mode: str = "full"):
    """Build and compile the three-layer LangGraph workflow.

    Args:
        settings: Optional settings override.
        mode: "full" runs all three layers (L1/L2/L3). "light" runs L1/L2 但直接在
            L2 通过后结束，不进入 L3，用于中间迭代轮的轻量模式。
    """

    cfg = settings or get_settings()

    if mode not in {"full", "light"}:
        raise ValueError(f"Unsupported graph mode: {mode!r}")

    workflow = StateGraph(GraphState)

    # Register nodes
    workflow.add_node("layer1", layer1_foundation_validation)
    workflow.add_node("layer2_generate", layer2_module_generation)
    workflow.add_node("layer2_validate", layer2_module_validation)
    if mode == "full":
        workflow.add_node("layer3", layer3_global_convergence)

    def _fail_foundation(state: GraphState) -> GraphState:
        return mark_failure(state, "Foundation score below threshold.")

    def _fail_module(state: GraphState) -> GraphState:
        return mark_failure(state, "Module score did not reach threshold after retries.")

    workflow.add_node("fail_foundation", _fail_foundation)
    workflow.add_node("fail_module", _fail_module)

    # Entry point: start at Layer 1.
    workflow.set_entry_point("layer1")

    # From Layer 1 -> Layer 2 or fail.
    workflow.add_conditional_edges(
        "layer1",
        layer1_router,
        {
            "pass": "layer2_generate",
            "fail": "fail_foundation",
        },
    )

    # Layer 2 self-correction loop.
    workflow.add_edge("layer2_generate", "layer2_validate")
    if mode == "full":
        workflow.add_conditional_edges(
            "layer2_validate",
            layer2_router,
            {
                "to_layer3": "layer3",
                "retry": "layer2_generate",
                "fail": "fail_module",
            },
        )
        # After Layer 3, terminate.
        workflow.add_edge("layer3", END)
    else:
        # Light mode: L2 达标后直接结束，不进入 L3 全局收敛/验收。
        workflow.add_conditional_edges(
            "layer2_validate",
            layer2_router,
            {
                "to_layer3": END,
                "retry": "layer2_generate",
                "fail": "fail_module",
            },
        )

    workflow.add_edge("fail_foundation", END)
    workflow.add_edge("fail_module", END)

    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app


__all__ = ["build_graph", "GraphState", "InitialStateConfig"]

