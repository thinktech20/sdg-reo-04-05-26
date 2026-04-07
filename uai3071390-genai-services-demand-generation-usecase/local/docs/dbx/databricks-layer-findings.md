# Databricks Layer — Processing, Chunking & Embedding

> Research findings from codebase analysis + DS experiment docs + Feng's SOT verification table.
> Date: April 1, 2026

---

## 1. Three Databricks Catalogs in Play

| Catalog | Role | Where Used |
|---------|------|------------|
| **vgpd** | Dev — default in all application code | SQL SOT queries (IBAT, ER, FSR, PRISM, Heatmap, Events) |
| **vgpp** | Prod | Only referenced in DS experiment doc (PRISM for RE Narrative). **Not in application code.** |
| **main** | Shared / AI workspace | Vector search indexes + embedding table (`main.gp_services_sdg_poc.*`) |

Code sets catalog via env var with `vgpd` default:
```python
CATALOG = os.getenv("CATALOG", "vgpd")
```

---

## 2. Two Data Access Paths

| Path | Client | What It Hits | Used For |
|------|--------|-------------|----------|
| **Naksha SQL API** | HTTP proxy (`NakshaClient`) | SOT views in vgpd | Structured metadata queries, counts, BFF data-readiness |
| **Databricks Vector Search API** | REST POST to `/api/2.0/vector-search/indexes/` | Pre-chunked indexes in `main` catalog | Semantic retrieval (FSR chunks, ER chunks) |

Fallback: Direct Databricks SQL connector if Naksha fails.

---

## 3. Data Flow: SOT → Chunks → Vector Index

### FSR (Field Service Reports)

```
SOT Table: vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot (~35K rows)
    │
    ↓  upstream chunking pipeline (NOT in this codebase)
    │
    ├── Legacy: field_service_report → field_service_report_gt (databricks-gte-large-en)
    │
Source Table: main.gp_services_sdg_poc.field_service_report_gt_litellm  ← ACTIVE
    │
    ↓  embedding via azure-text-embedding-3-large-1 (3072-dim)
    │
Vector Index: main.gp_services_sdg_poc.vs_field_service_report_gt_litellm
```

Other FSR tables in catalog (legacy/POC): `fsr_poc_chunks`, `fsr_poc_chunks3`, `fsr_adv_chunks2`

### ER (Engineering Records)

```
SOT Table: vgpd.qlt_std_views.u_pac
    │
    ↓  upstream chunking pipeline (NOT in this codebase)
    │
    ├── Legacy embedding: databricks-gte-large-en
    │
Source Table: main.gp_services_sdg_poc.engineering_report_chunk  ← ACTIVE
    │  (vector index sources from engineering_report_chunk_litellm — same data + embeddings)
    │
    ↓  embedding via azure-text-embedding-3-large-1 (3072-dim)
    │
Vector Index: main.gp_services_sdg_poc.vs_engineering_report_chunk_litellm
```

Also in catalog: `u_pac`, `u_pac2`, `u_pac_temp` — copies of the ER SOT table

### Embedding Strategy

| Aspect | Detail |
|--------|--------|
| **Migrated from** | Databricks-managed `databricks-gte-large-en` |
| **Migrated to** | Self-managed `azure-text-embedding-3-large-1` (3072-dim) via LiteLLM |
| **Query embeddings** | Pre-computed, stored in `main.gp_services_sdg_poc.heatmap_issue_prompt_embeddings` |
| **Runtime embedding** | None — if prompt not in table, vector search falls back to text-only |

---

## 4. SOT Verification Table Analysis (Feng's Screenshot)

### Column Definitions

| Column | Meaning |
|--------|---------|
| ESN | Equipment serial number |
| FSR vgpp | FSR document count in **prod** catalog |
| FSR vgpd | FSR document count in **dev** catalog |
| FSR Doc(Δ) | FSR document/chunk count in **Delta** (vector source) table |
| FSR Note | Comparison result between SOT and Delta |
| ER vgpp | ER case count in **prod** |
| ER vgpd | ER case count in **dev** |
| ER Case(Δ) | ER case count in **Delta** table |
| ER Note | Comparison result |

