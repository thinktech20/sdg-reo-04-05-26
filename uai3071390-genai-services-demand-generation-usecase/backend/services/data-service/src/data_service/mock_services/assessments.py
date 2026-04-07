"""
Mock Assessment Data
Provides sample risk assessments with reliability and outage analyses
"""

import os
import uuid
from datetime import datetime
from typing import Any

from data_service.db import event_history as event_history_store
from data_service.db import narrative_summary as narrative_summary_store
from data_service.db import risk_analysis as risk_analysis_store

# In-memory assessments storage
MOCK_ASSESSMENTS: dict[str, dict[str, Any]] = {}
SAMPLE_ASSESSMENTS = {
    "asmt_001": {
        "id": "asmt_001",
        "esn": "GT12345",
        "unitNumber": "train-001",
        "component": "Traction Motor",
        "milestone": "6000 Hours",
        "createdBy": "user_001",
        "createdByName": "John Doe",
        "createdAt": "2026-02-18T10:30:00Z",
        "updatedAt": "2026-02-18T14:45:00Z",
        "status": "Completed",
        "workflowStatus": "COMPLETED",
        "reliability": {
            "riskLevel": "Medium",
            "overallScore": 72,
            "riskCategories": [
                {
                    "id": "finding_001",
                    "Issue name": "Component Degradation",
                    "Component and Issue Grouping": "Traction Motor - Component Degradation",
                    "Condition": "Traction motor shows signs of bearing wear. Operating temperature elevated by 8% over baseline.",
                    "Threshold": "Baseline +5%",
                    "Actual Value": "Baseline +8%",
                    "Risk": "Medium",
                    "Evidence": "[FSR-2026-010] Operating temperature elevated by 8% over Q3 baseline readings.",
                    "Citation": "FSR-2026-010, p.4",
                    "justification": "Operating temperature is above the expected threshold and indicates degradation that should be addressed during planned maintenance.",
                    "Ambiguity handling": "No ambiguity identified in the available mock evidence.",
                    "_meta": {
                        "esn": "GT12345",
                        "component_type": "Traction Motor",
                        "data_types": "Historical FSR Reports, Real-time Monitoring",
                        "date_window": "2026-02-18 to 2026-02-18",
                    },
                },
                {
                    "id": "finding_002",
                    "Issue name": "Historical Trends",
                    "Component and Issue Grouping": "Traction Motor - Historical Trends",
                    "Condition": "Similar equipment in the same model and age range shows a 12% increase in failures after 8000 operating hours.",
                    "Threshold": "Failure rate below 10% increase",
                    "Actual Value": "12% increase after 8000 hours",
                    "Risk": "Light",
                    "Evidence": "[ER-2025-018] Fleet-wide data shows a 12% increase in traction motor failures at 8000+ operating hours.",
                    "Citation": "ER-2025-018, p.7",
                    "justification": "Historical trend data indicates elevated fleet risk, but the current unit evidence does not support a higher than light severity on its own.",
                    "Ambiguity handling": "Trend data is fleet-level rather than unit-specific; treat as contextual evidence.",
                    "_meta": {
                        "esn": "GT12345",
                        "component_type": "Traction Motor",
                        "data_types": "Fleet-wide Analytics",
                        "date_window": "2026-02-18 to 2026-02-18",
                    },
                },
                {
                    "id": "finding_003",
                    "Issue name": "Flux Probe Review",
                    "Component and Issue Grouping": "Traction Motor Rotor - Flux Probe",
                    "Condition": "Flux probe trend is intermittent, with two recent runs showing uneven pole signal amplitude on the DE side.",
                    "Threshold": "Consistent pole balance within +/-3% variance",
                    "Actual Value": "Pole variance measured at 6% on 2 of the last 5 runs",
                    "Risk": "Light",
                    "Evidence": "[TEST-2026-014] Flux probe traces show repeatable DE-side variation above normal balance band.",
                    "Citation": "TEST-2026-014, waveform set B",
                    "justification": "The deviation is measurable but not yet severe enough to indicate immediate action. Continued monitoring is warranted because the trend is directionally unfavorable.",
                    "Ambiguity handling": "Probe placement history is incomplete; interpret the result as trending evidence rather than a stand-alone defect confirmation.",
                    "_meta": {
                        "esn": "GT12345",
                        "component_type": "Traction Motor",
                        "data_types": "Diagnostic Test Results, Historical FSR Reports",
                        "date_window": "2026-02-18 to 2026-02-18",
                    },
                },
                {
                    "id": "finding_004",
                    "Issue name": "Rotor Vibration Trend",
                    "Component and Issue Grouping": "Traction Motor Rotor - Vibration",
                    "Condition": "Rotor vibration has increased gradually across the last three inspections and is now above the fleet median.",
                    "Threshold": "Fleet median +10%",
                    "Actual Value": "Fleet median +14%",
                    "Risk": "Medium",
                    "Evidence": "[ER-2026-022] Rotor vibration trend increased from 2.8 mm/s to 3.5 mm/s over the last three service intervals.",
                    "Citation": "ER-2026-022; Condition Monitoring Trend 18",
                    "justification": "The trend exceeds the expected operational band and aligns with early-stage degradation behavior, but the measured level does not yet support a heavy risk classification.",
                    "Ambiguity handling": "Trend is based on a limited sample window; confirm against the next scheduled inspection before escalating severity.",
                    "_meta": {
                        "esn": "GT12345",
                        "component_type": "Traction Motor",
                        "data_types": "Condition Monitoring, Fleet-wide Analytics",
                        "date_window": "2026-02-18 to 2026-02-18",
                    },
                },
                {
                    "id": "finding_005",
                    "Issue name": "End Winding Support Blocking",
                    "Component and Issue Grouping": "Traction Motor Stator - End Winding Support",
                    "Condition": "Support blocking near the upper end winding appears displaced with localized dusting and mechanical looseness.",
                    "Threshold": "No visible displacement or looseness in support blocking",
                    "Actual Value": "Visible displacement and localized looseness at one upper support location",
                    "Risk": "Heavy",
                    "Evidence": "[FSR-2026-012] Technician noted displaced end-winding blocking with accompanying dust pattern near support clamp.",
                    "Citation": "FSR-2026-012, photo refs 8-10",
                    "justification": "Mechanical support degradation in the end winding region can accelerate insulation wear and lead to a more significant failure mode if not corrected during the next outage.",
                    "Ambiguity handling": "Visual confirmation is strong, but exact displacement magnitude is not recorded; recommend maintenance verification before restart-to-failure assumptions.",
                    "_meta": {
                        "esn": "GT12345",
                        "component_type": "Traction Motor",
                        "data_types": "Field Service Report, Visual Inspection",
                        "date_window": "2026-02-18 to 2026-02-18",
                    },
                },
                {
                    "id": "finding_006",
                    "Issue name": "DC Leakage Check",
                    "Component and Issue Grouping": "Traction Motor Stator - DC Leakage",
                    "Condition": "Insulation leakage measurement was slightly elevated compared with the previous maintenance interval.",
                    "Threshold": "Leakage trend stable relative to prior interval",
                    "Actual Value": "Leakage increased by 9% compared with prior interval",
                    "Risk": "Light",
                    "Evidence": "[TEST-2026-019] DC leakage values remain acceptable but have drifted upward versus the last baseline set.",
                    "Citation": "TEST-2026-019, sheet 2",
                    "justification": "The movement is notable but remains within acceptable operating range. It should be retained as a watch item rather than treated as an immediate reliability threat.",
                    "Ambiguity handling": "Environmental conditions during test were not fully normalized; compare against the next controlled test set.",
                    "_meta": {
                        "esn": "GT12345",
                        "component_type": "Traction Motor",
                        "data_types": "Electrical Test Results",
                        "date_window": "2026-02-18 to 2026-02-18",
                    },
                },
                {
                    "id": "finding_007",
                    "Issue name": "Connection Ring Dusting",
                    "Component and Issue Grouping": "Traction Motor Stator - Connection Ring",
                    "Condition": "Fine brown dusting was observed around the connection ring area with no confirmed thermal distress.",
                    "Threshold": "No dusting or residue accumulation around connection ring",
                    "Actual Value": "Localized dusting present around one quadrant of the connection ring",
                    "Risk": "Medium",
                    "Evidence": "[FSR-2026-015] Dusting observed near connection ring support hardware during borescope inspection.",
                    "Citation": "FSR-2026-015, section 3.2",
                    "justification": "Dusting in the connection ring area suggests developing mechanical or electrical wear. The current evidence supports intervention planning but not emergency action.",
                    "Ambiguity handling": "No lab residue analysis was performed, so the dust source is inferred from location and appearance only.",
                    "_meta": {
                        "esn": "GT12345",
                        "component_type": "Traction Motor",
                        "data_types": "Borescope Inspection, Field Service Report",
                        "date_window": "2026-02-18 to 2026-02-18",
                    },
                },
                {
                    "id": "finding_008",
                    "Issue name": "Oil Ingress Review",
                    "Component and Issue Grouping": "Traction Motor Stator - Oil Ingress",
                    "Condition": "Minor oil residue was observed at the lower housing edge, but no widespread contamination pattern is present.",
                    "Threshold": "No oil residue within stator housing or drain path",
                    "Actual Value": "Trace residue at lower housing edge only",
                    "Risk": "Light",
                    "Evidence": "[FSR-2026-017] Small amount of oil staining noted near lower housing edge; internal surfaces otherwise dry.",
                    "Citation": "FSR-2026-017, note 11",
                    "justification": "The observed residue is limited in scope and does not yet indicate broad insulation exposure. It should be corrected opportunistically and rechecked at the next inspection.",
                    "Ambiguity handling": "Source of oil residue is inferred and not chemically confirmed; severity remains conservative.",
                    "_meta": {
                        "esn": "GT12345",
                        "component_type": "Traction Motor",
                        "data_types": "Field Service Report, Maintenance Inspection",
                        "date_window": "2026-02-18 to 2026-02-18",
                    },
                },
                {
                    "id": "finding_009",
                    "Issue name": "Slot Wedge Tightness",
                    "Component and Issue Grouping": "Traction Motor Stator - Slot Wedge Tightness",
                    "Condition": "Tap test indicates two slot wedge locations with reduced tightness relative to the rest of the winding pack.",
                    "Threshold": "Uniform acceptable response across all tested slot wedge positions",
                    "Actual Value": "2 of 16 checked positions showed reduced tightness response",
                    "Risk": "Medium",
                    "Evidence": "[TEST-2026-021] Slot wedge tap test identified two marginal positions in the upper quadrant.",
                    "Citation": "TEST-2026-021, appendix A",
                    "justification": "Localized wedge looseness can contribute to winding movement under load. The issue is not system-wide, but it is significant enough to prioritize in maintenance planning.",
                    "Ambiguity handling": "Only a subset of positions was tested during this outage; broader coverage may refine the risk level.",
                    "_meta": {
                        "esn": "GT12345",
                        "component_type": "Traction Motor",
                        "data_types": "Mechanical Test Results",
                        "date_window": "2026-02-18 to 2026-02-18",
                    },
                },
                {
                    "id": "finding_010",
                    "Issue name": "Foreign Object Damage Screening",
                    "Component and Issue Grouping": "Traction Motor General - Foreign Object Damage",
                    "Condition": "No confirmed foreign object damage was found, but one historic service note referenced debris retrieval during prior maintenance.",
                    "Threshold": "No historical or current evidence of foreign object intrusion",
                    "Actual Value": "Historic note only; no current damage observed",
                    "Risk": "Not Mentioned",
                    "Evidence": "[ER-2024-033] Prior maintenance record references small debris retrieval; current inspection did not confirm any active damage.",
                    "Citation": "ER-2024-033; FSR-2026-018",
                    "justification": "The current inspection does not support an active FOD condition. The historic note is retained for traceability but should not drive severity without corroborating present evidence.",
                    "Ambiguity handling": "Historic evidence exists without current confirmation, so the finding is recorded as context rather than as a scored defect.",
                    "_meta": {
                        "esn": "GT12345",
                        "component_type": "Traction Motor",
                        "data_types": "Event Records, Field Service Report",
                        "date_window": "2026-02-18 to 2026-02-18",
                    },
                },
            ],
            "summary": (
                "Simulated risk-eval output saved for ESN GT12345 using component 'Traction Motor', "
                "data types 'Historical FSR Reports, Real-time Monitoring', and date window 2026-02-18 to 2026-02-18."
            ),
            "metrics": {
                "mtbf": 4250,  # Mean Time Between Failures (hours)
                "reliability": 0.92,
                "availability": 0.95,
                "failureRate": 0.00023,
            },
        },
        "outage": {
            "riskLevel": "Low",
            "estimatedDuration": "4-6 hours",
            "estimatedCost": 8500,
            "scope": [
                {
                    "id": "scope_001",
                    "task": "Bearing Inspection & Replacement",
                    "duration": "3 hours",
                    "cost": 4500,
                    "criticality": "High",
                },
                {
                    "id": "scope_002",
                    "task": "Motor Testing & Calibration",
                    "duration": "2 hours",
                    "cost": 2000,
                    "criticality": "Medium",
                },
                {
                    "id": "scope_003",
                    "task": "Documentation & System Update",
                    "duration": "1 hour",
                    "cost": 2000,
                    "criticality": "Low",
                },
            ],
            "schedulingRecommendation": "Schedule during next planned maintenance window (Week of March 15, 2026)",
            "impactAnalysis": {
                "serviceImpact": "Low - Can be performed during regular maintenance",
                "safetyImpact": "None - No safety concerns",
                "operationalImpact": "Minimal - Part availability confirmed",
            },
        },
        "feedback": [
            {
                "userId": "user_001",
                "userName": "Demo User",
                "findingId": "finding_001",
                "feedback": "down",
                "feedbackType": "correct",
                "rating": 4,
                "comments": "Ground truth severity is higher than the model output.",
                "helpful": False,
            },
            {
                "userId": "user_001",
                "userName": "Demo User",
                "findingId": "finding_002",
                "feedback": "up",
                "feedbackType": "correct",
                "rating": 1,
                "comments": "Historical trend call looks aligned with the supporting evidence.",
                "helpful": True,
            },
            {
                "userId": "user_001",
                "userName": "Demo User",
                "findingId": "finding_003",
                "feedback": "up",
                "feedbackType": "correct",
                "rating": 1,
                "comments": "Flux probe trend is appropriately treated as a watch item.",
                "helpful": True,
            },
            {
                "userId": "user_001",
                "userName": "Demo User",
                "findingId": "finding_004",
                "feedback": "down",
                "feedbackType": "correct",
                "rating": 2,
                "comments": "Rotor vibration should likely stay Light until another inspection confirms the trend.",
                "helpful": False,
            },
            {
                "userId": "user_001",
                "userName": "Demo User",
                "findingId": "finding_005",
                "feedback": "up",
                "feedbackType": "correct",
                "rating": 1,
                "comments": "Heavy classification is justified by the visible support displacement.",
                "helpful": True,
            },
            {
                "userId": "user_001",
                "userName": "Demo User",
                "findingId": "finding_006",
                "feedback": "up",
                "feedbackType": "correct",
                "rating": 1,
                "comments": "DC leakage drift is minor and looks correctly classified.",
                "helpful": True,
            },
            {
                "userId": "user_001",
                "userName": "Demo User",
                "findingId": "finding_007",
                "feedback": "down",
                "feedbackType": "correct",
                "rating": 4,
                "comments": "Connection ring dusting may deserve Heavy if repeated in the next outage review.",
                "helpful": False,
            },
            {
                "userId": "user_001",
                "userName": "Demo User",
                "findingId": "finding_008",
                "feedback": "up",
                "feedbackType": "correct",
                "rating": 1,
                "comments": "Oil ingress is limited and Light is acceptable here.",
                "helpful": True,
            },
            {
                "userId": "user_001",
                "userName": "Demo User",
                "findingId": "finding_009",
                "feedback": "up",
                "feedbackType": "correct",
                "rating": 1,
                "comments": "Slot wedge tightness should stay Medium until broader testing is done.",
                "helpful": True,
            },
            {
                "userId": "user_001",
                "userName": "Demo User",
                "findingId": "finding_010",
                "feedback": "up",
                "feedbackType": "correct",
                "rating": 1,
                "comments": "Historic-only FOD context is correctly treated as not mentioned.",
                "helpful": True,
            }
        ],
    }
}

