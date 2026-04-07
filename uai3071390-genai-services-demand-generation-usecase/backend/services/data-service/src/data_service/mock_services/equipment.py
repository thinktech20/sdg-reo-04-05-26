"""
Mock data aligned to the real domain model used by the demo and frontend.

Domain model
────────────
  Train     — a gas turbine generator TRAIN at a plant site.
              Identified by id (e.g. train-001). Has trainName, site, trainType,
              outageId, outageType (Major|Minor), startDate, endDate, equipment[].
              Served by: GET /api/units

  Equipment — a serialised GE Vernova component within a train.
              Identified by serialNumber (ESN). Has equipmentType, equipmentCode,
              model, site, commercialOpDate, totalEOH, totalStarts, coolingType.
              Served by: GET /api/equipment/search?esn=
                         GET /api/equipment/{esn}/*
"""

import os
from typing import Any

IBAT_EQUIPMENT_URL = os.getenv("IBAT_EQUIPMENT_DATA_URL")
ER_CASES_DATA_URL = os.getenv("ER_CASES_DATA_URL")

# ── Install Base (keyed by serialNumber) ─────────────────────────────────────

MOCK_INSTALL_BASE = {
    "GT12345": {
        "serialNumber": "GT12345",
        "equipmentType": "Gas Turbine",
        "equipmentCode": "7FA.05",
        "model": "7FA",
        "site": "Moss Landing",
        "commercialOpDate": "1999-08-15",
        "totalEOH": 145234,
        "totalStarts": 892,
        "coolingType": "Air-Cooled",
    },
    "92307": {
        "serialNumber": "92307",
        "equipmentType": "Generator",
        "equipmentCode": "W88",
        "model": "W88",
        "site": "Moss Landing",
        "commercialOpDate": "1999-08-15",
        "totalEOH": 145234,
        "totalStarts": 892,
        "coolingType": "Hydrogen-Cooled",
    },
    "ST99999": {
        "serialNumber": "ST99999",
        "equipmentType": "Steam Turbine",
        "equipmentCode": "D11",
        "model": "D11",
        "site": "Moss Landing",
        "commercialOpDate": "1999-08-15",
        "totalEOH": 145234,
        "totalStarts": 892,
        "coolingType": None,
    },
    "GT67890": {
        "serialNumber": "GT67890",
        "equipmentType": "Gas Turbine",
        "equipmentCode": "7FA.05",
        "model": "7FA",
        "site": "Pittsburg",
        "commercialOpDate": "2001-05-20",
        "totalEOH": 132456,
        "totalStarts": 745,
        "coolingType": "Air-Cooled",
    },
    "GEN54321": {
        "serialNumber": "GEN54321",
        "equipmentType": "Generator",
        "equipmentCode": "W88",
        "model": "W88",
        "site": "Pittsburg",
        "commercialOpDate": "2001-05-20",
        "totalEOH": 132456,
        "totalStarts": 745,
        "coolingType": "Hydrogen-Cooled",
    },
    "GT11111": {
        "serialNumber": "GT11111",
        "equipmentType": "Gas Turbine",
        "equipmentCode": "9FA.03",
        "model": "9FA",
        "site": "Delta Energy",
        "commercialOpDate": "2005-03-10",
        "totalEOH": 98234,
        "totalStarts": 523,
        "coolingType": "Closed-Loop Water",
    },
    "GEN22222": {
        "serialNumber": "GEN22222",
        "equipmentType": "Generator",
        "equipmentCode": "A13",
        "model": "A13",
        "site": "Colstrip",
        "commercialOpDate": "1986-11-22",
        "totalEOH": 287456,
        "totalStarts": 342,
        "coolingType": "Hydrogen-Cooled",
    },
    "ST88888": {
        "serialNumber": "ST88888",
        "equipmentType": "Steam Turbine",
        "equipmentCode": "STF-A60",
        "model": "STF-A",
        "site": "Colstrip",
        "commercialOpDate": "1986-11-22",
        "totalEOH": 287456,
        "totalStarts": 342,
        "coolingType": None,
    },
}

