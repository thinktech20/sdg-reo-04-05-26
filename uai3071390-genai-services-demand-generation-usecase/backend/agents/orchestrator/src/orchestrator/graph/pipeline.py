"""Build and compile the LangGraph pipeline.

Graph topology (job_type-routed):

    START
      ↓
    [conditional by job_type]
        ├── job_type="run", persona=RE  → risk_eval → finalize → END
      ├── job_type="run", persona=OE  → risk_eval → event_history → finalize → END
      └── job_type="narrative"        → narrative → finalize → END

The two invocations are always separate HTTP calls:
  1. POST /analyze/run       — triggers A1 (+ A3 for OE)
  2. POST /analyze/narrative — triggers A2, ONLY after user submits feedback

Checkpointer:
    Skeleton uses MemorySaver (in-process only -- intended for local dev and tests).
    Production: replace with DynamoDB-backed AsyncSqliteSaver or the Foundation
    Services checkpointer bridge (no direct boto3 DynamoDB calls).
    Integration point is clearly marked below.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver  # noqa: PLC0415
from langgraph.graph import END, START, StateGraph  # noqa: PLC0415

import orchestrator.config as config
from orchestrator.graph.nodes import (
    event_history_node,
    finalize_node,
    narrative_node,
    risk_eval_node,
)
from orchestrator.graph.state import PipelineState


def _first_node(state: PipelineState) -> str:
    """Route START to the correct entry node based on job_type."""
    return "narrative" if state.get("job_type") == "narrative" else "risk_eval"


def _after_risk_eval(state: PipelineState) -> str:
    """After A1 completes: RE finalizes; OE continues to event_history (A3)."""
    persona = str(state.get("persona", "RE")).upper()
    return "event_history" if persona == "OE" else "finalize"

logger = logging.getLogger(__name__)


def build_pipeline() -> Any:
    """Compile and return the LangGraph pipeline.

    Returns a `CompiledGraph` instance ready for `ainvoke()` / `invoke()`.
    Called once at application startup and stored in `app.state.graph`.
    """
    logger.info("orchestrator: building LangGraph routed pipeline")

    graph = StateGraph(PipelineState)

    # Register nodes
    graph.add_node("risk_eval", risk_eval_node)
    graph.add_node("narrative", narrative_node)
    graph.add_node("event_history", event_history_node)
    graph.add_node("finalize", finalize_node)

    # Routed topology
    graph.add_conditional_edges(START, _first_node, {"risk_eval": "risk_eval", "narrative": "narrative"})
    graph.add_conditional_edges("risk_eval", _after_risk_eval, {"event_history": "event_history", "finalize": "finalize"})
    graph.add_edge("event_history", "finalize")
    graph.add_edge("narrative", "finalize")
    graph.add_edge("finalize", END)

    # Checkpointer: MemorySaver for local dev; DynamoDB-backed for production.
    # Set ORCHESTRATOR_CHECKPOINTER_TYPE=dynamodb + install langgraph-checkpoint-dynamodb
    # to use DynamoDB in ECS. Requires LanggraphCheckpointerTable to exist in DynamoDB.
    if config.ORCHESTRATOR_CHECKPOINTER_TYPE == "dynamodb":
        try:
            from langgraph.checkpoint.dynamodb.aio import AsyncDynamoDBSaver  # type: ignore[import]  # noqa: PLC0415

            checkpointer_kwargs: dict[str, Any] = {
                "table_name": config.LANGGRAPH_CHECKPOINTER_TABLE,
                "region_name": config.AWS_REGION,
            }
            if config.DYNAMODB_ENDPOINT_URL:
                checkpointer_kwargs["endpoint_url"] = config.DYNAMODB_ENDPOINT_URL
            checkpointer = AsyncDynamoDBSaver(**checkpointer_kwargs)
            logger.info("orchestrator: using DynamoDB checkpointer table=%s", config.LANGGRAPH_CHECKPOINTER_TABLE)
        except ImportError:
            logger.warning(
                "orchestrator: ORCHESTRATOR_CHECKPOINTER_TYPE=dynamodb but "
                "langgraph-checkpoint-dynamodb is not installed — falling back to MemorySaver. "
                "Add langgraph-checkpoint-dynamodb to pyproject.toml to enable."
            )
            checkpointer = MemorySaver()
    else:
        checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)
