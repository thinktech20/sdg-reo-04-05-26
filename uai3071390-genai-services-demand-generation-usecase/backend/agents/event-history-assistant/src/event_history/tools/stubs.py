"""Tool stubs for the Event History Assistant (A3).

Docstrings serve as tool descriptions sent to the LLM by Strands.
Replace stub returns with real Data Service calls in a later step.
"""

from __future__ import annotations

from strands import tool


@tool
def query_event_history(serial_number: str) -> str:
    """Retrieve the full operational event history for an asset.

    Returns a chronological list of all recorded operational events including
    outages, maintenance activities, inspections, and incidents.

    Args:
        serial_number: Asset serial number (ESN) to retrieve event history for.
    """
    return f"[STUB] Event history for {serial_number}: {{events: [], total: 0, date_range: null}}"


@tool
def filter_events_by_type(serial_number: str, event_type: str) -> str:
    """Filter event history by event type for a given asset.

    Returns only events matching the specified type, useful for analysing
    patterns in specific event categories (e.g. Unplanned Outages only).

    Args:
        serial_number: Asset serial number (ESN).
        event_type: Event category — 'Unplanned Outage', 'Planned Maintenance',
                    'Inspection', 'Incident', or 'Near-Miss'.
    """
    return f"[STUB] {event_type} events for {serial_number}: {{events: [], count: 0}}"


@tool
def filter_events_by_severity(serial_number: str, severity: str) -> str:
    """Filter event history by severity level for a given asset.

    Returns events at or above the specified severity, enabling focus on
    high-impact events relevant to the current risk assessment.

    Args:
        serial_number: Asset serial number (ESN).
        severity: Minimum severity level — 'Critical', 'High', 'Medium', or 'Low'.
    """
    return f"[STUB] Events with severity >= {severity} for {serial_number}: {{events: [], count: 0}}"


@tool
def get_event_timeline(serial_number: str, from_date: str, to_date: str) -> str:
    """Retrieve a time-bounded event timeline for an asset.

    Returns all events between the specified dates, formatted as a
    chronological timeline suitable for trend analysis.

    Args:
        serial_number: Asset serial number (ESN).
        from_date: Start date in ISO 8601 format (YYYY-MM-DD).
        to_date: End date in ISO 8601 format (YYYY-MM-DD).
    """
    return (
        f"[STUB] Event timeline for {serial_number} from {from_date} to {to_date}: "
        "{{timeline: [], total_events: 0}}"
    )


@tool
def count_events_by_type(serial_number: str) -> str:
    """Count events grouped by type for an asset — useful for pattern analysis.

    Returns a summary breakdown of event counts per category, helping identify
    the most frequent event types over the asset's operational history.

    Args:
        serial_number: Asset serial number (ESN).
    """
    return f"[STUB] Event counts by type for {serial_number}: {{Unplanned Outage: 0, Planned Maintenance: 0, Inspection: 0, Incident: 0}}"


# Exported list for the agent
EVENT_HISTORY_TOOLS = [
    query_event_history,
    filter_events_by_type,
    filter_events_by_severity,
    get_event_timeline,
    count_events_by_type,
]