# ── Train Configurations ──────────────────────────────────────────────────────

MOCK_TRAINS = [
    {
        "id": "train-001",
        "trainName": "1-1 Train",
        "site": "Moss Landing",
        "trainType": "Combined Cycle 1x1",
        "outageId": "ML-2025-001",
        "outageType": "Major",
        "startDate": "2025-04-15",
        "endDate": "2025-06-30",
        "equipment": [
            MOCK_INSTALL_BASE["GT12345"],
            MOCK_INSTALL_BASE["92307"],
            MOCK_INSTALL_BASE["ST99999"],
        ],
    },
    {
        "id": "train-002",
        "trainName": "2-1 Train",
        "site": "Pittsburg",
        "trainType": "Simple Cycle",
        "outageId": "PIT-2025-002",
        "outageType": "Major",
        "startDate": "2025-09-01",
        "endDate": "2025-11-15",
        "equipment": [
            MOCK_INSTALL_BASE["GT67890"],
            MOCK_INSTALL_BASE["GEN54321"],
        ],
    },
    {
        "id": "train-003",
        "trainName": "3-1 Train",
        "site": "Delta Energy",
        "trainType": "Simple Cycle",
        "outageId": "DE-2025-003",
        "outageType": "Minor",
        "startDate": "2025-06-10",
        "endDate": "2025-07-05",
        "equipment": [
            MOCK_INSTALL_BASE["GT11111"],
        ],
    },
    {
        "id": "train-004",
        "trainName": "Unit 3",
        "site": "Colstrip",
        "trainType": "Combined Cycle 2x1",
        "outageId": "COL-2026-001",
        "outageType": "Major",
        "startDate": "2026-03-01",
        "endDate": "2026-05-31",
        "equipment": [
            MOCK_INSTALL_BASE["GEN22222"],
            MOCK_INSTALL_BASE["ST88888"],
        ],
    },
]

# ── ER Cases (keyed by serial number) ────────────────────────────────────────

MOCK_ER_CASES = {
    "GT12345": [
        {
            "id": "ER-2024-2345",
            "caseId": "ER-2024-2345",
            "serialNumber": "GT12345",
            "shortDesc": "Stage 1 bucket TBC coating degradation",
            "longDesc": (
                "Borescope inspection revealed TBC spallation on 3 stage 1 buckets. "
                "Estimated 15% coating loss on leading edge."
            ),
            "severity": "Medium",
            "status": "Open",
            "dateOpened": "2024-09-01",
            "closeNotes": "Plan bucket replacement at next HGP",
            "category": "Turbine",
        },
        {
            "id": "ER-2024-3001",
            "caseId": "ER-2024-3001",
            "serialNumber": "GT12345",
            "shortDesc": "Combustion liner cracking — cans 7 and 9",
            "longDesc": (
                "Minor circumferential cracking observed on combustion liners for cans 7 "
                "and 9 during last combustion inspection. Aft frame also shows minor oxidation."
            ),
            "severity": "Low",
            "status": "Monitoring",
            "dateOpened": "2024-11-14",
            "closeNotes": "",
            "category": "Combustion",
        },
    ],
    "92307": [
        {
            "id": "ER-2024-1234",
            "caseId": "ER-2024-1234",
            "serialNumber": "92307",
            "shortDesc": "Corona damage observed on stator end windings",
            "longDesc": (
                "During routine visual inspection, corona discharge patterns were observed on "
                "phase A end windings. PD levels measured at 850 pC."
            ),
            "severity": "Medium",
            "status": "Open",
            "dateOpened": "2024-08-15",
            "closeNotes": "Recommended monitoring and assessment at next outage",
            "category": "Electrical",
        },
        {
            "id": "ER-2024-0987",
            "caseId": "ER-2024-0987",
            "serialNumber": "92307",
            "shortDesc": "Elevated stator bar temperatures",
            "longDesc": (
                "RTD readings showing 5°C above baseline on bars 12-15. "
                "Trend analysis indicates gradual increase over 6 months."
            ),
            "severity": "High",
            "status": "Monitoring",
            "dateOpened": "2024-06-20",
            "closeNotes": "Schedule thermal imaging during next inspection",
            "category": "Thermal",
        },
    ],
    "GEN22222": [
        {
            "id": "ER-2025-0055",
            "caseId": "ER-2025-0055",
            "serialNumber": "GEN22222",
            "shortDesc": "Collector ring wear approaching allowable limit",
            "longDesc": (
                'Collector ring diameter measured at 0.012" below new dimension. '
                "Approaching 50% of allowable wear limit. Unit age: 37+ years."
            ),
            "severity": "Medium",
            "status": "Open",
            "dateOpened": "2025-01-10",
            "closeNotes": "",
            "category": "Mechanical",
        },
    ],
}

