from __future__ import annotations

import hashlib
from typing import Dict

from langgraph.graph import END

from ..cache.foundation_cache import load_foundation, save_foundation
from ..cache.incremental_cache import load_best_cached_version, save_version
from ..config import get_settings
from ..graph.state import GraphState, TokenUsage
from ..agents.foundation_validators import evaluate_foundation
from ..agents.module_supervisors import propose_module_update, score_module_update
from ..agents.global_convergence import global_convergence_review


def _merge_usage(state: GraphState, usage: Dict[str, int]) -> None:
    u = dict(state.get("token_usage") or {})
    state["token_usage"] = TokenUsage(
        input_tokens=u.get("input_tokens", 0) + usage.get("input_tokens", 0),
        output_tokens=u.get("output_tokens", 0) + usage.get("output_tokens", 0),
    )


def layer1_foundation_validation(state: GraphState) -> GraphState:
    """Layer 1: foundation sanitization and contract generation."""

    settings = get_settings()
    messages = list(state.get("messages", []))

    existing = load_foundation()
    if existing is not None:
        state["immutable_foundation"] = existing
        scores = dict(state.get("scores", {}))
        scores["foundation"] = max(settings.foundation_threshold, 0.9)
        state["scores"] = scores
        messages.append("Layer1: loaded existing immutable foundation from cache.")
        state["messages"] = messages
        return state

    contract, score, eval_messages, usage = evaluate_foundation(
        foundation_code=state.get("foundation_codebase", ""),
        user_request=state.get("user_request", ""),
    )
    _merge_usage(state, usage)
    scores = state.get("scores", {})
    scores["foundation"] = score
    state["scores"] = scores
    state["immutable_foundation"] = contract
    messages.extend(eval_messages)
    messages.append(f"Layer1: aggregated foundation score={score:.3f}")
    state["messages"] = messages

    saved = save_foundation(contract, overwrite=False)
    if saved:
        messages.append("Layer1: saved immutable foundation to cache.")
    else:
        messages.append("Layer1: foundation cache already existed; did not overwrite.")

    state["messages"] = messages
    return state


def layer2_module_generation(state: GraphState) -> GraphState:
    """Layer 2: generate or refine a module based on the foundation.
    If a high-scoring cached version exists for this request, reuse it and skip LLM.
    """

    settings = get_settings()
    foundation = state.get("immutable_foundation", {})
    user_request = state.get("user_request", "")
    module_name = "core_module"

    request_hash = hashlib.sha256(user_request.encode("utf-8")).hexdigest()
    state["latest_module_request_hash"] = request_hash

    # Short-circuit: reuse cached module for same request to save tokens.
    cached = load_best_cached_version(
        module_name=module_name,
        min_score=settings.module_threshold,
        request_hash=request_hash,
    )
    if cached is not None:
        state["latest_module_proposal"] = {
            "module": module_name,
            "content": cached.get("content", ""),
            "rationale": f"Reused from cache (v{cached.get('version')}).",
        }
        state["layer2_from_cache"] = True
        messages = list(state.get("messages", []))
        messages.append(
            f"Layer2: skipped generation, reusing cached module for '{module_name}'."
        )
        state["messages"] = messages
        return state

    state["layer2_from_cache"] = False
    proposal, usage = propose_module_update(
        module_name=module_name,
        user_request=user_request,
        foundation=foundation,
    )
    _merge_usage(state, usage)

    messages = list(state.get("messages", []))
    messages.append(f"Layer2: proposed update for {module_name}.")
    state["messages"] = messages

    state["latest_module_proposal"] = {
        "module": proposal.module_name,
        "content": proposal.content,
        "rationale": proposal.rationale,
    }
    return state