### Pattern Key

| Note Value | Meaning | Implication |
|------------|---------|-------------|
| **Δ>SOT** | Chunks outnumber SOT records | Expected — 1 doc/case → multiple chunks |
| **match** | Counts align | SOT and chunked data are in sync |
| **=vgpp** | Delta matches prod, not dev | Dev catalog is stale for this ESN |
| **Δ has data, SOT=0** | Chunks exist, SOT view returns 0 | Data in delta but not in dev SOT views |
| **Δ<SOT** | SOT has more than chunks | Some docs not yet chunked/indexed |
| **Δ>vgpp** | Delta > prod | Extra chunks beyond what prod SOT shows |
| **NO CHUNKS** | Zero chunked data | Ingestion gap — ESN never processed |
| **between** | Delta count falls between vgpp and vgpd | Partial sync |

### Critical Observations

1. **vgpp ≠ vgpd for many ESNs** — Dev catalog often has fewer (or zero) records while prod has data. Dev may be stale or only partially synced.
2. **Delta counts often > SOT counts** — Expected since one FSR document or ER case gets split into multiple chunks.
3. **Two ESNs with NO CHUNKS (337X134, 337X789)** — These have FSR/ER data in SOT but zero chunks in the vector source table. Ingestion gap.
4. **"between" is the most common pattern** — Delta count sits between vgpp and vgpd, suggesting partial coverage or different SOT refresh windows.

---

## 5. What the Code Queries

### SQL SOT Queries (equipment_service.py)

Used for UI data-readiness checks:

```sql
-- ER case count per ESN
SELECT COUNT(*) AS cnt
FROM vgpd.qlt_std_views.u_pac
WHERE u_serial_number = :esn

-- FSR report count per ESN
SELECT COUNT(*) AS cnt
FROM vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot
WHERE esn = :esn

-- Outage history count per ESN (JOIN)
SELECT COUNT(*) AS cnt
FROM vgpd.fsr_std_views.eventmgmt_event_vision_sot em
INNER JOIN vgpd.fsr_std_views.event_equipment_dtls_event_vision_sot ed
  ON em.ev_equipment_event_id = ed.ev_equipment_event_id
WHERE ev_serial_number = :esn
```

### Vector Search Queries (retriever_service.py, er_service.py)

Both use HYBRID mode (keyword + vector):

```python
POST {workspace_url}/api/2.0/vector-search/indexes/{index}/query
{
    "query_text": "issue prompt text",
    "query_vector": [0.1, 0.2, ...],   # from heatmap_issue_prompt_embeddings
    "filters_json": {"generator_serial": "ESN"},
    "num_results": 10,
    "query_type": "HYBRID",
    "columns": ["chunk_id", "chunk_text", "pdf_name", "page_number", "generator_serial"]
}
```

**FSR chunk columns returned:** `chunk_id`, `pdf_name`, `page_number`, `chunk_text`, `generator_serial`, similarity score

**ER chunk columns returned:** `chunk_id`, `er_case_number`, `chunk_text`, `serial_number`, `opened_at`, `status`, `u_component`, `u_field_action_taken`, `equipment_id`

### RE-Only FSR Enrichment (post-vector-search)

RE persona has a 4-table SQL JOIN pipeline after vector search (OE does not):

1. `_chunk_rows_by_id()` — hydrate chunk from source table (gets metadata JSON)
2. `_pdf_ref_rows()` — join via `fsr_pdf_ref` (s3_filename → esn, event_id)
3. `_scraped_mapping_rows()` — join via `fsr_scraped_file_mapping_ref`
4. `_fsr_report_rows()` — join via `fsr_field_vision_field_services_report_psot` (esn + event_id → start_date, end_date, event_type, outage_type)

All 3 SQL lookups run in parallel (`ThreadPoolExecutor`, max_workers=3).

---

## 6. Databricks Schemas & Tables

