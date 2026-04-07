"""LangGraph pipeline state definition."""

from __future__ import annotations

from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):
    """Mutable state threaded through every LangGraph node.

    Fields are updated incrementally as each node completes.
    `total=False` allows partial updates without KeyError.
    """

    # Inputs -- set once at graph entry; nodes treat as read-only
    assessment_id: str
    job_type: str     # "run" | "narrative"
    esn: str
    persona: str
    input_payload: dict[str, Any]

    # Per-node results -- written by each node, read by finalize
    risk_eval_result: dict[str, Any]
    narrative_result: dict[str, Any]
    event_history_result: dict[str, Any]

    # Final aggregated output -- written by finalize_node, read by the HTTP handler
    final_result: dict[str, Any]

    # Control
    current_stage: str  # tracks which node is active (for status polling)
    error: str | None  # set on any unhandled exception; triggers FAILED path