def layer2_module_validation(state: GraphState) -> GraphState:
    """Layer 2: validate the latest module proposal and update incremental cache."""

    settings = get_settings()
    foundation = state.get("immutable_foundation", {})
    proposal_data = state.get("latest_module_proposal") or {}
    module_name = proposal_data.get("module", "core_module")
    content = proposal_data.get("content", "")
    request_hash = state.get("latest_module_request_hash")

    messages = list(state.get("messages", []))

    # Short-circuit: reuse cached version (from generation or previous run).
    if state.get("layer2_from_cache"):
        cached = load_best_cached_version(
            module_name=module_name,
            min_score=settings.module_threshold,
            request_hash=request_hash,
        )
        if cached is not None:
            cached_score = float(cached.get("score", 0.0))
            scores = state.get("scores", {})
            scores["module"] = cached_score
            state["scores"] = scores
            messages.append(
                f"Layer2: reused cached module version (score={cached_score:.3f})."
            )
            state["messages"] = messages
            state["retry_count"] = int(state.get("retry_count", 0))
            return state

    cached = load_best_cached_version(
        module_name=module_name,
        min_score=settings.module_threshold,
        request_hash=request_hash,
    )
    if cached is not None:
        cached_score = float(cached.get("score", 0.0))
        scores = state.get("scores", {})
        scores["module"] = cached_score
        state["scores"] = scores
        # Restore proposal content from cache so downstream layers can use it.
        state["latest_module_proposal"] = {
            "module": module_name,
            "content": cached.get("content", ""),
            "rationale": f"Reused from incremental cache (version={cached.get('version')}).",
        }
        messages.append(
            f"Layer2: reused cached module version (score={cached_score:.3f}) "
            f"for module '{module_name}'."
        )
        state["messages"] = messages
        # No retries needed when we accept a cached version.
        state["retry_count"] = int(state.get("retry_count", 0))
        return state

    from ..agents.module_supervisors import ModuleProposal

    proposal = ModuleProposal(
        module_name=module_name,
        content=content or "",
        rationale=proposal_data.get("rationale", ""),
    )

    score, messages_from_validator, usage = score_module_update(
        proposal, foundation, user_request=state.get("user_request", "")
    )
    _merge_usage(state, usage)
    scores = state.get("scores", {})
    scores["module"] = score
    state["scores"] = scores

    messages.append(f"Layer2: module score={score:.3f}")
    messages.extend(messages_from_validator)
    state["messages"] = messages

    retry_count = int(state.get("retry_count", 0))
    if score < settings.module_threshold:
        retry_count += 1
    state["retry_count"] = retry_count

    save_version(
        module_name=module_name,
        content=proposal.content,
        score=score,
        request_hash=request_hash if isinstance(request_hash, str) else None,
    )

    return state


def layer3_global_convergence(state: GraphState) -> GraphState:
    """Layer 3: global convergence and final decision."""

    settings = get_settings()
    messages = list(state.get("messages", []))

    global_score, report, usage = global_convergence_review(state)
    _merge_usage(state, usage)
    scores = state.get("scores", {})
    scores["global_score"] = global_score
    state["scores"] = scores
    state["final_report"] = report

    messages.append(f"Layer3: global score={global_score:.3f}")
    state["messages"] = messages

    if global_score >= settings.global_threshold:
        state["status"] = "success"
        state["failure_reason"] = ""
    else:
        state["status"] = "failed"
        state["failure_reason"] = "Global convergence score below threshold."

    return state


def mark_failure(state: GraphState, reason: str) -> GraphState:
    """Helper to mark the state as failed with a reason."""

    messages = list(state.get("messages", []))
    messages.append(f"Failure: {reason}")
    state["messages"] = messages
    state["status"] = "failed"
    state["failure_reason"] = reason
    return state


def layer1_router(state: GraphState) -> str:
    """Routing function after Layer 1."""

    settings = get_settings()
    scores = state.get("scores", {})
    foundation_score = float(scores.get("foundation", 0.0))
    if foundation_score >= settings.foundation_threshold:
        return "pass"
    return "fail"


def layer2_router(state: GraphState) -> str:
    """Routing function inside Layer 2 self-correction loop."""

    settings = get_settings()
    scores = state.get("scores", {})
    module_score = float(scores.get("module", 0.0))
    retry_count = int(state.get("retry_count", 0))

    if module_score >= settings.module_threshold:
        return "to_layer3"
    if retry_count < settings.max_module_retries:
        return "retry"
    return "fail"