### Tables Used in Code

| Schema | Table | Service | Purpose |
|--------|-------|---------|---------|
| `fsr_std_views` | `fsr_field_vision_field_services_report_psot` | equipment_service, retriever | FSR report metadata + counts |
| `fsr_std_views` | `fsr_pdf_ref` | fsr_metadata_service | S3 filename → PDF display name |
| `fsr_std_views` | `fsr_unit_risk_matrix_view` | heatmap_service | Risk matrix (71 rows, 14 cols) |
| `fsr_std_views` | `eventmgmt_event_vision_sot` | equipment_service | Event lifecycle (85.8K rows) |
| `fsr_std_views` | `event_equipment_dtls_event_vision_sot` | equipment_service | Equipment per event (85.8K rows) |
| `fsr_std_views` | `scope_schedule_summary_event_vision_sot` | equipment_service | Outage scope/scheduling |
| `prm_std_views` | `IBAT_EQUIPMENT_MST` | ibat_service | Equipment master (665K rows) |
| `prm_std_views` | `IBAT_PLANT_MST` | ibat_service | Plant master (135K rows) |
| `prm_std_views` | `ibat_train_mst` | train_service | Train master (175K rows) |
| `qlt_std_views` | `u_pac` | er_service, equipment_service | ER cases |
| `seg_std_views` | `seg_fmea_wo_models_gen_psot` | prism_service | PRISM FMEA risk models |

### main.gp_services_sdg_poc — Full Table Inventory (29 tables)

> Source: Databricks catalog screenshot, April 2026

#### Vector Search Indexes (6)

| Table | Source Delta Table | Used In Code |
|-------|-------------------|-------------|
| `vs_field_service_report_gt_litellm` | `field_service_report_gt_litellm` | Yes — retriever_service.py (FSR retrieval) |
| `vs_engineering_report_chunk_litellm` | `engineering_report_chunk` (+ `_litellm` with embeddings) | Yes — er_service.py (ER retrieval) |
| `vs_field_service_report_gt` | `field_service_report_gt` | No — pre-LiteLLM migration (legacy) |
| `vs_engineering_report_chunk` | `engineering_report_chunk` | No — pre-LiteLLM migration (legacy) |
| `vs_field_service_report` | `field_service_report` | No — earliest version |
| `poc_vs_field_service_report_gt_litellm` | — | No — POC index |

#### Delta Source Tables — FSR (7)

| Table | Purpose | Status |
|-------|---------|--------|
| `field_service_report_gt_litellm` | **Active** — FSR chunks with LiteLLM embeddings (3072-dim) | In use |
| `field_service_report_gt` | FSR chunks with old Databricks-managed embeddings | Legacy |
| `field_service_report` | Earliest FSR chunk table | Legacy |
| `fsr_poc_chunks` | POC chunk table | Legacy |
| `fsr_poc_chunks3` | POC chunk table v3 (4x original) | Legacy |
| `fsr_adv_chunks2` | Advanced chunking experiment | Legacy |
| `field_service_report_gt_litellm_reingest_targets_20260323` | Reingest tracking (March 23 batch) | Operational |

#### Delta Source Tables — ER (4)

| Table | Purpose | Status |
|-------|---------|--------|
| `engineering_report_chunk` | **Active** — ER chunk base table (verified via Q6) | In use |
| `engineering_report_chunk_litellm` | ER chunks with LiteLLM embeddings (vector index source) | In use |
| `poc_vs_engineering_report_chunk_litellm` | POC ER index | Legacy |
| `u_pac` / `u_pac2` / `u_pac_temp` | Copies of ER SOT table from `vgpd.qlt_std_views.u_pac` | Operational |

#### Support Tables (8)