# ── FSR Reports (keyed by serial number) ─────────────────────────────────────

MOCK_FSR_REPORTS = {
    "GT12345": [
        {
            "id": "FSR-2023-0418",
            "reportId": "FSR-2023-0418",
            "serialNumber": "GT12345",
            "title": "Hot Gas Path Inspection",
            "reportDate": "2023-04-18",
            "outageDate": "2023-04-15",
            "technician": "J. Martinez",
            "scopeSummary": (
                "HGP inspection completed. All combustion hardware inspected, stage 1-2 "
                "buckets and nozzles inspected, transition pieces assessed."
            ),
            "conditionsObserved": (
                "Stage 1 buckets showing normal wear patterns. Combustion liners within "
                "serviceable limits. Transition pieces — minor cracking on 2 units."
            ),
            "recommendations": [
                "Replace transition pieces at next HGP.",
                "Continue monitoring stage 1 bucket TBC condition.",
                "Plan for potential bucket replacement at Major Inspection.",
            ],
            "testResults": {
                "exhaustSpread": "15°F",
                "wheelspaceTemps": "Normal",
                "vibration": "0.3 mils",
            },
            "pageCount": 18,
        },
    ],
    "92307": [
        {
            "id": "FSR-2023-0420",
            "reportId": "FSR-2023-0420",
            "serialNumber": "92307",
            "title": "Generator Major Inspection",
            "reportDate": "2023-04-20",
            "outageDate": "2023-04-15",
            "technician": "A. Patel",
            "scopeSummary": (
                "Generator Major Inspection completed. Stator visual inspection, "
                "rotor removal, collector ring inspection."
            ),
            "conditionsObserved": (
                "Minor dusting on stator end windings, collector ring wear within limits "
                '(0.015" measured). Rotor retaining ring NDT passed.'
            ),
            "recommendations": [
                "Plan detailed PD testing at 12-month milestone.",
                "Monitor collector ring wear trend.",
                "Consider end winding cleaning at next opportunity.",
            ],
            "testResults": {
                "dcLeakage": "2.5 GΩ @ 5kV",
                "statorBarTemp": "Max 85°C",
                "pdLevel": "450 pC",
            },
            "pageCount": 24,
        },
    ],
    "GT67890": [
        {
            "id": "FSR-2024-0902",
            "reportId": "FSR-2024-0902",
            "serialNumber": "GT67890",
            "title": "Combustion Inspection",
            "reportDate": "2024-09-05",
            "outageDate": "2024-09-01",
            "technician": "R. Chen",
            "scopeSummary": (
                "Combustion inspection completed on all 6 combustion cans. "
                "End cover removed, fuel nozzles and caps inspected."
            ),
            "conditionsObserved": (
                "All combustion liners within serviceable limits. "
                "Fuel nozzle tips show minor coking — cleaned in place."
            ),
            "recommendations": [
                "Replace fuel nozzle caps at next HGP.",
                "No scope additions required.",
            ],
            "testResults": {
                "exhaustSpread": "12°F",
                "combustionRates": "Normal",
            },
            "pageCount": 10,
        },
    ],
}

# ── Outage History (keyed by serial number) ───────────────────────────────────

