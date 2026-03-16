from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, TypedDict


class FoundationContract(TypedDict, total=False):
    """Formalized description of the trusted foundation codebase."""

    summary: str
    assumptions: List[str]
    safety_constraints: List[str]
    known_risks: List[str]


class ModuleVersionEntry(TypedDict, total=False):
    """One version of a module stored in the incremental cache."""

    module: str
    version: int
    content: str
    score: float
    summary: str
    timestamp: str
    request_hash: str | None


IncrementalCache = Dict[str, List[ModuleVersionEntry]]


class Scores(TypedDict, total=False):
    foundation: float
    module: float
    global_score: float


StatusType = Literal["pending", "success", "failed"]


class TokenUsage(TypedDict, total=False):
    input_tokens: int
    output_tokens: int


class GraphState(TypedDict, total=False):
    """Main LangGraph state shared across all layers."""

    user_request: str
    foundation_codebase: str
    immutable_foundation: FoundationContract
    incremental_cache: IncrementalCache
    scores: Scores
    retry_count: int
    messages: List[str]
    final_report: str
    status: StatusType
    failure_reason: str
    token_usage: TokenUsage
    latest_module_request_hash: str
    layer2_from_cache: bool


@dataclass
class InitialStateConfig:
    """Helper for constructing an initial GraphState."""

    user_request: str
    foundation_codebase: str = ""
    retry_count: int = 0

    def to_state(self) -> GraphState:
        return GraphState(
            user_request=self.user_request,
            foundation_codebase=self.foundation_codebase,
            immutable_foundation=FoundationContract(
                summary="",
                assumptions=[],
                safety_constraints=[],
                known_risks=[],
            ),
            incremental_cache={},
            scores=Scores(
                foundation=0.0,
                module=0.0,
                global_score=0.0,
            ),
            retry_count=self.retry_count,
            messages=[],
            final_report="",
            status="pending",
            failure_reason="",
            token_usage=TokenUsage(input_tokens=0, output_tokens=0),
        )

