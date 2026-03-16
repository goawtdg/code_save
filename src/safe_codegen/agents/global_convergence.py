from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..graph.state import GraphState
from ..llm import get_llm_client, get_validation_client


def _collect_summary_from_state(state: GraphState) -> str:
    lines: List[str] = []
    lines.append(f"User request (intent to preserve): {state.get('user_request', '')}")
    scores = state.get("scores", {})
    lines.append(f"Foundation score: {scores.get('foundation', 0.0):.3f}")
    lines.append(f"Module score: {scores.get('module', 0.0):.3f}")
    lines.append(f"Global score (previous): {scores.get('global_score', 0.0):.3f}")
    lines.append(f"Retry count: {state.get('retry_count', 0)}")
    lines.append(f"Messages count: {len(state.get('messages', []))}")
    return "\n".join(lines)


def _usage(response: Any) -> Dict[str, int]:
    return {
        "input_tokens": getattr(response, "input_tokens", 0) or 0,
        "output_tokens": getattr(response, "output_tokens", 0) or 0,
    }


def _acceptance_prompt(summary: str, use_validation_as_primary: bool) -> str:
    """Build Layer 3 prompt; when validation is primary, emphasize 完整性、可用性、安全合规、语义不偏移."""
    base = (
        "You are GlobalConvergence, a senior engineer performing a final review of a "
        "multi-layer code generation pipeline. Two goals: semantic alignment with user intent (no drift), and efficient token use.\n\n"
        "High-level metrics and signals:\n"
        f"{summary}\n\n"
    )
    if use_validation_as_primary:
        base += (
            "As the final acceptance authority, assess and report on:\n"
            "- 语义不偏移 (Semantic alignment): Does the outcome match the user request without scope creep or intent drift?\n"
            "- 完整性 (Completeness): Are all required components and behaviors covered?\n"
            "- 可用性 (Usability): Is the outcome fit for use and maintainable?\n"
            "- 安全合规 (Security & Compliance): Any security risks or policy violations?\n"
            "Provide a short narrative and key recommendations. Your score will decide acceptance."
        )
    else:
        base += (
            "Given these signals, provide:\n"
            "- Semantic alignment: does the outcome match the user request without intent drift?\n"
            "- A short narrative assessment of overall consistency and safety.\n"
            "- Key recommendations or follow-up checks.\n"
            "Your response will be used as the final human-readable report."
        )
    return base


def global_convergence_review(state: GraphState) -> Tuple[float, str, Dict[str, int]]:
    """Layer 3: 最后验收由验证模型（若配置）负责完整性、可用性、安全合规；否则由主模型完成。

    Returns:
        global_score: float in [0, 1]
        final_report: human-readable report text
        usage: token usage dict
    """
    main_client = get_llm_client()
    validation_client = get_validation_client()
    summary = _collect_summary_from_state(state)
    use_validation_primary = validation_client is not None

    prompt_primary = _acceptance_prompt(summary, use_validation_primary)

    if use_validation_primary:
        # 最后验收：由另一个模型（验证后端）做主审，负责完整性、可用性、安全合规
        response = validation_client.generate_text(prompt_primary)
        usage = _usage(response)
        # 可选：主模型做交叉校验，取更保守的分数
        main_response = main_client.generate_text(_acceptance_prompt(summary, False))
        usage["input_tokens"] += _usage(main_response)["input_tokens"]
        usage["output_tokens"] += _usage(main_response)["output_tokens"]
        response_content = response.content
        scores = state.get("scores", {})
        foundation = float(scores.get("foundation", 0.0))
        module = float(scores.get("module", 0.0))
        prior_global = float(scores.get("global_score", 0.0))
        base = 0.5 * foundation + 0.3 * module + 0.2 * prior_global
        depth_bonus = min(len(response.content) / 2000.0, 0.2)
        global_score = max(0.0, min(1.0, base + depth_bonus))
        main_base = 0.5 * foundation + 0.3 * module + 0.2 * prior_global
        main_depth = min(len(main_response.content) / 2000.0, 0.2)
        main_score = max(0.0, min(1.0, main_base + main_depth))
        global_score = min(global_score, main_score)
        response_content += f"\n\n[主模型交叉校验 score={main_score:.3f}]"
    else:
        response = main_client.generate_text(prompt_primary)
        usage = _usage(response)
        response_content = response.content
        scores = state.get("scores", {})
        foundation = float(scores.get("foundation", 0.0))
        module = float(scores.get("module", 0.0))
        prior_global = float(scores.get("global_score", 0.0))
        base = 0.5 * foundation + 0.3 * module + 0.2 * prior_global
        depth_bonus = min(len(response.content) / 2000.0, 0.2)
        global_score = max(0.0, min(1.0, base + depth_bonus))

    return global_score, response_content, usage

