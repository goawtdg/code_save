from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from ..config import get_settings
from ..graph.state import FoundationContract
from ..llm import get_llm_client, get_validation_client


@dataclass
class EvaluationResult:
    name: str
    score: float
    reasons: List[str]


def _clip_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def _heuristic_score(text: str) -> float:
    """Very small heuristic used when backend is mock or LLM output is free-form."""

    length_bonus = min(len(text) / 1000.0, 1.0)
    keywords = ["test", "security", "validation", "contract"]
    keyword_hits = sum(1 for k in keywords if k.lower() in text.lower())
    keyword_bonus = min(keyword_hits * 0.1, 0.3)
    return _clip_score(0.6 + length_bonus * 0.2 + keyword_bonus)


def _usage(response: Any) -> Dict[str, int]:
    return {
        "input_tokens": getattr(response, "input_tokens", 0) or 0,
        "output_tokens": getattr(response, "output_tokens", 0) or 0,
    }


def _run_correctness_critic(foundation_code: str, user_request: str) -> Tuple[EvaluationResult, Dict[str, int]]:
    # 基座双模型之一：正确性评审使用主模型
    client = get_llm_client()
    prompt = (
        "You are CorrectnessCritic, reviewing a codebase used as a foundation for "
        "further code generation.\n\n"
        f"User request:\n{user_request}\n\n"
        f"Foundation snippet or description:\n{foundation_code[:4000]}\n\n"
        "Briefly assess logical soundness and completeness. Focus on obvious pitfalls.\n"
        "Respond in natural language; an external system will derive a numeric score."
    )
    response = client.generate_text(prompt)
    score = _heuristic_score(response.content)
    result = EvaluationResult(
        name="CorrectnessCritic",
        score=score,
        reasons=[response.content],
    )
    return result, _usage(response)


def _run_security_auditor(foundation_code: str, user_request: str) -> Tuple[EvaluationResult, Dict[str, int]]:
    # 基座双模型：安全审计使用验证模型（若配置），与 CorrectnessCritic 的主模型形成交叉验证
    client = get_validation_client() or get_llm_client()
    prompt = (
        "You are SecurityAuditor, scanning an initial codebase for obvious security "
        "issues such as hard-coded secrets, unsafe eval/exec, command injection, etc.\n\n"
        f"User request:\n{user_request}\n\n"
        f"Foundation snippet or description:\n{foundation_code[:4000]}\n\n"
        "List main security concerns, if any, using short bullet points. "
        "If overall risk is low, explain why."
    )
    response = client.generate_text(prompt)
    base = _heuristic_score(response.content)
    lower = response.content.lower()
    risk_hits = lower.count("vulnerability") + lower.count("vulnerabilities") + lower.count("critical")
    penalty = min(risk_hits * 0.05, 0.3)
    score = _clip_score(base - penalty)
    result = EvaluationResult(
        name="SecurityAuditor",
        score=score,
        reasons=[response.content],
    )
    return result, _usage(response)


def evaluate_foundation(
    foundation_code: str, user_request: str
) -> Tuple[FoundationContract, float, List[str], Dict[str, int]]:
    """Run Layer 1 validators and synthesize a formalized foundation contract.

    Returns:
        contract: structured description of the trusted foundation.
        aggregated_score: combined score across validators.
        messages: human-readable explanations and notes.
        usage: token usage dict with input_tokens, output_tokens.
    """
    correctness, u1 = _run_correctness_critic(foundation_code, user_request)
    security, u2 = _run_security_auditor(foundation_code, user_request)
    usage = {
        "input_tokens": u1["input_tokens"] + u2["input_tokens"],
        "output_tokens": u1["output_tokens"] + u2["output_tokens"],
    }

    scores = [correctness.score, security.score]
    aggregated = sum(scores) / len(scores)

    contract: FoundationContract = {
        "summary": "Validated foundation for safe code generation.",
        "assumptions": [
            "User request and foundation description accurately reflect the target system.",
        ],
        "safety_constraints": [
            "Avoid use of dangerous primitives (eval/exec, raw shell injection).",
            "Do not hard-code secrets or credentials.",
        ],
        "known_risks": [],
    }

    messages: List[str] = []
    for res in (correctness, security):
        messages.append(f"{res.name} score={res.score:.3f}")
        messages.extend(res.reasons)

    return contract, aggregated, messages, usage