| Table | Purpose | Used In Code |
|-------|---------|-------------|
| `heatmap_issue_prompt_embeddings` | Pre-computed query embeddings for issue prompts | Yes — retriever_service.py, er_service.py |
| `heatmap_issue_prompt_embeddings_temp` | Temp version of above | No |
| `fsr_pdf_esn_mapping` | PDF filename → ESN mapping | Likely used in enrichment |
| `fsr_pdf_esn_patch_checkpoint` | Patch tracking for PDF-ESN mapping | Operational |
| `ibat_equipment_mst` / `ibat_plant_mst` / `ibat_train_mst` | Copies of IBAT SOT tables | Not directly (code reads from vgpd) |
| `component_data` | Component reference data | Unknown |
| `document_chunks` | Generic chunk table | Unknown |
| `risk_assessment_feedback` | Experiment feedback output | DS experiments |
| `severity_data` | Severity reference/experiment data | DS experiments |

### vgpd Schemas — Visible in Catalog but NOT in Code

- `eng_std_views` — **not referenced anywhere in application code**
- `fsr_sox_std_views` — **not referenced anywhere in application code**

---

## 7. Chunking Pipeline — From DS Experiment Notebooks

> Source: `ERexperiment.py` and `semantic_30_samples.ipynb` shared by Xujin Zhou (DS team).
> Located at: `local/docs/dbx/reference/notebooks/`

The DS team built **experimentation** notebooks, not production pipelines. The data in the app's vector indexes (`main.gp_services_sdg_poc`) was loaded ad-hoc — there is **no automated production ingestion pipeline**.

### 7.1 ER Chunking Pipeline (ERexperiment.py — 978 lines)

**Data source:** Reads directly from **prod** SOT — `vgpp.qlt_std_views.u_pac`

**Connection:**
```
Host: gevernova-ai-dev-dbr.cloud.databricks.com
HTTP Path: /sql/1.0/warehouses/c383216f6af5c7c0
```

**Preprocessing:**
- Filters to `opened_at >= 2016-01-01`
- Drops rows with missing/blank `u_serial_number`
- Maps columns: `number` → `er_number`, `u_status` → `status`
- Retains 50+ columns including all SME-required fields

**Chunking logic:**
1. Concatenates 12 unstructured text fields per ER into one block:
   `close_notes`, `description_`, `comments_and_work_notes`, `u_desired_deliverable`,
   `u_field_action_taken`, `u_resolve_notes`, `u_feedback_comments`,
   `u_immediate_response_explanati`, `user_input`, `work_notes`, `short_description`, `comments`
2. Format: `[FIELD_NAME]\n{content}` separated by double newlines
3. Token estimation: `words × 1.33`
4. If ER ≤ 4,096 tokens → single chunk
5. If ER > 4,096 tokens → sliding window split with 10% overlap
6. Structured metadata preserved in every chunk:
   `er_number`, `opened_at`, `u_component`, `u_field_action_taken`,
   `serial_number`, `status`, `equipment_id`, `chunk_index`, `total_chunks`

**Experiment output tables** (NOT the app tables):
- Chunks: `vaid.ai_sot_field_service_report.er_chunks`
- Results: `vaid.ai_sot_field_service_report.er_retrieval_results`
- Metrics: `vaid.ai_sot_field_service_report.er_retrieval_metrics`

**Retrieval evaluation:**
- BM25 (keyword, weight 0.6) + FAISS (semantic, weight 0.4) + Ensemble (RRF, constant=60)
- Reranking: Jaccard overlap (0.6) + position score (0.4), 1.2x boost for status=Complete
- Embeddings: LiteLLM gateway → `azure-text-embedding-3-large-1` (3072-dim)
- LiteLLM host: `https://dev-gateway.apps.gevernova.net`

### 7.2 FSR Chunking Pipeline (semantic_30_samples.ipynb — 10 cells)

**Data source:** PDF files from Databricks Volume:
```
/Volumes/vgpd/fsr_std_views/fsr_std_vol/FSR_After_2016/FSR_Databricks/
```

**PDF loading:** PyMuPDFLoader (page-by-page extraction)