MOCK_OUTAGE_HISTORY = {
    "GT12345": [
        {
            "id": "OUT-HGP-2023",
            "esn": "GT12345",
            "eventType": "Hot Gas Path Inspection",
            "plannedDate": "2023-04-15",
            "actualDate": "2023-04-18",
            "projectId": "ML-PRJ-2023-0415",
            "status": "Completed",
            "duration": "33 days",
        },
        {
            "id": "OUT-CI-2021",
            "esn": "GT12345",
            "eventType": "Combustion Inspection",
            "plannedDate": "2021-10-01",
            "actualDate": "2021-10-05",
            "projectId": "ML-PRJ-2021-1001",
            "status": "Completed",
            "duration": "7 days",
        },
        {
            "id": "OUT-MI-2019",
            "esn": "GT12345",
            "eventType": "Major Inspection",
            "plannedDate": "2019-05-10",
            "actualDate": "2019-05-10",
            "projectId": "ML-PRJ-2019-0510",
            "status": "Completed",
            "duration": "45 days",
        },
    ],
    "92307": [
        {
            "id": "OUT-GMI-2023",
            "esn": "92307",
            "eventType": "Generator Major Inspection",
            "plannedDate": "2023-04-15",
            "actualDate": "2023-04-20",
            "projectId": "ML-PRJ-2023-0415",
            "status": "Completed",
            "duration": "35 days",
        },
        {
            "id": "OUT-GSI-2022",
            "esn": "92307",
            "eventType": "Stator Visual Inspection",
            "plannedDate": "2022-03-10",
            "actualDate": "2022-03-12",
            "projectId": "ML-PRJ-2022-0310",
            "status": "Completed",
            "duration": "5 days",
        },
    ],
    "GT67890": [
        {
            "id": "OUT-CI-2024-PIT",
            "esn": "GT67890",
            "eventType": "Combustion Inspection",
            "plannedDate": "2024-09-01",
            "actualDate": "2024-09-05",
            "projectId": "PIT-PRJ-2024-0901",
            "status": "Completed",
            "duration": "12 days",
        },
    ],
    "GEN22222": [
        {
            "id": "OUT-GMI-2020-COL",
            "esn": "GEN22222",
            "eventType": "Generator Major Inspection",
            "plannedDate": "2020-06-15",
            "actualDate": "2020-06-18",
            "projectId": "COL-PRJ-2020-0615",
            "status": "Completed",
            "duration": "42 days",
        },
    ],
}


# ── Helper Functions ──────────────────────────────────────────────────────────


def get_all_trains() -> list[dict[str, Any]]:
    """Return all train configurations (with nested equipment)."""
    return MOCK_TRAINS


def search_equipment_by_esn(esn: str) -> dict[str, Any] | None:
    """Lookup a single equipment item by serial number (case-insensitive)."""
    equipment = MOCK_INSTALL_BASE.get(esn) or MOCK_INSTALL_BASE.get(esn.upper())
    return equipment


def _filter_by_date(
    items: list[dict[str, Any]],
    date_field: str,
    start_date: str | None,
    end_date: str | None,
) -> list[dict[str, Any]]:
    """Filter a list of records by an ISO-8601 date field (lexicographic comparison)."""
    if not start_date and not end_date:
        return items
    result = []
    for item in items:
        d = item.get(date_field) or ""
        if start_date and d < start_date:
            continue
        if end_date and d > end_date:
            continue
        result.append(item)
    return result


def get_er_cases_by_esn(
    esn: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    cases = MOCK_ER_CASES.get(esn) or MOCK_ER_CASES.get(esn.upper(), [])
    return _filter_by_date(cases, "dateOpened", start_date, end_date)


def get_fsr_reports_by_esn(
    esn: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    reports = MOCK_FSR_REPORTS.get(esn, [])
    return _filter_by_date(reports, "outageDate", start_date, end_date)


def get_outage_history_by_esn(
    esn: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    history = MOCK_OUTAGE_HISTORY.get(esn, [])
    return _filter_by_date(history, "startDate", start_date, end_date)