# Initialize with sample data
MOCK_ASSESSMENTS.update(SAMPLE_ASSESSMENTS)


def _format_finding_output_order(finding: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(finding, dict):
        return finding

    # Preserve id / findingId so that feedback_map lookups in both the data-service
    # GET /findings endpoint and the narrative service can resolve feedback by ID.
    finding_id = str(finding.get("id") or finding.get("findingId") or "")
    ordered_finding: dict[str, Any] = {}
    if finding_id:
        ordered_finding["id"] = finding_id
        ordered_finding["findingId"] = finding_id
    ordered_finding.update({
        "Issue name": finding.get("Issue name", ""),
        "Component and Issue Grouping": finding.get("Component and Issue Grouping", ""),
        "Condition": finding.get("Condition", ""),
        "Threshold": finding.get("Threshold", ""),
        "Actual Value": finding.get("Actual Value", ""),
        "Risk": finding.get("Risk", ""),
        "Evidence": finding.get("Evidence", ""),
        "Citation": finding.get("Citation", ""),
        "justification": finding.get("justification", ""),
        "Ambiguity handling": finding.get("Ambiguity handling", ""),
        "_meta": finding.get("_meta", {}),
    })

    return ordered_finding


def _derive_component_from_grouping(grouping: str) -> str:
    normalized = str(grouping or "").lower()
    if "rotor" in normalized:
        return "Rotor"
    if "stator" in normalized:
        return "Stator"
    return "Stator"


def _seed_mock_risk_analysis_store() -> None:
    for assessment_id, assessment in SAMPLE_ASSESSMENTS.items():
        esn = str(assessment.get("esn") or assessment.get("esin_id") or "")
        reliability = assessment.get("reliability") if isinstance(assessment.get("reliability"), dict) else {}
        findings = reliability.get("riskCategories") if isinstance(reliability.get("riskCategories"), list) else []
        formatted_findings = [_format_finding_output_order(finding) for finding in findings if isinstance(finding, dict)]
        summary = str(reliability.get("summary") or "")

        risk_analysis_store.write_risk_analysis(
            esn=esn,
            assessment_id=assessment_id,
            raw_rows=formatted_findings,
            findings=formatted_findings,
            summary=summary,
        )

        feedback_rows = assessment.get("feedback") if isinstance(assessment.get("feedback"), list) else []
        for feedback in feedback_rows:
            if not isinstance(feedback, dict):
                continue
            finding_id = str(feedback.get("findingId") or "").strip()
            if not finding_id:
                continue
            risk_analysis_store.write_feedback(assessment_id, finding_id, feedback)


# Guard: only seed when DynamoDB is actually reachable (i.e. not during test collection
# or unit-test runs where no local DynamoDB is running).  The conftest sets USE_MOCK via
# monkeypatch after import, so checking the env var here is the earliest safe gate.
if os.getenv("DYNAMODB_ENDPOINT_URL") or not os.getenv("USE_MOCK", "").lower() == "true":
    try:
        _seed_mock_risk_analysis_store()
    except Exception:  # noqa: BLE001
        pass  # DynamoDB not available — tests will seed via fixtures or skip seeding


def _normalize_assessment_shape(assessment: dict[str, Any]) -> dict[str, Any]:
    """Return an API-facing assessment shape in canonical backend schema."""
    normalized = dict(assessment)
    assessment_id = normalized.get("assessmentId") or normalized.get("id")
    esn = normalized.get("esn") or normalized.get("serialNumber")

    # Canonical storage keys
    normalized["assessmentId"] = assessment_id
    normalized["esn"] = esn

    # Compatibility aliases for current UI/tests (response only).
    normalized["id"] = assessment_id
    normalized["serialNumber"] = esn

    # Keep only the canonical review field.
    if not normalized.get("reviewPeriod"):
        normalized["reviewPeriod"] = normalized.get("milestone") or "18-month"

    return normalized


def create_assessment(assessment_data: dict[str, Any]) -> dict[str, Any]:
    """Create a new assessment."""
    from data_service import config  # noqa: PLC0415
    from data_service.db import assessments as db_store  # noqa: PLC0415

    assessment_id = f"asmt_{uuid.uuid4().hex[:8]}"
    esn = assessment_data.get("esn") or assessment_data.get("serialNumber", "")
    persona = assessment_data.get("persona", "")
    workflow_id = assessment_data.get("workflowId", "")
    review_period = assessment_data.get("reviewPeriod") or assessment_data.get("milestone") or "18-month"
    filters: dict[str, Any] = {
        "dataTypes": assessment_data.get("dataTypes") or [],
        "fromDate": assessment_data.get("dateFrom"),
        "toDate": assessment_data.get("dateTo"),
    }
    assessment = {
        "assessmentId": assessment_id,
        "esn": esn,
        "persona": persona,
        "workflowId": workflow_id,
        "unitNumber": assessment_data.get("unitNumber"),
        "component": assessment_data.get("component"),
        "reviewPeriod": review_period,
        "equipmentType": assessment_data.get("equipmentType"),
        "createdBy": assessment_data.get("createdBy", "user_001"),
        "createdAt": datetime.now().isoformat() + "Z",
        "updatedAt": datetime.now().isoformat() + "Z",
        "workflowStatus": "PENDING",
        "filters": filters,
    }

    MOCK_ASSESSMENTS[assessment_id] = assessment
    if not config.USE_MOCK_ASSESSMENTS:  # pragma: no cover
        # Write the initial assessment row to the execution-state DynamoDB table.
        db_store.write_assessment(
            esn=esn,
            assessment_id=assessment_id,
            persona=persona,
            workflow_id=workflow_id,
            review_period=review_period,
            unit_number=assessment_data.get("unitNumber"),
            filters=filters,
            created_by=assessment_data.get("createdBy", "user_001"),
        )
    return _normalize_assessment_shape(assessment)


def get_assessment(assessment_id: str) -> dict[str, Any] | None:
    """Get assessment by ID, joined with any stored analysis results."""
    from data_service import config  # noqa: PLC0415
    from data_service.db import assessments as db_store  # noqa: PLC0415

    assessment = MOCK_ASSESSMENTS.get(assessment_id)
    if assessment is None and not config.USE_MOCK_ASSESSMENTS:
        assessment = db_store.read_latest_assessment(assessment_id)
    if assessment is None:
        return None

    # Shallow-copy so we don't mutate the in-memory source
    assessment = dict(assessment)

    reliability = assessment.get("reliability") if isinstance(assessment.get("reliability"), dict) else None
    if reliability and isinstance(reliability.get("riskCategories"), list):
        for finding in reliability["riskCategories"]:
            if not isinstance(finding, dict):
                continue
            if "component" not in finding:
                finding["component"] = _derive_component_from_grouping(
                    str(finding.get("Component and Issue Grouping", ""))
                )

    # Join risk analysis findings → reliabilityRiskCategories
    # Note: write_risk_analysis stores the list under "findings", not "riskCategories"
    ra = risk_analysis_store.read_risk_analysis(assessment_id)
    if ra is not None:
        findings: list[dict[str, Any]] = []
        if isinstance(ra.get("findings"), list):
            findings = ra["findings"]
        feedback_map = ra.get("feedback") if isinstance(ra.get("feedback"), dict) else {}
        # Always expose the key so the UI can detect that analysis has completed.
        assessment["reliabilityRiskCategories"] = {
            f["id"]: f
            for f in findings
            if isinstance(f, dict) and "id" in f
        }
        assessment["savedRows"] = {
            str(finding_id): str(payload.get("submittedAt", ""))
            for finding_id, payload in feedback_map.items()
            if isinstance(payload, dict)
        }

    # Join narrative summary
    ns = narrative_summary_store.read_narrative_summary(assessment_id)
    if ns and ns.get("summary"):
        assessment["narrativeSummary"] = ns["summary"]

    # Join event history
    eh = event_history_store.read_event_history(assessment_id)
    if eh and eh.get("events"):
        assessment["eventHistory"] = eh["events"]

    return _normalize_assessment_shape(assessment)


def get_all_assessments(
    status: str = "",
    esn: str = "",
    date_from: str = "",
    date_to: str = "",
) -> list[dict[str, Any]]:
    """Return all assessments, with optional status, ESN, and date-range filters."""
    from data_service import config  # noqa: PLC0415
    from data_service.db import assessments as db_store  # noqa: PLC0415

    if config.USE_MOCK_ASSESSMENTS:
        results = list(MOCK_ASSESSMENTS.values())
        if status:
            status_lc = status.lower()
            results = [
                a
                for a in results
                if str(a.get("workflowStatus") or a.get("status") or "").lower() == status_lc
            ]
        if esn:
            results = [a for a in results if str(a.get("esn") or "").lower() == esn.lower()]
        if date_from:
            results = [a for a in results if a.get("createdAt", "") >= date_from]
        if date_to:
            date_to_end = date_to + "T23:59:59Z"
            results = [a for a in results if a.get("createdAt", "") <= date_to_end]
        sorted_results = sorted(results, key=lambda a: a.get("createdAt", ""), reverse=True)
        return [_normalize_assessment_shape(a) for a in sorted_results]

    live_results = db_store.list_assessments(
        status=status or None,
        esn=esn or None,
        date_from=date_from or None,
        date_to=date_to or None,
    )
    return [_normalize_assessment_shape(a) for a in live_results]


def update_assessment(assessment_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update an existing assessment."""
    if assessment_id in MOCK_ASSESSMENTS:
        MOCK_ASSESSMENTS[assessment_id].update(updates)
        MOCK_ASSESSMENTS[assessment_id]["updatedAt"] = datetime.now().isoformat() + "Z"
        return _normalize_assessment_shape(MOCK_ASSESSMENTS[assessment_id])
    return None


def analyze_reliability(assessment_id: str) -> dict[str, Any] | None:
    """Generate mock reliability analysis.

    Returns findings in the format expected by _group_by_operation:
    each item has a `component` key and a `conditions` list.
    Also returns `narrativeSummary` because the RE_DEFAULT pipeline runs
    risk_eval → narrative in a single workflow pass.
    """
    assessment = MOCK_ASSESSMENTS.get(assessment_id)
    if not assessment:
        return None

    assessment["updatedAt"] = datetime.now().isoformat() + "Z"
    assessment["status"] = "In Progress"

    return {
        # Flat findings grouped by component — processed by _group_by_operation
        # into RiskCategory objects keyed by (component, operation) slug.
        "findings": [
            {
                "component": "Traction Motor",
                "overallRisk": "Medium",
                "processDocument": "GEI-50063",
                "reliabilityModelRef": "RM-ELEC-001",
                "conditions": [
                    {
                        "category": "Component Degradation",
                        "condition": "Elevated operating temperature",
                        "threshold": "Baseline +5%",
                        "actualValue": "Baseline +8%",
                        "riskLevel": "Medium",
                        "testMethod": "Thermal monitoring",
                        "evidence": "3 consecutive FSR reports showing upward trend",
                        "dataSource": "Historical FSR + Real-time monitoring",
                        "justification": "Operating temperature elevated 8% above Q3 baseline (FSR-2026-010, §3.2)",
                        "primaryCitation": "FSR-2026-010, p.4",
                        "status": "complete",
                    },
                    {
                        "category": "Wear Patterns",
                        "condition": "Bearing surface wear within acceptance limits",
                        "threshold": "Class B tolerance",
                        "actualValue": "Class A — within specification",
                        "riskLevel": "Low",
                        "testMethod": "Dimensional inspection",
                        "evidence": "Last scheduled overhaul report",
                        "dataSource": "Maintenance Records",
                        "justification": "Bearing surfaces within specification at last inspection",
                        "primaryCitation": "MNT-2025-044, p.12",
                        "status": "complete",
                    },
                ],
            },
            {
                "component": "Electrical System",
                "overallRisk": "Light",
                "processDocument": "GEI-50064",
                "reliabilityModelRef": "RM-ELEC-002",
                "conditions": [
                    {
                        "category": "Insulation Health",
                        "condition": "Insulation resistance above minimum threshold",
                        "threshold": "> 100 MΩ",
                        "actualValue": "142 MΩ",
                        "riskLevel": "Low",
                        "testMethod": "Megger test",
                        "evidence": "Periodic insulation resistance test results",
                        "dataSource": "Test Records + ML Prediction Model",
                        "justification": "Resistance well above the 100 MΩ minimum; all KPIs within normal range",
                        "primaryCitation": "ER-2025-018, p.7",
                        "status": "complete",
                    },
                ],
            },
        ],
        # RE_DEFAULT pipeline produces narrative in the same workflow pass.
        "narrativeSummary": (
            "Risk Evaluation Summary\n\n"
            "Overall reliability risk: MEDIUM.\n\n"
            "Traction Motor: Elevated operating temperature (8% above baseline) detected across 3 "
            "consecutive FSR reports. Bearing inspection and proactive maintenance scheduling recommended "
            "within the next 500 operating hours (reference: FSR-2026-010, §3.2).\n\n"
            "Electrical System: All parameters within specification. Insulation resistance measured at "
            "142 MΩ against a minimum threshold of 100 MΩ. Continue standard monitoring protocol.\n\n"
            "No immediate safety concerns identified. Schedule maintenance during the next available window."
        ),
    }


def analyze_outage(assessment_id: str) -> dict[str, Any] | None:
    """Generate mock outage analysis"""
    assessment = MOCK_ASSESSMENTS.get(assessment_id)
    if not assessment:
        return None

    # Mock outage analysis
    outage_analysis = {
        "riskLevel": "Low",
        "estimatedDuration": "6-8 hours",
        "estimatedCost": 12000,
        "scope": [
            {
                "id": f"scope_{uuid.uuid4().hex[:6]}",
                "task": "Component Inspection",
                "duration": "2 hours",
                "cost": 3000,
                "criticality": "High",
            },
            {
                "id": f"scope_{uuid.uuid4().hex[:6]}",
                "task": "Replacement & Installation",
                "duration": "4 hours",
                "cost": 7000,
                "criticality": "High",
            },
            {
                "id": f"scope_{uuid.uuid4().hex[:6]}",
                "task": "Testing & Validation",
                "duration": "2 hours",
                "cost": 2000,
                "criticality": "Medium",
            },
        ],
        "schedulingRecommendation": "Schedule during next maintenance window",
        "impactAnalysis": {
            "serviceImpact": "Low - Minimal service disruption expected",
            "safetyImpact": "None - Standard safety protocols apply",
            "operationalImpact": "Low - Parts readily available",
        },
    }

    assessment["outage"] = outage_analysis
    assessment["updatedAt"] = datetime.now().isoformat() + "Z"
    if assessment.get("reliability"):
        assessment["status"] = "Completed"

    return outage_analysis


def update_reliability_findings(assessment_id: str, reliability_data: dict[str, Any]) -> dict[str, Any] | None:
    """Update reliability findings"""
    assessment = MOCK_ASSESSMENTS.get(assessment_id)
    if not assessment:
        return None

    if assessment.get("reliability"):
        assessment["reliability"].update(reliability_data)
    else:
        assessment["reliability"] = reliability_data

    assessment["updatedAt"] = datetime.now().isoformat() + "Z"
    return _normalize_assessment_shape(assessment)


def update_outage_scope(assessment_id: str, outage_data: dict[str, Any]) -> dict[str, Any] | None:
    """Update outage scope"""
    assessment = MOCK_ASSESSMENTS.get(assessment_id)
    if not assessment:
        return None

    if assessment.get("outage"):
        assessment["outage"].update(outage_data)
    else:
        assessment["outage"] = outage_data

    assessment["updatedAt"] = datetime.now().isoformat() + "Z"
    return _normalize_assessment_shape(assessment)


def submit_feedback(assessment_id: str, finding_id: str, feedback_data: dict[str, Any]) -> dict[str, Any] | None:
    """Submit feedback for a specific finding"""
    assessment = MOCK_ASSESSMENTS.get(assessment_id)
    if not assessment:
        return None

    feedback = {
        "id": f"feedback_{uuid.uuid4().hex[:8]}",
        "findingId": finding_id,
        "userId": feedback_data.get("userId", "user_001"),
        "userName": feedback_data.get("userName", "Unknown User"),
        "feedback": feedback_data.get("feedback"),
        "feedbackType": feedback_data.get("feedbackType"),
        "rating": feedback_data.get("rating", 0),
        "comments": feedback_data.get("comments", ""),
        "helpful": feedback_data.get("helpful", True),
        "submittedAt": datetime.now().isoformat() + "Z",
    }

    if "feedback" not in assessment:
        assessment["feedback"] = []

    assessment["feedback"].append(feedback)
    assessment["updatedAt"] = datetime.now().isoformat() + "Z"

    return feedback
