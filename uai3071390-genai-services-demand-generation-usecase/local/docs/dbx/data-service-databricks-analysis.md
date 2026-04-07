# Data Service — Databricks Analysis

## Overview

The data-service connects to Databricks SQL (via `databricks-sql-connector` or Naksha proxy) and AWS DynamoDB to retrieve data for MCP tools. This document maps the Databricks tables/views used by each service.

## Databricks Catalog: `vgpd`

All table/schema names are configurable via environment variables. Defaults shown below.

### Schema: `prm_std_views` (IBAT)

| Table/View | Config Vars | Service | MCP Tool |
|---|---|---|---|
| `IBAT_EQUIPMENT_MST` | `IBAT_CATALOG`, `IBAT_SCHEMA`, `IBAT_EQUIPMENT_TABLE` | ibat_service.py, equipment_service.py | read_ibat |
| `IBAT_PLANT_MST` | `IBAT_PLANT_TABLE`, `IBAT_PLANT_VIEW` | ibat_service.py | read_ibat |
| `ibat_train_mst` | `IBAT_TRAIN_TABLE`, `IBAT_TRAIN_VIEW` | ibat_service.py, train_service.py | read_ibat |

### Schema: `fsr_std_views` (FSR, Events, Heatmap)

| Table/View | Config Vars | Service | MCP Tool |
|---|---|---|---|
| `fsr_field_vision_field_services_report_psot` | `FSR_CATALOG`, `FSR_SCHEMA`, `FSR_TABLE` | equipment_service.py | query_fsr |
| `fsr_pdf_ref` | hardcoded `_FSR_PDF_REF_TABLE` | fsr_metadata_service.py | query_fsr |
| `fsr_unit_risk_matrix_view` | `HEATMAP_CATALOG`, `HEATMAP_SCHEMA`, `HEATMAP_TABLE` | heatmap_service.py | load_heatmap (read_risk_matrix) |
| `eventmgmt_event_vision_sot` | `EVENT_MASTER_CATALOG`, `EVENT_MASTER_SCHEMA`, `OUTAGE_EVENTMGMT_TABLE` | equipment_service.py | read_event_master |
| `event_equipment_dtls_event_vision_sot` | `OUTAGE_EQUIP_DTLS_TABLE` | equipment_service.py | read_event_master |
| `scope_schedule_summary_event_vision_sot` | `OUTAGE_SCOPE_TABLE` | equipment_service.py | read_event_master |

### Schema: `qlt_std_views` (ER Cases)

| Table/View | Config Vars | Service | MCP Tool |
|---|---|---|---|
| `u_pac` | `ER_CATALOG`, `ER_SCHEMA`, `ER_TABLE` | equipment_service.py, er_service.py | query_er |

### Schema: `seg_std_views` (PRISM / FMEA)

| Table/View | Config Vars | Service | MCP Tool |
|---|---|---|---|
| `seg_fmea_wo_models_gen_psot` | `PRISM_CATALOG`, `PRISM_SCHEMA`, `PRISM_SOT_TABLE` | prism_service.py, equipment_service.py | read_prism |

### Schemas Not Used

| Schema | Status |
|---|---|
| `eng_std_views` | Not referenced in codebase |
| `fsr_sox_std_views` | Not referenced in codebase |

## Databricks Catalog: `main` (Vector Search)

| Index | FQN | Config Var | Service | MCP Tool |
|---|---|---|---|---|
| `vs_field_service_report_gt_litellm` | `main.gp_services_sdg_poc.vs_field_service_report_gt_litellm` | `VECTOR_SEARCH_INDEX` | retriever_service.py | query_fsr (vector retrieval) |

## AWS DynamoDB Tables (not Databricks)

| Config Var | Default Table Name | Purpose |
|---|---|---|
| `EXECUTION_STATE_TABLE` | `app-uai3071390-sdg-ddtable-execution-state-store-dev` | Workflow execution state |
| `RISK_ANALYSIS_TABLE` | `app-uai3071390-sdg-ddtable-risk-analysys-output-table-dev` | Risk assessment output (RE/OE tables, reports) |
| `NARRATIVE_SUMMARY_TABLE` | `app-uai3071390-sdg-ddtable-navigation-summary-dev` | Narrative summary |
| `EVENT_HISTORY_TABLE` | `app-uai3071390-sdg-ddtable-event-history-report-dev` | Event history report |

## Databricks Connectivity

| Component | Location | Notes |
|---|---|---|
| `DatabricksClient` | data_service/databricks_client.py | Direct SQL via `databricks.sql` connector |
| `NakshaClient` | data_service/client.py | SQL via Naksha proxy (alternative path) |
| `VectorSearchClient` | retriever_service.py | Databricks Vector Search for FSR retrieval |
| Dependency | pyproject.toml | `databricks-sql-connector>=2.9.0` |

## MCP Tool → Databricks Table Mapping (Summary)

| MCP Tool (auto-generated name) | Alias | Databricks Table(s) | Schema |
|---|---|---|---|
| `get_ibat_equipment_endpoint_...` | read_ibat | IBAT_EQUIPMENT_MST, IBAT_PLANT_MST, ibat_train_mst | prm_std_views |
| `read_prism_dataservices_...` | read_prism | seg_fmea_wo_models_gen_psot | seg_std_views |
| `retrieve_endpoint_...` | query_fsr | fsr_field_vision_field_services_report_psot + Vector Search | fsr_std_views + main |
| `get_er_cases_endpoint_...` | query_er | u_pac | qlt_std_views |
| `load_heatmap_dataservices_...` | load_heatmap / read_risk_matrix | fsr_unit_risk_matrix_view | fsr_std_views |
| read_event_master | read_event_master | eventmgmt_event_vision_sot + related | fsr_std_views |
| read_re_table, read_re_report | — | DynamoDB (RISK_ANALYSIS_TABLE) | N/A |
| read_oe_table | — | DynamoDB (RISK_ANALYSIS_TABLE) | N/A |
| read_event_report | — | DynamoDB (EVENT_HISTORY_TABLE) | N/A |