**Chunking strategy tested:** Semantic chunking via LangChain `SemanticChunker`
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2` (for chunk boundary detection)
- Breakpoint: Percentile (threshold=95)
- Processes 30 sample PDFs
- Outputs: chunk count, avg/std/min/max chunk size per PDF

**Note:** This is the semantic chunking **experiment** notebook. The winning strategy for production was **V3 hierarchical recursive chunking** (chunk_size=4000, overlap=200), not semantic chunking.

### 7.3 Key Insight: Experiment vs App Tables

| What | DS Experiment Tables | App Tables |
|------|---------------------|------------|
| ER chunks | `vaid.ai_sot_field_service_report.er_chunks` | `main.gp_services_sdg_poc.engineering_report_chunk` |
| ER results | `vaid.ai_sot_field_service_report.er_retrieval_results` | — |
| FSR chunks | (local analysis only) | `main.gp_services_sdg_poc.field_service_report_gt_litellm` |
| Vector indexes | — | `main.gp_services_sdg_poc.vs_*_litellm` |

The DS team validated strategies → the app tables were populated separately (likely manual ad-hoc loads). No production-level ingestion code exists.

---

## 8. Data Service Tool Map (T1–T7)

| Tool | Name | Data Source | Access Method |
|------|------|------------|---------------|
| T1 | FSR | `vs_field_service_report_gt_litellm` + `fsr_..._psot` | Vector Search + SQL |
| T2 | ER | `vs_engineering_report_chunk_litellm` + `u_pac` | Vector Search + SQL |
| T3 | IBAT | `IBAT_EQUIPMENT_MST` + `IBAT_PLANT_MST` | SQL only |
| T4 | PRISM | `seg_fmea_wo_models_gen_psot` | SQL only (RE persona only) |
| T5 | Heatmap | `fsr_unit_risk_matrix_view` | CSV or SQL |
| T6 | Retriever | Combines T1 + T2 | Hybrid 3-path parallel |
| T7 | Event Master | `eventmgmt_event_vision_sot` + 2 joined views | SQL only (OE persona only) |

---

## 9. DS Experimentation Summary

> Source: 31 experiment docs in `local/docs/dbx/reference/DS-experimentations/`

### 9.1 Document Index

| ID | File | Topic |
|----|------|-------|
| — | `4-experimentations-overview-v1/v2.pdf` | Master list of all DS experiments in scope for MVP1 |
| 4a | `4a-read-risk-matrix-tool-specs.pdf` | Risk Matrix tool spec (`load_risk_matrix`) |
| 4b | `4b-read-prism-tool-specs.pdf` | PRISM tool spec (`read_prism_by_serial`) |
| 4c | `4c-read-ibat-tool-specs.pdf` | IBAT tool spec (`read_ibat_by_serial`) |
| 4d | `4d-query-er-tool-specs.pdf` | ER query tool spec (`query_er`) |
| 4d | `4d-er-chunking-retrieval-reranking-experimentation.pdf` | **ER chunking + retrieval deep-dive** |
| 4e | `4e-query-fsr-tool-specs.pdf` | FSR query tool spec (`query_fsr`) |
| 4e | `4e-fsr-chunking-retrieval-reranking-experimentation.pdf` | **FSR chunking + retrieval deep-dive** |
| 4f | `4f-re-risk-evaluation-experiment.pdf` | RE risk eval experiment (14 pages, accuracy results) |
| 4g | `4g-read-re-table-tool-specs.pdf` | RE Table read tool spec |
| 4h | `4h-read-event-master-tool-specs.pdf` | Event Master tool spec |
| 4i | `4i-re-narrative-summary-experiment.pdf` | RE Narrative experiment |
| 4j | `4j-read-re-report-tool-specs.pdf` | RE Report read tool spec |
| 4k | `4k-oe-event-history-key-findings-experiment.pdf` | OE Event History experiment |
| 4l | `4l-oe-read-event-report-tool-specs.pdf` | OE Event Report read tool spec |
| 4m | `4m-oe-risk-evaluation-experiment.pdf` | OE risk eval experiment |
| 4n | `4n-read-oe-table-tool-specs.pdf` | OE Table read tool spec |
| 4o | `4o-oe-narrative-summary-experiment.pdf` | OE Narrative experiment |
| 4p | `4p-read-oe-report-tool-specs.pdf` | OE Report tool spec |
| — | `4d-er-chunking-retrieval-reranking/er-chunking-experiment.pdf` | ER chunking strategy analysis (48 configs tested) |
| — | `4d-er-chunking-retrieval-reranking/er-oversized-chunks-retrieval.pdf` | Oversized ER chunk (>4K) retrieval test |
| — | `4d-er-chunking-retrieval-reranking/er-retrieval-strategies-technical-doc.pdf` | ER retrieval strategies comparison (BM25/FAISS/Ensemble) |
| — | `4d-er-chunking-retrieval-reranking/er-retrieval-metrics-analysis.pdf` | ER retrieval metrics at K=3,5,7,10 |
| — | `4d-er-chunking-retrieval-reranking/er-retrieval-experimentation-process.pdf` | ER experimentation pipeline user guide |
| — | `4e-fsr-chunking-retrieval-reranking/fsr-retrieval-dbr-implementation.pdf` | FSR retrieval on Databricks (evaluation notebook) |
| — | `4e-fsr-chunking-retrieval-reranking/fsr-retrieval-e2e-pipeline-local.pdf` | FSR retrieval local pipeline (full code path) |
| — | `fsr-structured-data-primary-key.pdf` | FSR `(event_id, esn)` primary key analysis |
| — | `4e-fsr-chunking-retrieval-reranking/section-based-chunking-analysis.pdf` | Non-recursive subsection chunking stats |
| — | `4e-fsr-chunking-retrieval-reranking/semantic-chunking-strategy-experimentation.pdf` | Semantic chunking vs recursive comparison |

### 9.2 ER Chunking — Key Findings

**Dataset:** 551,069 ERs total. 12 unstructured text fields concatenated per ER before chunking.

**Winning config:** ER-level chunking, 4K token limit, 10% overlap.

| Parameter | Chosen Value | Why |
|-----------|-------------|-----|
| Strategy | ER-level (not sliding window) | Preserves ER boundaries; 1 ER = 1 chunk unless it's too long |
| Token limit | 4,096 | Most ERs < 400 tokens; only outliers need splitting |
| Overlap | 10% | Prevents key phrases from being lost at chunk boundaries |
| Metadata | Preserved in every chunk | `serial_number`, `er_number`, `opened_at`, `status`, etc. |

**Key insight:** Chunking is done **per serial**, not globally. Users filter by ESN first, then search within that serial's ERs.

**Oversized chunks (>4K):** Tested separately — chunk_index & metadata correctly preserved; overlaps within chunks responded well to retrieval.

### 9.3 FSR Chunking — Key Findings

**Strategies tested:** Page-based, section, sub-section (L1/L2), paragraph, recursive, semantic.

| Strategy | 54-page FSR | 306-page FSR | Notes |
|----------|------------|-------------|-------|
| Page (0) | 5 min | 10 min | Simple but ignores section boundaries |
| Section (1) | 35 min | 20 min | Slower due to Foundation Service overhead |
| Sub-section L1 (2) | 1h 20m | 5h | Diminishing returns |
| Sub-section L2 (3) | 1h 45m | 6h 30m | Very slow |
| **Recursive (custom)** | **10–20 sec** | **10–20 sec** | **Winner — hierarchical split then merge** |
| Semantic | Viable | Viable | GPU-intensive, marginal quality gain |

**Winning config:** V3 hierarchical recursive chunking.
- `chunk_size = 4000`, `chunk_overlap = 200`, `max_depth = 5`
- Splits by section → subsection → sub-subsection, then `RecursiveCharacterTextSplitter`
- Merges small consecutive chunks up to `chunk_size`
- Preserves section path metadata (`section_1` through `section_5`)

**Section-based (non-recursive) comparison:**
- 759 total chunks across 30 PDFs, avg 25.3 chunks/report
- Median chunk = 552 chars, but max = 218K chars — extreme variability
- Recursive is preferred because it normalizes chunk sizes for better embedding quality

**Semantic chunking verdict:** Significantly more compute-intensive (embeds every sentence). Justified only if retrieval accuracy materially improves — not chosen for MVP1.

### 9.4 Retrieval Strategy — ER Results

**Retrievers compared:** BM25 (keyword), FAISS (semantic), Ensemble (hybrid).

**Recall@K across 7 serials, 84 queries:**

| K | BM25 | Ensemble | FAISS |
|---|------|----------|-------|
| 3 | 78.6% | 75.0% | 64.3% |
| 5 | 83.3% | 83.3% | 82.1% |
| 7 | 84.5% | 86.9% | 85.7% |
| 10 | 89.3% | 89.3% | **90.5%** |

- **K=3 doesn't meet 85% recall target** — K≥7 required
- FAISS weakest at low K (needs semantic mass), strongest at K=10
- **Ensemble (hybrid) is most robust** — leads in FirstRight@K (51.2%)
- **Reranking had minimal effect** with Jaccard scorer — cross-encoder reranker recommended

### 9.5 Retrieval Strategy — FSR Results (Databricks)

**Evaluation modes tested:** ANN, ANN+reranking, Hybrid, Hybrid+reranking.

**Best result:** Custom Hybrid R@20 = 88.6%, DBR Hybrid+criteria R@10 = 78.8%.

**Key config:** HYBRID query type combining `query_text` + `query_vector` via Databricks Vector Search API.

**Embedding migration:** Moved from Databricks-managed `databricks-gte-large-en` to self-managed `azure-text-embedding-3-large-1` (3072-dim) via LiteLLM. Both ER and FSR indexes rebuilt.

### 9.6 FSR SOT Primary Key Analysis

**Source table:** `vgpp.fsr_std_views.fsr_field_vision_field_services_report_psot` (35,251 rows)

**Near-valid primary key:** `(event_id, esn)` — works on 99.5% of rows (35,079/35,251).
- 86 duplicate pairs (172 rows) differ almost exclusively in `report_unit_status` (status progression: Started→Completed, etc.)
- 2,003 rows have NULL `esn` — each `event_id` appears only once with NULL
- **Dedup strategy in code:** Prefer Completed > Started > Not Started > Hold

### 9.7 Risk Evaluation Experiments

**RE persona (4f):** 42 Rotor/Stator issues, tested across 26–33 ESNs.

| Run | ESNs | K | Model | Accuracy |
|-----|------|---|-------|----------|
| Exp 1, Run 1 | 7 | 10 | azure-gpt-4o | 71.4% |
| Exp 1, Run 4 | 7 | 10 | **azure-gpt-5-2** | **85.7%** |
| Final (26 ESN, k=20) | 26 | 20 | azure-gpt-5-2 | **81.68%** |

- GPT-5-2 chosen for balance of accuracy + API stability
- k=20 vs k=10: +2.01% accuracy but +1.9% false positives
- Biggest gap: Not Mentioned vs Light (both score=1) — accounts for 50% of "errors"
- If NM+Light merged: effective accuracy ~90%+

**OE persona (4m):** 12 "Other Repairs" issues.
- 27-ESN run: 65.1% accuracy, 25.3% FP rate — model over-predicts severity
- Major FP contributor: Bearings (16 false positives)
- Med severity never predicted correctly (0% F1)

---

## 10. Open Questions

1. **Where does the chunking pipeline live?** (Databricks notebooks? Separate repo?)
2. **How often are vector indexes refreshed** from SOT tables?
3. **Is FSR Doc(Δ) in Feng's table counting distinct documents or distinct chunks?** (If documents, "Δ>SOT" means extra docs exist in delta beyond the current SOT view)
4. **Why is vgpd missing data for ESNs that vgpp has?** Is the dev catalog actively maintained or is it a snapshot?
5. **What are `eng_std_views` and `fsr_sox_std_views` used for?** Visible in catalog but zero code references.
6. **No sync mechanism documented** between SOT tables and vector indexes — how is staleness managed?
