"""Simulate mode for the Narrative Summary Assistant.

When AGENT_SIMULATE_MODE=true the real LLM call is skipped.  Instead the
endpoint sleeps for AGENT_SIM_DELAY_SECS and returns this pre-baked narrative
fixture, mirroring the SAMPLE_GENERATOR_NARRATIVE from the frontend mock data.
"""

from __future__ import annotations

import asyncio
import logging

from narrative_summary import config
from narrative_summary.schemas import RunRequest, RunResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pre-baked narrative text fixture
# ---------------------------------------------------------------------------

SIM_NARRATIVE = """\
RELIABILITY ASSESSMENT SUMMARY
================================

Unit assessed for the 18-month milestone review.

KEY FINDINGS:
The analysis identified 1 high-risk condition, 1 medium-risk condition, and \
2 data-needed conditions across 3 risk categories.

High priority finding: Partial Discharge (PD) Levels — PD levels at 1850 pC, \
exceeding the 800 pC threshold and trending upward from 600 pC in 2023. This \
indicates progressive insulation degradation warranting an accelerated monitoring \
schedule and a rewind feasibility assessment if levels exceed 1200 pC.

Medium priority finding: Unit Age — At 26 years the stator exceeds the 25-year \
age threshold per GEK-103542 Section 3.1, increasing statistical probability of \
insulation degradation.

RISK CATEGORY SUMMARY:
• Stator Rewind Risk: Overall risk is MEDIUM. 1 high-risk and 1 medium-risk \
finding. DC leakage remains within acceptable limits; PD levels require enhanced \
monitoring. RTD temperature data not available — recommend obtaining before next \
milestone.
• Rotor Rewind Risk: Overall risk is LIGHT. Rotor age (26 years) is below the \
30-year threshold. No field ground test data available — recommend testing during \
next planned outage.
• Exciter Rewind Risk: Overall risk is LIGHT. Brush hours (6,200) are within \
the 8,000-hour service interval. Schedule inspection at next 18-month milestone.

RECOMMENDATIONS:
1. Increase PD monitoring frequency to quarterly intervals.
2. Obtain RTD stator bar temperature history from site operations.
3. Schedule field ground resistance test during next planned outage.
4. Commission formal stator rewind feasibility study if PD levels exceed 1200 pC.
5. Review FSR-2024-002 data with site reliability team prior to next milestone.

DATA GAPS:
• Stator bar RTD temperature data (data-needed)
• Rotor field ground resistance test results (data-needed)

OVERALL RISK ASSESSMENT: MEDIUM — Recommend proactive action on high-priority \
PD finding before next planned outage window.
"""


async def simulate_run(request_body: RunRequest) -> RunResponse:
    """Return a pre-baked narrative summary fixture after a realistic delay."""
    logger.info(
        "narrative SIMULATE run assessment_id=%s delay=%.1fs",
        request_body.assessment_id,
        config.AGENT_SIM_DELAY_SECS,
    )
    await asyncio.sleep(config.AGENT_SIM_DELAY_SECS)

    return RunResponse(
        status="accepted",
        assessment_id=request_body.assessment_id,
        message=f"[SIMULATE] Narrative summary generated for '{request_body.assessment_id}'.",
        narrative_summary=SIM_NARRATIVE,
    )
