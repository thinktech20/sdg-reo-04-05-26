"""Simulate mode for the Event History Assistant.

When AGENT_SIMULATE_MODE=true the real LLM call is skipped.  Instead the
endpoint sleeps for AGENT_SIM_DELAY_SECS and returns this pre-baked event
history fixture.  The event shape should match what the frontend EventRecord
interface expects once that interface is finalised.
"""

from __future__ import annotations

import asyncio
import logging

from event_history import config
from event_history.schemas import RunRequest, RunResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pre-baked event history fixture
# ---------------------------------------------------------------------------

SIM_HISTORY_EVENTS: list[dict] = [
    {
        "id": "evt-001",
        "date": "2024-06-15",
        "eventType": "Planned Outage",
        "description": "18-month planned maintenance outage. Performed stator PD testing, rotor visual inspection, and brush gear replacement.",
        "findings": [
            "Stator PD levels measured at 1850 pC — above 800 pC threshold",
            "Rotor retaining ring visually inspected — no cracking observed",
            "Exciter brush gear replaced at 6,200 hours of service",
        ],
        "actionsTaken": "PD test completed. Brush gear replaced. Recommended quarterly PD monitoring.",
        "severity": "Routine",
        "documentRef": "FSR-2024-002",
        "technicianId": "T-4421",
    },
    {
        "id": "evt-002",
        "date": "2023-12-10",
        "eventType": "Condition Monitoring",
        "description": "Quarterly online PD monitoring. PD levels recorded at 1200 pC — approaching threshold.",
        "findings": [
            "PD levels at 1200 pC, up from 960 pC in September 2023",
        ],
        "actionsTaken": "Increased monitoring frequency to monthly. Flagged for 18-month milestone review.",
        "severity": "Advisory",
        "documentRef": "CM-2023-Q4",
        "technicianId": "T-3817",
    },
    {
        "id": "evt-003",
        "date": "2023-06-20",
        "eventType": "Condition Monitoring",
        "description": "Bi-annual PD monitoring. PD levels at 960 pC — elevated but within watch range.",
        "findings": [
            "PD levels at 960 pC, up from 600 pC in 2022",
        ],
        "actionsTaken": "Logged for trend analysis. No immediate action required.",
        "severity": "Informational",
        "documentRef": "CM-2023-Q2",
        "technicianId": "T-3817",
    },
    {
        "id": "evt-004",
        "date": "2022-06-05",
        "eventType": "Planned Outage",
        "description": "18-month planned maintenance outage. Stator and rotor visual inspection. PD baseline test.",
        "findings": [
            "PD baseline: 600 pC — within normal range",
            "Rotor winding resistance test — within spec",
            "No visual defects detected on stator or end-windings",
        ],
        "actionsTaken": "All tests within acceptable limits. Next PD monitoring in 6 months.",
        "severity": "Routine",
        "documentRef": "FSR-2022-007",
        "technicianId": "T-4421",
    },
    {
        "id": "evt-005",
        "date": "2021-08-30",
        "eventType": "Forced Outage",
        "description": "Exciter ground fault alarm triggered. Unit tripped offline for investigation.",
        "findings": [
            "Exciter brush gear worn beyond limits — contributing to ground fault",
            "No damage to exciter winding",
        ],
        "actionsTaken": "Emergency brush gear replacement. Unit returned to service after 18-hour repair.",
        "severity": "High",
        "documentRef": "FO-2021-004",
        "technicianId": "T-2990",
    },
]


async def simulate_run(request_body: RunRequest) -> RunResponse:
    """Return a pre-baked event history fixture after a realistic delay."""
    logger.info(
        "event-history SIMULATE run assessment_id=%s delay=%.1fs",
        request_body.assessment_id,
        config.AGENT_SIM_DELAY_SECS,
    )
    await asyncio.sleep(config.AGENT_SIM_DELAY_SECS)

    summary_msg = (
        f"[SIMULATE] Event history compiled for assessment "
        f"'{request_body.assessment_id}'. "
        f"{len(SIM_HISTORY_EVENTS)} events found spanning 2021–2024. "
        "Key pattern: escalating PD levels identified as primary risk driver."
    )

    return RunResponse(
        status="accepted",
        assessment_id=request_body.assessment_id,
        message=summary_msg,
        history_events=SIM_HISTORY_EVENTS,
    )
