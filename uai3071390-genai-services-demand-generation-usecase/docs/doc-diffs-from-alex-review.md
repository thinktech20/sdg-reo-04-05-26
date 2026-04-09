# Documentation Diffs — Alex Pipeline Review (2026-04-09)

Findings from reviewing Alex's FSR pipeline code vs. existing docs 01–08 and ADRs.
Source review: `databricks_layer/docs/reviews/09-Apr-alex-fsr-pipeline-review.md`

**Docs that need NO changes:** 01-project-overview, 05-app-code-analysis, ADR-001, ADR-005, ADR README

---

## Finding Reference

| ID | Description |
|---|---|
| A | Embedding model mismatch: POC ingest uses `databricks-gte-large-en` (VS auto-embed); production target uses `azure-text-embedding-3-large-1` via LiteLLM for both ingest+query |
| C | ESN identification is 4-layer (not "LLM + regex"): regex on first 2 pages → filename parsing → LLM (GPT-4o) → ref view join (takes priority) |
| D | No `embedding` column in Delta table — VS auto-embeds at sync time; embedding is never stored in Delta in current POC |
| F | Reranking hurts Recall@1 and Recall@3. New eval: hybrid_retrieval R@1=0.432, hybrid_reranking R@1=0.303. Helps at k≥5 only. |
| G | Steps 5 (chunk hydration) and 6 (3-view metadata join at query time) are NOT in Alex's code. `fsr_scraped_file_mapping_ref` exists but is disconnected from retrieval. |
| H | Two parallel pipelines exist: `fsr_pipeline` (full corpus) and `fsr_pipeline_gt_direct` (30-ESN GT subset) |
| I | Scraping pipeline POC output is `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref`, not `vgpd.fsr_std_views...` |
| K | `fsr_pipeline/src/experiments.py` has broken imports — would fail at runtime |

---

## 02-fsr-findings.md

### Diff 1 — `embedding` column (Finding D)

**Code citation:** `delta_store.py:L236-L246` — `_delta_schema()` defines the Delta table schema; there is no `embedding` or `chunk_embedding` field in the schema definition. `config.py:L138` defines `EMBEDDING_VECTOR_COLUMN = "embeddings"` but this variable is never passed to `build_delta_rows` or `save_rows_to_delta`. `pipeline.py:L783-L793` confirms that Step 3 simply triggers a VS delta-sync (`_sync_vs_index()`); no embedding array is written to Delta at any prior step.

**PDF spec reference:** [Query FSR Spec §Data Sources — Primary Vector Search Table] states: "Self-managed Azure OpenAI embedding written during ingestion and indexed in Vector Search. This field is not returned to the caller." The spec envisions an `embedding ARRAY` column; the POC does not implement this.

**Assessment: ⚠️ CONCERN**
The spec requires embeddings to be stored in the Delta table for a self-managed VS index, but the current POC delegates embedding to VS at sync time using a Databricks-managed model (`databricks-gte-large-en`). This is architecturally intentional for the POC but is a gap vs. production spec and must be closed before moving to a self-managed LiteLLM index. It is not a bug in the current POC context but is a real production blocker.

**Current:**
```
embedding         = 3072-dim Azure OpenAI vector (stored at ingestion, NOT returned to callers)
```
**Should be:**
Remove this row entirely. Add note:
> No `embedding` column: VS auto-embeds `chunk_text` during index sync using `databricks-gte-large-en`. No embedding vector is stored in the Delta table in the current POC. Production target requires an embedding array written to a Delta column for use with a self-managed VS index.

---

### Diff 2 — ESN description (Finding C)

**Code citation:** `pdf_processor.py:L40-L55` — the 7 regex patterns applied to the first 2 PDF pages (priority order: `ESN/SY:`, `ESN:`, `Equipment Serial Number:`, `Serial Number:`, `Generator Serial:`, `Unit Serial Number:`, `GAS TURBINE (`). `pdf_processor.py:L64-L81` — filename parsing (`_extract_esn_from_filename`): splits stem on spaces/underscores, accepts first token matching `[A-Z0-9]{4,12}` and not a date. `esn_identifier.py:L27-L31` — LLM model (`azure-gpt-4o`) and qualification thresholds (`MIN_ESN_COUNT = 1`, `MIN_ESN_FRACTION = 0.10`). `delta_store.py:L181-L223` — `load_ref_view_lookup()` loads `vgpd.fsr_std_views.fsr_pdf_ref` and joins on UUID stem; ref view ESNs and dates take priority over all previous layers via `build_delta_rows:L293` (`final_esns = _dedupe_esn_values(ref_esns, esn_labels)` with ref first).

**PDF spec reference:** [Query FSR Spec §Acceptance Criteria] states: "ESN extraction uses LLM + regex identification from report text." The spec simplifies the actual 4-layer implementation. [Data Extraction Spec §Stage 2] describes LLM-assisted extraction as the normalization step, which aligns with Layer 3.

**Assessment: ✅ ACCEPTABLE**
The 4-layer approach is a sensible and robust engineering choice that goes beyond the minimal spec description. The fallback chain (regex → filename → LLM → ref view) ensures higher ESN coverage than LLM + regex alone. The ref view taking priority is correct because `fsr_pdf_ref` is the authoritative enterprise source. No correctness risk — only the documentation needs to reflect the actual implementation.

**Current:**
```
generator_serial  = ESN extracted via LLM + regex (nullable; row duplicated per ESN for multi-ESN chunks)
```
**Should be:**
```
generator_serial  = ESN extracted via 4-layer process: (1) regex on first 2 pages (7 patterns in
                    priority order: ESN/SY:, ESN:, Equipment Serial Number:, Serial Number:,
                    Generator Serial:, Unit Serial Number:, GAS TURBINE(); (2) filename parsing
                    (UUID first token matching [A-Z0-9]{4,12}, not a date); (3) LLM (azure-gpt-4o)
                    over full document text — returns {ESN: count} JSON, qualified if count ≥ 1
                    AND count/total ≥ 10%; (4) ref view join on fsr_pdf_ref.s3_filename (takes
                    priority over layers 1-3; also provides report_date). Nullable; row
                    duplicated per ESN for multi-ESN chunks (chunk_id suffixed __{esn}).
```

---

### Diff 3 — Retrieval eval table (Finding F)

**Code citation:** `fsr_pipeline_gt_direct/src/evaluate_retrieval.py:L712-L718` — defines the four eval modes: `ann_retrieval`, `ann_reranking`, `hybrid_retrieval`, `hybrid_reranking`. `evaluate_retrieval.py:L816-L821` — recall is computed as binary (1.0 if any match in top-k, else 0.0). `evaluate_retrieval.py:L86-L88` — `PAGE_WINDOW = 10`: a hit is counted when the cited page falls within `[page_number, page_number + 10]`. `fsr_pipeline_gt_direct/run_pipeline.py:L197` — `EVAL_MAX_K = 20`.

**PDF spec reference:** [Query FSR Spec §Retrieval Validation Snapshot] documents the earlier evaluation metrics: "DBR built-in HYBRID + criteria achieved Recall@1 = 45.5, Recall@5 = 67.4, and Recall@10 = 78.8." The new eval run from Alex's `fsr_pipeline_gt_direct` provides updated numbers under a different (non-criteria) query variant. [Query FSR Spec §Step 4 — Reranking] mandates unconditional reranking; this eval data challenges that decision.

**Assessment: ⚠️ CONCERN**
The new eval numbers show hybrid without reranking outperforming hybrid with reranking at k=1 (0.432 vs 0.303). This is a meaningful finding because the spec mandates unconditional reranking (Step 4). Applying reranking unconditionally will systematically hurt top-1 retrieval quality, which matters for RE Risk Evaluation Chain. The finding is not a code bug, but it surfaces a spec decision that needs revisiting — making it a concern rather than merely acceptable.

**Current table includes:**
```
| DBR HYBRID     | Y | 45.5 | 67.4 | 78.8 | 84.8 |
| DBR Reranked   | Y | 19.7 | 56.1 | 73.5 | 86.4 |
```
**Add footnote below table:**
> Updated eval (2026-04-09, Alex's `fsr_pipeline_gt_direct`, 132 serial/issue pairs, `issue_prompt_only` variant):
> hybrid_retrieval R@1=0.432, R@5=0.667, R@20=0.841
> hybrid_reranking R@1=0.303, R@5=0.667, R@20=0.841
> Reranking hurts at k≤3, is neutral at k=5, and is equivalent at k≥20. These numbers use a
> different query variant (no criteria appended) and a 30-ESN GT subset, so they are not directly
> comparable to the earlier table. Reconcile against Alex's evaluation run before finalising
> ADR-003 and the reranking mandate in Step 4 of the spec.

---

### Diff 4 — Ingest embedding model (Finding A)

**Code citation:** `fsr_pipeline/src/config.py:L132-L136` — `VS_INDEX_EMBEDDING_ENDPOINT = "databricks-gte-large-en"` (the model VS uses to auto-embed at sync time) vs. `VECTOR_SEARCH_EMBEDDING_MODEL = "azure-text-embedding-3-large-1"` (the LiteLLM model used for query vectors). `pipeline.py:L291-L306` — `_ensure_vs_index_exists()` creates the index with `embedding_model_endpoint_name: VS_INDEX_EMBEDDING_ENDPOINT` (i.e., `databricks-gte-large-en`). `vector_embeddings.py:L38-L43` — `_LiteLLMEmbeddingClient` uses `VECTOR_SEARCH_EMBEDDING_MODEL` (`azure-text-embedding-3-large-1`) for query embedding.

**PDF spec reference:** [Query FSR Spec §Data Sources — Embedding model] states: "self-managed Azure OpenAI embedding deployment via LiteLLM (current runtime default: azure-text-embedding-3-large-1, 3072-dim)." [Query FSR Spec §Step 2 — Generate query vector internally] confirms the same model must be used for both ingest and query. The current POC violates this.

**Assessment: ❌ WRONG**
The ingest and query paths use different embedding models (`databricks-gte-large-en` for index, `azure-text-embedding-3-large-1` for query). These are different embedding spaces with different dimensionalities. The dense retrieval leg of HYBRID search compares query vectors from `azure-text-embedding-3-large-1` against index vectors from `databricks-gte-large-en`, which is semantically invalid. The spec requires the same model for both. This must be fixed before production and should be flagged as a known POC limitation in documentation. (ADR-002 decision gates the remediation path.)

**Where:** Section describing HYBRID retrieval dense leg.
**Current:**
```
Dense leg: vector similarity against query_vector (Azure OpenAI embedding)
```
**Add note:**
> POC embedding model mismatch (confirmed 2026-04-09): The VS index auto-embeds `chunk_text`
> using `databricks-gte-large-en` (config.py:L133, VS_INDEX_EMBEDDING_ENDPOINT). Query vectors
> are generated using `azure-text-embedding-3-large-1` via LiteLLM (config.py:L135-L136,
> vector_embeddings.py:L38-L43). These are different models in different embedding spaces,
> making the dense retrieval leg of HYBRID semantically inconsistent. Production target
> (per Query FSR Spec §Embedding model) aligns both ingest and query to
> `azure-text-embedding-3-large-1` via a self-managed VS index. Pending ADR-002 decision.

---

### Diff 5 — Steps 5/6 deferred (Finding G)

**Code citation:** `pipeline.py:L396-L474` — `_test_retrieval()` reads directly from the VS response columns `["chunk_id", "pdf_name", "page_number", "chunk_text"]`; there is no secondary Delta lookup by `chunk_id`. `retrieval.py:L20` — `_RETURN_COLUMNS = ["chunk_id", "pdf_name", "page_number", "chunk_text"]`; no join to any metadata view. `delta_store.py:L181-L223` — `load_ref_view_lookup()` joins only `fsr_pdf_ref` at ingest time; `fsr_field_vision_field_services_report_psot` and `fsr_scraped_file_mapping_ref` are never queried. `run_scraping_pipeline.py:L70` — scraping writes to `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref`; this table is never referenced in `fsr_pipeline` or `fsr_pipeline_gt_direct`.

**PDF spec reference:** [Query FSR Spec §Step 5 — Chunk row hydration] requires reloading the full chunk row from Delta by `chunk_id`. [Query FSR Spec §Step 6 — Metadata enrichment] requires runtime joins to all three supplementary views (`fsr_field_vision_field_services_report_psot`, `fsr_pdf_ref`, `fsr_scraped_file_mapping_ref`). [Query FSR Spec §Supplementary: Structured Metadata Views] lists all three views. Neither step is implemented.

**Assessment: ⚠️ CONCERN**
Steps 5 and 6 are explicitly called out in the spec as required for the production `query_fsr` response shape. The grouped response (`chunk`, `fsr_report`, `pdf_ref`, `scraped_mapping`) is the contract callers of the REST tool will receive. Their absence from the current notebook pipeline is an expected POC gap (the spec itself notes this under "Current Experiment vs Production Spec"), but the documentation must clearly mark them as deferred so readers do not assume the spec is implemented. The scraping table being entirely disconnected is the most concrete gap — data exists but is unreachable.

**Where:** Key Implementation Learnings / retrieval pipeline steps.
**Add:**
> Steps 5 (chunk hydration via secondary Delta SQL lookup by chunk_id) and 6 (full 3-view
> metadata join at query time joining fsr_field_vision_field_services_report_psot, fsr_pdf_ref,
> and fsr_scraped_file_mapping_ref) are NOT implemented in the current POC. The retrieval path
> reads directly from the VS response (retrieval.py:L20, pipeline.py:L412).
> `fsr_scraped_file_mapping_ref` is populated by the scraping pipeline
> (run_scraping_pipeline.py:L70) but is not connected to retrieval at any point.
> These are deferred gaps — see doc 08 and Query FSR Spec §Current Experiment vs Production Spec.

---

## 03-fsr-implementation-plan.md

### Diff 1 — VS index sync step (Finding A)

**Code citation:** `config.py:L132-L134` — `VS_INDEX_EMBEDDING_ENDPOINT = "databricks-gte-large-en"`. `pipeline.py:L297-L303` — index is created as `DELTA_SYNC` type with `embedding_source_columns: [{name: "chunk_text", embedding_model_endpoint_name: VS_INDEX_EMBEDDING_ENDPOINT}]`, meaning Databricks manages the embedding at sync time. `fsr_pipeline_gt_direct/src/config.py:L130` — the gt_direct pipeline uses `EMBEDDING_VECTOR_COLUMN = "chunk_embedding"` (a different column name, suggesting a self-managed index was prototyped for the GT subset).

**PDF spec reference:** [Query FSR Spec §Embedding persistence] states: "document embeddings are generated during ingestion, stored in the Delta table, and indexed in Vector Search." [Query FSR Spec §Current Experiment vs Production Spec point 5] explicitly acknowledges the naming discrepancy and confirms the LiteLLM index (`vs_field_service_report_gt_litellm`) is for the 30-ESN subset only.

**Assessment: ⚠️ CONCERN**
The difference between the POC (Databricks-managed GTE embeddings) and the production spec (self-managed LiteLLM embeddings stored in Delta) is a consequential architecture choice, not a simple config tweak. Moving to self-managed requires: (1) generating and storing embeddings at ingest time, (2) rebuilding the VS index as self-managed type, (3) ensuring the same model is used for both. The implementation plan must reflect this as a planned transition rather than implying the current state matches the spec.

**Current (Phase 1, Step 4):**
```
Embedding model: azure-text-embedding-3-large-1 (3072-dim) — configured on the VS index side
```
**Add note after this block:**
> POC vs. Production (2026-04-09): The current POC uses a Delta Sync index where VS auto-embeds
> `chunk_text` using `databricks-gte-large-en` at sync time (config.py:L133,
> pipeline.py:L297-L303). No embedding array is written to the Delta table during ingestion.
> Production target per Query FSR Spec §Embedding persistence: self-managed VS index where both
> ingest and query use `azure-text-embedding-3-large-1` via LiteLLM, with embedding arrays
> written to a Delta column before index sync. This transition is a key production build decision
> pending ADR-002. The `fsr_pipeline_gt_direct` config (gt_direct/config.py:L130) references
> `EMBEDDING_VECTOR_COLUMN = "chunk_embedding"`, suggesting a self-managed index was prototyped
> for the 30-ESN GT subset.

---

### Diff 2 — ESN extraction step (Finding C)

**Code citation:** `pdf_processor.py:L40-L55` (7 regex patterns), `pdf_processor.py:L64-L81` (filename parsing), `esn_identifier.py:L27-L63` (LLM call with GPT-4o, `MIN_ESN_COUNT = 1`, `MIN_ESN_FRACTION = 0.10`), `delta_store.py:L181-L223` (ref view join at ingest time, ref results prefixed first in `_dedupe_esn_values`). `delta_store.py:L307-L318` — multi-ESN chunks: when `len(final_esns) > 1`, one row is written per ESN with `chunk_id = f"{doc_id}_{chunk_index}__{esn}"`.

**PDF spec reference:** [Query FSR Spec §Acceptance Criteria] states: "ESN extraction uses LLM + regex identification from report text" and "Multi-ESN chunks are duplicated at ingestion time (one row per ESN) so generator_serial filter works for all tagged ESNs." [Data Extraction Spec §Stage 2] describes LLM-based normalization, which corresponds to Layer 3.

**Assessment: ✅ ACCEPTABLE**
The 4-layer approach correctly implements the spec's intent (ESN identification + multi-ESN row expansion) while being more robust. The ref view join is the right prioritization choice because `fsr_pdf_ref` is the authoritative enterprise record. The `chunk_id` suffix format `__{esn}` for multi-ESN chunks matches the spec's documented format. Only the documentation needs updating.

**Current:**
```
2. ESN Extraction
   - LLM + regex identification of generator_serial from chunk_text
   - Multi-ESN chunks: duplicate row per ESN
   - Join vgpd.fsr_std_views.fsr_pdf_ref to backfill generator_serial and report_date
```
**Should be:**
```
2. ESN Extraction (4-layer)
   Layer 1: Regex on first 2 pages — 7 patterns in priority order
            (pdf_processor.py:L40-L55: ESN/SY:, ESN:, Equipment Serial Number:,
            Serial Number:, Generator Serial:, Unit Serial Number:, GAS TURBINE()
   Layer 2: Filename parsing — first token of PDF stem if matches [A-Z0-9]{4,12}
            and is not a pure-numeric date sequence (pdf_processor.py:L64-L81)
   Layer 3: LLM (azure-gpt-4o via LiteLLM) — full document text →
            {ESN: count} JSON (esn_identifier.py:L293-L358);
            qualified if count ≥ MIN_ESN_COUNT=1 AND count/total ≥ MIN_ESN_FRACTION=10%
            (esn_identifier.py:L30-L31, L373-L387)
   Layer 4: Ref view join — vgpd.fsr_std_views.fsr_pdf_ref on s3_filename UUID stem
            (delta_store.py:L181-L223); ref ESNs take priority over layers 1-3
            and also supply report_date
   Multi-ESN: one Delta row per ESN per chunk; chunk_id format: {doc_id}_{chunk_index}__{esn}
            (delta_store.py:L307-L312)
```

---

### Diff 3 — Steps 5 and 6 (Finding G)

**Code citation:** `pipeline.py:L396-L474` — retrieval smoke test reads directly from VS response columns; no chunk hydration step. `retrieval.py:L20` — `_RETURN_COLUMNS` contains only `["chunk_id", "pdf_name", "page_number", "chunk_text"]`; no metadata join. `run_scraping_pipeline.py:L70` — scraping output table is `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref`; no code in `fsr_pipeline` or `fsr_pipeline_gt_direct` reads from this table.

**PDF spec reference:** [Query FSR Spec §Step 5 — Chunk row hydration] and [Query FSR Spec §Step 6 — Metadata enrichment] describe both steps as required for the production response shape. [Query FSR Spec §Current Experiment vs Production Spec point 3] explicitly states these are not implemented in the current experiment.

**Assessment: ✅ ACCEPTABLE**
The spec itself acknowledges Steps 5 and 6 are not implemented in the current notebook experiment. This is a known, documented gap between POC and production. The concern is only that implementation plan docs may read as if these steps are complete — they must be explicitly marked as deferred.

**Current:** Steps 5 and 6 are listed as standard pipeline steps.
**Mark each as:**
> [NOT IN CURRENT POC — deferred to production build]

**Add note:**
> As of 2026-04-09, only `fsr_pdf_ref` is joined — at ingest time, not query time
> (delta_store.py:L181-L223). Neither `fsr_scraped_file_mapping_ref` nor
> `fsr_field_vision_field_services_report_psot` is queried at any point in the current pipeline.
> Steps 5-6 are implementation items for the production REST service (DEV team scope per
> Query FSR Spec §Current Experiment vs Production Spec). The scraping pipeline populates the
> table (run_scraping_pipeline.py:L70) but it is not yet connected.

---

### Diff 4 — Pipeline variants (Finding H)

**Code citation:** `fsr_pipeline/src/config.py:L118-L130` — `EMBEDDINGS_TABLE = "main.gp_services_sdg_poc.field_service_report"`, `VS_INDEX_NAME = "main.gp_services_sdg_poc.vs_field_service_report"`. `fsr_pipeline_gt_direct/src/config.py:L117-L129` — `EMBEDDINGS_TABLE = "main.gp_services_sdg_poc.field_service_report_gt_litellm"`, `VS_INDEX_NAME = "main.gp_services_sdg_poc.vs_field_service_report_gt_litellm"`. `fsr_pipeline/src/config.py:L109-L114` — 4 volume paths (includes `UAT_Files`). `fsr_pipeline_gt_direct/src/config.py:L109-L113` — 3 volume paths (no `UAT_Files`).

**PDF spec reference:** [Query FSR Spec §Data Sources — Current experiment 30-ESN LiteLLM subset] states: "it was created as a focused 30-ESN ground-truth evaluation set for REChain retrieval testing and self-managed LiteLLM embedding validation. It is not the full FSR corpus." [Query FSR Spec §Data Sources] distinguishes the full corpus index (`vs_field_service_report`) from the GT subset index (`vs_field_service_report_gt_litellm`).

**Assessment: ✅ ACCEPTABLE**
Having two separate pipelines for full-corpus vs. GT-subset evaluation is a reasonable experimental design. The spec itself documents the existence of both. The risk is reader confusion about which pipeline is "the" pipeline. Documentation should clearly state the boundary and purpose of each.

**Where:** Entry Point section.
**Add:**
> Two parallel pipeline variants exist as of 2026-04-09:
> - `fsr_pipeline` (fsr_pipeline/src/config.py:L118-L130): Full-corpus ingestion, targets
>   `main.gp_services_sdg_poc.field_service_report` and
>   `main.gp_services_sdg_poc.vs_field_service_report`; scans 4 volume paths (incl. UAT_Files);
>   auto-creates VS index; includes retrieval smoke test only (no ground-truth eval harness).
> - `fsr_pipeline_gt_direct` (fsr_pipeline_gt_direct/src/config.py:L117-L129): 30-ESN
>   ground-truth evaluation subset; targets `field_service_report_gt_litellm` and
>   `vs_field_service_report_gt_litellm`; scans 3 volume paths; full ground-truth eval harness
>   (Recall@K, Precision@K, 4 modes). The LiteLLM VS index for the GT subset was validated
>   separately per Query FSR Spec §Data Sources.

---

## 04-data-catalog.md

### Diff 1 — Embedding Configuration table (Finding A + D)

**Code citation:** `config.py:L132-L137` — `VS_INDEX_EMBEDDING_ENDPOINT = "databricks-gte-large-en"` (ingest) vs. `VECTOR_SEARCH_EMBEDDING_MODEL = "azure-text-embedding-3-large-1"` (query). `vector_embeddings.py:L100-L111` — `_CLIENT = _LiteLLMEmbeddingClient()` is module-level; `get_query_vector()` wraps `_cached_query_vector()` with `@lru_cache(maxsize=512)`. `delta_store.py:L236-L246` — `_delta_schema()` has no embedding field. `fsr_pipeline_gt_direct/src/config.py:L130` — `EMBEDDING_VECTOR_COLUMN = "chunk_embedding"` (gt_direct differs; `embeddings` in main pipeline config:L138).

**PDF spec reference:** [Query FSR Spec §Data Sources — Embedding model] and [Query FSR Spec §Embedding persistence] define the production state: same model for both ingest and query, stored in Delta. The current POC state is explicitly noted as different in [Query FSR Spec §Current Experiment vs Production Spec point 5].

**Assessment: ❌ WRONG**
The embedding vector column name is also inconsistent between the two configs: `fsr_pipeline/config.py:L138` defines `EMBEDDING_VECTOR_COLUMN = "embeddings"` while `fsr_pipeline_gt_direct/config.py:L130` defines it as `"chunk_embedding"`. Neither is actually written to the Delta table in the current POC (as confirmed by `_delta_schema()`), but these mismatched variable names are misleading and could cause errors if a future developer assumes a column name from config.

**Current:**
```
| Persistence | Stored in Delta table at ingestion; indexed in VS; generated fresh at query time |
```
**Should be split into POC vs. Production:**
```
| Ingest (POC)   | NOT stored in Delta — VS auto-embeds chunk_text using databricks-gte-large-en
|                | at sync time (config.py:L133, pipeline.py:L297-L303)
| Query (POC)    | azure-text-embedding-3-large-1 via LiteLLM — generated per request,
|                | cached lru_cache(maxsize=512) (vector_embeddings.py:L103-L111)
| Ingest (Prod)  | azure-text-embedding-3-large-1 via LiteLLM — embedding array written to
|                | Delta column before VS index sync (production target, not yet implemented)
| Query (Prod)   | azure-text-embedding-3-large-1 via LiteLLM — same model as ingest
|                | (consistent embedding space per Query FSR Spec §Embedding model)
```

---

### Diff 2 — "No embedding column" note (Finding A)

**Code citation:** `config.py:L132-L134` — `VS_INDEX_EMBEDDING_ENDPOINT = "databricks-gte-large-en"`. Note: `config.py:L138` defines `EMBEDDING_VECTOR_COLUMN = "embeddings"` but this is not written to Delta by any current code path.

**PDF spec reference:** [Query FSR Spec §Data Sources column table] lists the `embedding` column as `ARRAY` type with note: "Self-managed Azure OpenAI embedding written during ingestion and indexed in Vector Search. This field is not returned to the caller."

**Assessment: ⚠️ CONCERN**
The config defines `EMBEDDING_VECTOR_COLUMN` but the variable is effectively dead code in the current pipeline — it is never passed to `build_delta_rows` or `save_rows_to_delta`. This creates confusion for anyone reading the config and assuming an embedding column exists. It should be either removed or clearly commented as a future-state variable.

**Current note:**
```
model: azure-text-embedding-3-large-1, configured on the VS index side
```
**Add:**
> (POC actual: VS index uses `databricks-gte-large-en` — config.py:L133.
> Production target: `azure-text-embedding-3-large-1` — config.py:L135-L136.
> These are different embedding spaces; EMBEDDING_VECTOR_COLUMN in config.py:L138
> is defined but not written to Delta in the current POC.)

---

### Diff 3 — Experiment tables (Finding D + H)

**Code citation:** `fsr_pipeline/src/config.py:L118-L130` — table and index names. `fsr_pipeline_gt_direct/src/config.py:L117-L129` — GT subset table and index names.

**PDF spec reference:** [Query FSR Spec §Data Sources] documents both the full corpus table (`main.gp_services_sdg_poc.field_service_report`) and the GT LiteLLM subset table (`main.gp_services_sdg_poc.field_service_report_gt_litellm`), explaining the purpose of each.

**Assessment: ✅ ACCEPTABLE**
The table catalog simply needs to reflect reality. Both tables and both VS indexes exist for legitimate purposes and the spec documents them both.

**Current:**
```
| main.gp_services_sdg_poc.field_service_report | Full FSR corpus (chunks + embeddings) |
```
**Should be:**
```
| main.gp_services_sdg_poc.field_service_report | Full FSR corpus (chunks only — no embedding
|                                               | column; VS auto-embeds at sync time via
|                                               | databricks-gte-large-en; config.py:L118-L133) |
```
**Add missing rows:**
```
| main.gp_services_sdg_poc.vs_field_service_report         | Full-corpus VS Delta Sync index
|                                                           | (databricks-gte-large-en;
|                                                           | config.py:L128-L133)               |
| main.gp_services_sdg_poc.field_service_report_gt_litellm | 30-ESN GT subset table (chunks only;
|                                                           | gt_direct/config.py:L117-L119)      |
| main.gp_services_sdg_poc.vs_field_service_report_gt_litellm | 30-ESN GT subset VS index
|                                                           | (gt_direct/config.py:L127-L129)     |
```

---

## 06-pipeline-code-analysis.md

### Diff 1 — ESN count threshold (Finding C)

**Code citation:** `esn_identifier.py:L30-L31`:
```python
MIN_ESN_COUNT = 1
MIN_ESN_FRACTION = 0.10
```
`esn_identifier.py:L373-L387` — `_qualify_esn_counts()` applies both thresholds: `count >= min_count and (count / total_mentions) >= min_fraction`.

**PDF spec reference:** [Data Extraction Spec §Stage 2 — Normalization] describes LLM-based qualification but does not specify numeric thresholds. [Query FSR Spec §Acceptance Criteria] states: "ESN extraction uses LLM + regex identification from report text" without specifying thresholds. The thresholds are an implementation detail not defined in either spec PDF.

**Assessment: ❌ WRONG**
Doc 06 states the wrong threshold value (≥ 5 instead of ≥ 1). This is a factual error in the documentation, not an ambiguity. `esn_identifier.py:L30` is explicit: `MIN_ESN_COUNT = 1`. The documentation will mislead anyone trying to understand or reproduce the ESN qualification logic. This must be corrected.

**Current:**
```
Filter: keep ESNs where count ≥ MIN_ESN_COUNT=5 AND fraction ≥ MIN_ESN_FRACTION=10%
```
**VERIFIED (2026-04-09): `esn_identifier.py:L30-L31`:**
```python
MIN_ESN_COUNT = 1
MIN_ESN_FRACTION = 0.10
```
**Doc 06 is wrong — threshold is count ≥ 1, not ≥ 5.**
**Should be:**
```
Filter: keep ESNs where count ≥ MIN_ESN_COUNT=1 AND fraction ≥ MIN_ESN_FRACTION=10%
(esn_identifier.py:L30-L31, enforced in _qualify_esn_counts():L373-L387)
```
Apply this correction in both doc 02 and doc 06.

---

### Diff 2 — ESN "3-phase" → "4-layer" (Finding C)

**Code citation:** `pdf_processor.py:L84-L134` — `_extract_esn_from_pdf()` and `_extract_esn_from_snapshot()` implement Layers 1 and 2 (regex on first 2 pages + filename fallback). `esn_identifier.py:L293-L365` — `analyze_prepared_document_text_for_esn_counts()` implements Layer 3 (LLM call). `delta_store.py:L181-L223` — `load_ref_view_lookup()` implements Layer 4 (ref view join). `pdf_processor.py:L191-L263` — `process_single_pdf_with_background_doc_analysis()` orchestrates the overlap of LLM analysis with chunking via a background `ThreadPoolExecutor`.

**PDF spec reference:** [Data Extraction Spec §Stage 1 — PDF Extraction] describes first-page field extraction including ESN fields. [Data Extraction Spec §Stage 2 — Data Normalization] describes LLM normalization. The actual 4-layer approach in Alex's code is more sophisticated than either spec describes.

**Assessment: ✅ ACCEPTABLE**
The 4-layer design is correct and more robust than the documented "3-phase" approach. The background thread for LLM analysis (pdf_processor.py:L229-L231) is a well-engineered optimization that overlaps I/O-bound LLM calls with CPU-bound chunking. Only the documentation needs updating to reflect the actual implementation.

**Current:**
```
3-phase approach:
1. One LLM call per document ...
```
**Should be:**
```
4-layer approach:
Layer 1: Regex on first 2 pages — 7 patterns in priority order
         (pdf_processor.py:L40-L55, called from _extract_esn_from_snapshot():L119-L134)
Layer 2: Filename parsing — first token of PDF stem if matches [A-Z0-9]{4,12}
         and is not a pure-numeric date string (pdf_processor.py:L64-L81)
Layer 3: LLM (azure-gpt-4o) — [existing content for phases 1-4, updated with
         correct MIN_ESN_COUNT=1 threshold; see esn_identifier.py:L27-L31, L293-L365]
         Note: LLM call overlaps with chunking via background ThreadPoolExecutor
         (pdf_processor.py:L229-L231)
Layer 4: Ref view join — vgpd.fsr_std_views.fsr_pdf_ref on UUID stem
         (delta_store.py:L181-L223); ref ESNs are placed first in _dedupe_esn_values
         and thus override all previous layers; also supplies report_date
```

---

### Diff 3 — Embedding architecture table (Finding A)

**Code citation:** `config.py:L132-L137` — dual embedding configuration. `pipeline.py:L291-L306` — VS index creation spec sets `embedding_model_endpoint_name = VS_INDEX_EMBEDDING_ENDPOINT` (`databricks-gte-large-en`).

**PDF spec reference:** [Query FSR Spec §Step 3 — Vector Search retrieval] states: "Execute a native Databricks Vector Search query against the self-managed VS index, passing both query_text and the internally generated query_vector." A self-managed index requires the embedding to be pre-computed and stored — the current auto-embed Delta Sync setup is not self-managed in the spec's terminology.

**Assessment: ❌ WRONG**
The documentation table shows `azure-text-embedding-3-large-1` for the Delta-to-VS sync step, which is factually incorrect for the current POC. Readers of this table will incorrectly conclude the embedding pipeline is already consistent. This is a documentation error that will cause confusion when the team attempts to reproduce or extend the POC.

**Current:**
```
| Delta → VS index sync | Databricks VS | azure-text-embedding-3-large-1 (configured on VS) | During index sync |
```
**Should be:**
```
| Delta → VS index sync | Databricks VS | databricks-gte-large-en (POC — config.py:L133) /
|                       |               | azure-text-embedding-3-large-1 via LiteLLM
|                       |               | (production target — config.py:L135-L136) | During index sync |
```

---

### Diff 4 — Broken experiments.py (Finding K)

**Code citation:** `fsr_pipeline/src/experiments.py:L14-L18`:
```python
from retrieval import (
    BM25RetrieverWrapper,
    VectorSearchRetriever,
    WeightedEnsembleRetriever,
    rerank_by_keywords,
)
```
`fsr_pipeline/src/retrieval.py` — the entire file defines only `hybrid_search()`, `search_by_document()`, and `search_with_context()`. None of the four imported names exist anywhere in `retrieval.py`.

**PDF spec reference:** [Not in spec docs] — `experiments.py` is an internal pipeline file not referenced in either spec PDF.

**Assessment: ❌ WRONG**
This will raise `ImportError` the moment `experiments.py` is imported. Since `run_pipeline.py:L251-L252` calls `from evaluate_retrieval import evaluate_all` (which is in `fsr_pipeline_gt_direct`, not `fsr_pipeline`), and `experiments.py` is in `fsr_pipeline/src/`, a developer who tries to use `experiments.py` directly will hit an immediate hard failure. The file is a dead leftover from a local BM25/FAISS ensemble experiment and should be removed or replaced before any automated pipeline runs.

**Add new section at end of doc:**
```
## Known Code Quality Issue — Broken experiments.py

`fsr_pipeline/src/experiments.py:L14-L18` contains four broken imports:
- `BM25RetrieverWrapper` — does not exist in retrieval.py
- `VectorSearchRetriever` — does not exist in retrieval.py
- `WeightedEnsembleRetriever` — does not exist in retrieval.py
- `rerank_by_keywords` — does not exist in retrieval.py

`retrieval.py` only exports: `hybrid_search`, `search_by_document`, `search_with_context`.

This file will fail with `ImportError` at import time. It appears to be a leftover from a
local BM25/FAISS weighted ensemble experiment phase that was superseded by native Databricks
VS hybrid search. The `RetrievalExperiment` class in experiments.py (lines 25-177) is also
dead code — it instantiates the non-existent `BM25RetrieverWrapper` and `VectorSearchRetriever`.

Additionally, `fsr_pipeline/run_pipeline.py:L251-L252` imports `evaluate_retrieval` which only
exists in `fsr_pipeline_gt_direct/src/`, not in `fsr_pipeline/src/`. This will fail when
`RUN_EVALUATION=True` in the main pipeline.

Flag both for cleanup before any automated evaluation runs.
```

---

## 07-fsr-metadata-extraction.md

### Diff 1 — Output table name (Finding I)

**Code citation:** `fsr_scraping/run_scraping_pipeline.py:L70` — `OUTPUT_TABLE = _get_runtime_param("FSR_OUTPUT_TABLE", "main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref")`. The default output is `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref`, not `vgpd.fsr_std_views.fsr_scraped_file_mapping_ref`.

**PDF spec reference:** [Query FSR Spec §Supplementary: Structured Metadata Views, row 3] lists `vgpd.fsr_std_views.fsr_scraped_file_mapping_ref` as the production target. The current scraping pipeline writes to the POC location in `main.gp_services_sdg_poc.*`.

**Assessment: ⚠️ CONCERN**
The output table name mismatch between POC and production is a real operational risk. Any retrieval code that tries to join the production view (`vgpd.fsr_std_views.fsr_scraped_file_mapping_ref`) will find no data because the scraping pipeline currently writes to a different catalog/schema. This needs to be explicitly called out and a promotion/migration path defined before production.

**Current:**
```
Its output populates vgpd.fsr_std_views.fsr_scraped_file_mapping_ref
```
**Should be:**
```
POC output: main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref
            (run_scraping_pipeline.py:L70 — default runtime parameter)
Production target: vgpd.fsr_std_views.fsr_scraped_file_mapping_ref
            (Query FSR Spec §Supplementary Metadata Views, row 3)
A promotion step (copy/migration) from POC to production catalog is not yet defined.
```

---

### Diff 2 — Not yet connected to retrieval (Finding G)

**Code citation:** No import of `fsr_scraped_file_mapping_ref` exists in any file under `fsr_pipeline/src/` or `fsr_pipeline_gt_direct/src/`. `delta_store.py:L14` — only imports `EMBEDDINGS_TABLE` and `FSR_REF_VIEW` from config; `FSR_REF_VIEW = "vgpd.fsr_std_views.fsr_pdf_ref"` is the only supplementary view used at any stage.

**PDF spec reference:** [Query FSR Spec §Step 6 — Metadata enrichment] and [Query FSR Spec §Supplementary: Structured Metadata Views, row 3] require `fsr_scraped_file_mapping_ref` to be joined at query time. [Query FSR Spec §Current Experiment vs Production Spec point 3] explicitly states: "it does not construct joined fsr_report, pdf_ref, and scraped_mapping response payloads."

**Assessment: ⚠️ CONCERN**
The spec is explicit that this is a known POC gap, but the metadata extraction doc may lead readers to believe the scraping output feeds into retrieval. The disconnect is complete — the scraping pipeline produces data that is never read by the retrieval pipeline. The doc must state this plainly at the top to prevent misleading stakeholders about retrieval data quality.

**Add note at top of doc:**
> **IMPORTANT (2026-04-09):** `fsr_scraped_file_mapping_ref` is NOT yet connected to the
> retrieval pipeline. No code in `fsr_pipeline` or `fsr_pipeline_gt_direct` reads from this
> table. The join described as "at query time" in Step 6 of the Query FSR Tool Spec is a
> planned production step deferred from the current POC. The scraping pipeline populates the
> table at `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref`
> (run_scraping_pipeline.py:L70), but this data is not surfaced in any retrieval response.
> See also: Query FSR Spec §Current Experiment vs Production Spec.

---

## 08-known-gaps-and-risks.md

### Diff 1 — New gap: reranking recall tradeoff (Finding F)

**Code citation:** `fsr_pipeline_gt_direct/src/evaluate_retrieval.py:L712-L718` — four eval modes, including `hybrid_reranking` with `DatabricksReranker`. `evaluate_retrieval.py:L816-L821` — binary recall metric: `recall = 1.0 if cumulative_matches > 0 else 0.0`. `evaluate_retrieval.py:L273-L285` — `_query_sdk()` uses `DatabricksReranker(columns_to_rerank=["chunk_text"])`. `fsr_pipeline_gt_direct/run_pipeline.py:L197` — `EVAL_MAX_K = 20`.

**PDF spec reference:** [Query FSR Spec §Step 4 — Reranking] mandates: "Apply the Databricks built-in reranker (DatabricksReranker, reranking on chunk_text) to the hybrid search results." The spec does not qualify this with a k threshold. [Query FSR Spec §Retrieval Validation Snapshot] shows that in earlier experiments, reranking with criteria improved Recall@20 to 86.4.

**Assessment: ⚠️ CONCERN**
The spec mandates unconditional reranking, but the eval data shows it hurts Recall@1 (0.432 → 0.303, a 30% degradation). For use cases like RE Risk Evaluation Chain that need high top-1 precision, this is a material quality risk. The spec should be updated or ADR-003 should formally address this trade-off. The eval methodology (binary recall, PAGE_WINDOW=10) is reasonable but should be noted when citing these numbers.

**Add new gap:**
```
Gap 6 — Reranking Hurts Recall@1

Source: evaluate_retrieval.py eval run (eval_summary_20260311_182906.csv),
132 serial/issue pairs, issue_prompt_only variant, 30-ESN GT subset.

  Mode                  R@1    R@5    R@20
  hybrid_retrieval      0.432  0.667  0.841   ← best at low k
  hybrid_reranking      0.303  0.667  0.841   ← reranking hurts R@1 by 30%
  ann_retrieval         0.379  0.614  0.795
  ann_reranking         0.235  0.614  0.795

The spec (Query FSR Spec §Step 4) mandates reranking unconditionally. This eval data
shows reranking reduces Recall@1 by ~30% while providing no benefit at k≥5 (R@5 and
R@20 are identical with and without reranking for hybrid). The eval uses binary recall
(hit = page within ±PAGE_WINDOW=10 pages OR NFKC snippet match) which is conservative
but fair for page-level citation tasks.

Risk: RE Risk Evaluation Chain relies on top-k results at low k. Unconditional reranking
will systematically degrade top-1 quality.

Feeds into ADR-003 — Options C or D (configurable / k-threshold gating) are now
better supported by data. Reranking should be optional or applied only for k≥5.
```

---

### Diff 2 — fsr_scraped_file_mapping_ref deferred (Finding G)

**Code citation:** `delta_store.py:L14` — only `FSR_REF_VIEW = "vgpd.fsr_std_views.fsr_pdf_ref"` is imported; the scraped mapping view is absent. `run_scraping_pipeline.py:L70` — data lands in `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref`.

**PDF spec reference:** [Query FSR Spec §Step 6 — Metadata enrichment] requires the join. [Query FSR Spec §Current Experiment vs Production Spec point 3] confirms it is not implemented.

**Assessment: ⚠️ CONCERN**
This is a data availability gap masquerading as an implementation gap. The data exists (scraping pipeline runs) but is siloed. Until retrieval code reads from this table, the scraped metadata (which includes additional file-level fields not in FieldVision) provides no retrieval value. Connecting it requires writing the Step 6 join logic, which is a production build item.

**Add to Recommended Next Steps:**
> Connect `fsr_scraped_file_mapping_ref` to the retrieval pipeline (Step 6 of the Query FSR
> Spec). The table is populated by run_scraping_pipeline.py at
> `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref` but is never read by any retrieval
> code. Implementing this join requires: (1) promoting the table to
> `vgpd.fsr_std_views.fsr_scraped_file_mapping_ref` or updating the retrieval join key,
> (2) implementing the filename normalization logic described in Query FSR Spec §Join
> Relationships, (3) adding the `scraped_mapping` key to the grouped response shape.

---

### Diff 3 — Broken code risk (Finding K)

**Code citation:** `fsr_pipeline/src/experiments.py:L14-L18` — four broken imports from `retrieval.py`. `fsr_pipeline/run_pipeline.py:L251-L252` — `from evaluate_retrieval import evaluate_all` will fail because `evaluate_retrieval` is not in `fsr_pipeline/src/`.

**PDF spec reference:** [Not in spec docs] — broken imports are an internal code quality issue.

**Assessment: ❌ WRONG**
These are hard failures, not warnings. Any run of the main pipeline with `RUN_EVALUATION=True` (the default: `run_pipeline.py:L185`) will crash at the import statement. This is a runtime blocker for any automated pipeline execution.

**Add to Recommended Next Steps:**
> Fix two broken import failures before any automated pipeline runs:
> 1. `fsr_pipeline/src/experiments.py:L14-L18` — remove or replace the four broken imports
>    (`BM25RetrieverWrapper`, `VectorSearchRetriever`, `WeightedEnsembleRetriever`,
>    `rerank_by_keywords`). None exist in `retrieval.py`. The entire file is dead code
>    from a superseded experiment phase.
> 2. `fsr_pipeline/run_pipeline.py:L251-L252` — `from evaluate_retrieval import evaluate_all`
>    will fail because `evaluate_retrieval.py` only exists in `fsr_pipeline_gt_direct/src/`,
>    not in `fsr_pipeline/src/`. Either copy the module or add `fsr_pipeline_gt_direct/src/`
>    to sys.path before this import. Both are blockers when `RUN_EVALUATION=True` (the default).

---

### Diff 4 — Clarify evaluation scope under Gap 3 (Finding H)

**Code citation:** `fsr_pipeline_gt_direct/src/config.py:L117-L129` — GT subset table and index names. `fsr_pipeline/src/config.py:L118-L130` — full-corpus table and index names.

**PDF spec reference:** [Query FSR Spec §Data Sources — Why the LiteLLM subset exists] explicitly states the GT subset is "not the full FSR corpus" and was created specifically for REChain retrieval testing.

**Assessment: ✅ ACCEPTABLE**
The two-pipeline structure is correct experimental design. The gap is in documentation clarity about which pipeline serves which purpose. The spec itself documents this distinction.

**Where:** Gap 3 "Production tables not built."
**Add:**
> Current evaluation pipeline (`fsr_pipeline_gt_direct`) targets a 30-ESN ground-truth subset
> (`field_service_report_gt_litellm` / `vs_field_service_report_gt_litellm`
> — gt_direct/config.py:L117-L129). The 132 serial/issue pair evaluation
> (eval_summary_20260311_182906.csv) reflects this subset only. The full-corpus
> pipeline (`fsr_pipeline` — config.py:L118-L130) targets `field_service_report` /
> `vs_field_service_report` and has a retrieval smoke test but no ground-truth eval harness.
> Production evaluation at full corpus scale is a build item for MVP2.

---

## ADR-002 — Embedding Strategy

### Diff 1 — POC embedding space mismatch (Finding A)

**Code citation:** `config.py:L132-L137` — the two conflicting embedding configs side by side. `pipeline.py:L297-L303` — VS index creation uses `VS_INDEX_EMBEDDING_ENDPOINT` (`databricks-gte-large-en`). `vector_embeddings.py:L38-L43` — `_LiteLLMEmbeddingClient` uses `VECTOR_SEARCH_EMBEDDING_MODEL` (`azure-text-embedding-3-large-1`). These are provably different models from different providers with different output dimensionalities (768-dim for GTE-large vs 3072-dim for text-embedding-3-large).

**PDF spec reference:** [Query FSR Spec §Data Sources — Embedding model] and [Query FSR Spec §Step 2 — Generate query vector internally] together require the same model for both ingest and query. [Query FSR Spec §Current Experiment vs Production Spec point 5] acknowledges the mismatch: "the self-managed LiteLLM index currently used in REChain experimentation is main.gp_services_sdg_poc.vs_field_service_report_gt_litellm, which was created only for the 30-ESN ground-truth subset."

**Assessment: ❌ WRONG**
The embedding model mismatch between ingest and query is not a theoretical concern — it means the dense retrieval leg of HYBRID search in the main `fsr_pipeline` is comparing vectors from incompatible embedding spaces. The `fsr_pipeline_gt_direct` GT subset used a self-managed LiteLLM index for the 30-ESN evaluation, so the eval metrics (R@1=0.432) were produced under the correct (consistent) embedding condition. The main pipeline's metrics would likely be different if measured. ADR-002 must resolve this before production.

**Add to Context section:**
> POC embedding space mismatch (confirmed 2026-04-09 via code review):
> - VS index creation: `embedding_model_endpoint_name = "databricks-gte-large-en"`
>   (config.py:L133, pipeline.py:L301) — Databricks-managed, ~768-dim
> - Query vector generation: `azure-text-embedding-3-large-1` via LiteLLM
>   (config.py:L135-L136, vector_embeddings.py:L38-L43) — 3072-dim
> These are different models with different embedding spaces and different dimensionalities.
> The dense retrieval leg of HYBRID search in the current `fsr_pipeline` is semantically
> invalid — it compares query vectors from one space against index vectors from another.
> The 30-ESN GT eval (evaluate_retrieval.py) used `vs_field_service_report_gt_litellm`
> which is a self-managed LiteLLM index, so the reported R@1=0.432 reflects consistent
> embeddings. The full-corpus `vs_field_service_report` index uses mismatched embeddings.
> Production target per Query FSR Spec §Embedding model resolves this via a self-managed
> VS index with LiteLLM for both ingest and query, with embedding arrays stored in Delta.
> This is the primary technical motivation for Option A in ADR-002.

**Qualify the Option A advantage bullet:**
```
"Same model used during ingestion → consistent embedding space"
→ add: "(Production target only — current POC has a confirmed model mismatch
        between ingest [databricks-gte-large-en] and query [azure-text-embedding-3-large-1])"
```

---

## ADR-003 — Reranking Strategy

### Diff 1 — New eval numbers (Finding F)

**Code citation:** `evaluate_retrieval.py:L712-L718` — four eval modes. `evaluate_retrieval.py:L816-L821` — binary recall definition. `evaluate_retrieval.py:L86-L88` — `PAGE_WINDOW = 10`. `evaluate_retrieval.py:L273-L285` — `DatabricksReranker(columns_to_rerank=["chunk_text"])`.

**PDF spec reference:** [Query FSR Spec §Step 4 — Reranking] mandates `DatabricksReranker` applied unconditionally. [Query FSR Spec §Retrieval Validation Snapshot] documents earlier metrics where reranking + criteria improved Recall@20 to 86.4 and Recall@1 dropped to 19.7 — a significant top-1 degradation that is now confirmed in the updated eval.

**Assessment: ⚠️ CONCERN**
The pattern is consistent across both the earlier spec metrics (R@1 dropped from 45.5 to 19.7 with reranking) and Alex's updated eval (R@1 dropped from 0.432 to 0.303 with reranking). Reranking consistently hurts top-1 while providing diminishing returns at k≥5. The spec's unconditional reranking mandate should be revisited — the data strongly supports Options C or D in ADR-003.

**Current table:**
```
| DBR HYBRID + criteria | 45.5 | 67.4 | 78.8 | 84.8 |
| DBR Reranked + criteria | 19.7 | 56.1 | 73.5 | 86.4 |
```
**Add row or footnote:**
```
| hybrid_retrieval (2026-04-09, no criteria) | 43.2 | 66.7 | — | 84.1 |
   (evaluate_retrieval.py, issue_prompt_only variant, 30-ESN GT subset)
| hybrid_reranking (2026-04-09, no criteria) | 30.3 | 66.7 | — | 84.1 |
   Source: Alex's fsr_pipeline_gt_direct (evaluate_retrieval.py), 132 serial/issue pairs.
   PAGE_WINDOW=10, binary recall. Reranking hurts at k≤3, neutral at k=5, no gain at k≥20.
   Note: different query variant (no criteria), different eval set vs. earlier numbers.
   Consistent pattern: reranking reliably hurts R@1 across both eval runs.
   Strengthens case for Options C or D in ADR-003 (conditional / threshold-gated reranking).
```

**Update Context paragraph:**
```
"hurts low-k recall but helps at k=20"
→ "hurts at k≤3 (R@1 degraded ~30%), neutral at k=5 (R@5 unchanged),
   equivalent at k≥20 (R@20 identical with and without reranking in hybrid mode)"
```

---

## ADR-004 — Ingestion Pipeline Trigger

### Diff 1 — Pipeline step 4 (Finding A)

**Code citation:** `pipeline.py:L783-L793` — Step 3 in the pipeline is `_sync_vs_index()`, which triggers a VS delta-sync. No embedding generation step exists anywhere between `save_rows_to_delta()` and `_sync_vs_index()`. `delta_store.py:L329-L358` — `save_rows_to_delta()` writes the Delta table with no embedding column. `config.py:L132-L133` — `VS_INDEX_EMBEDDING_ENDPOINT = "databricks-gte-large-en"` is what VS uses to auto-embed at sync time.

**PDF spec reference:** [Query FSR Spec §Embedding persistence] states embeddings "are generated during ingestion, stored in the Delta table, and indexed in Vector Search." The current pipeline does not generate or store embeddings during ingestion — it defers to VS.

**Assessment: ❌ WRONG**
The ADR document listing "Generate embeddings" as a distinct ingestion step is factually incorrect for the current POC. The pipeline writes chunks to Delta and then triggers a VS delta-sync — there is no embedding generation step in the pipeline code. This must be corrected to avoid misleading the DEV team about what the current code does.

**Current:**
```
4. Generate embeddings (azure-text-embedding-3-large-1 via LiteLLM)
```
**Should be:**
```
4. Write chunks to Delta table (no embedding generation in current pipeline —
   pipeline.py:L763-L793 calls save_rows_to_delta() then _sync_vs_index(); delta_store.py
   schema has no embedding column — delta_store.py:L236-L246)
   POC: VS auto-embeds chunk_text at sync time using databricks-gte-large-en
        (config.py:L133, pipeline.py:L297-L303)
   Production target per Query FSR Spec §Embedding persistence: generate embedding vectors
   via LiteLLM (azure-text-embedding-3-large-1) and write to a Delta column before VS index
   sync; this requires a self-managed VS index (pending ADR-002)
```

---

### Diff 2 — Current state pipeline (Finding H)

**Code citation:** `fsr_pipeline_gt_direct/src/config.py:L127-L129` — `VS_INDEX_NAME = "main.gp_services_sdg_poc.vs_field_service_report_gt_litellm"`. `fsr_pipeline/run_pipeline.py:L1-L6` — notebook header states "Compute: Serverless (or cluster ai-pw-ser-ds-dev-apc if needed) (DEV workspace)". `fsr_pipeline_gt_direct/run_pipeline.py:L200-L208` — pipeline entrypoint with evaluation.

**PDF spec reference:** [Query FSR Spec §Current Experiment vs Production Spec point 1] states: "the current repository contains Databricks notebooks (run_pipeline.py, run_evaluation.py) and helper modules, not a deployed query_fsr REST service." [Query FSR Spec §Service operations] lists these as production requirements not yet implemented.

**Assessment: ✅ ACCEPTABLE**
The clarification here is about accuracy, not a code defect. The ADR's description of the current state should correctly reflect that the GT subset pipeline (`fsr_pipeline_gt_direct`) is a structured notebook workflow, not ad-hoc experimentation.

**Current:**
```
existing vector index was populated ad-hoc by the DS team using notebook experiments
```
**Should be:**
```
The existing GT subset VS index (vs_field_service_report_gt_litellm) was populated by
fsr_pipeline_gt_direct — a structured 30-ESN ground-truth subset pipeline
(fsr_pipeline_gt_direct/src/config.py:L127-L129), not ad-hoc notebooks. The full-corpus
pipeline (fsr_pipeline — config.py:L128-L130) targets vs_field_service_report. Neither
pipeline runs on an automated production trigger — both are manually executed Databricks
notebook workflows per Query FSR Spec §Service operations.
```

---

## ADR-006 — Query FSR Service Structure

### Diff 1 — Deferred modules (Finding G)

**Code citation:** `retrieval.py` (entire file) — no hydration or metadata enrichment logic. `pipeline.py:L412` — `columns = ["chunk_id", "pdf_name", "page_number", "chunk_text"]` — the retrieval smoke test does not include `generator_serial` (unlike the spec's first-pass columns requirement). `run_scraping_pipeline.py:L70` — scraping output table not referenced anywhere in retrieval code.

**PDF spec reference:** [Query FSR Spec §Step 5 — Chunk row hydration] and [Query FSR Spec §Step 6 — Metadata enrichment] describe what `hydrate.py` and `enrich.py` must implement. [Query FSR Spec §Step 4 — Reranking] describes what `rerank.py` must implement, with the caveat that eval data (evaluate_retrieval.py results) now challenges unconditional reranking.

**Assessment: ✅ ACCEPTABLE**
These modules are correctly deferred — the spec itself documents they are not in the current experiment. The proposed directory structure in ADR-006 should clearly mark each module's implementation status so the DEV team understands what exists vs. what must be built.

**Where:** Proposed directory structure.
**Add note:**
```
hydrate.py  → [NOT IN CURRENT POC — deferred to production build; implements
               Query FSR Spec §Step 5 — reload full chunk row from Delta by chunk_id]
enrich.py   → [NOT IN CURRENT POC — deferred; fsr_scraped_file_mapping_ref not connected
               to retrieval (run_scraping_pipeline.py writes to main.gp_services_sdg_poc.*;
               no retrieval code reads from it); implements Query FSR Spec §Step 6]
rerank.py   → [CONDITIONAL — pending ADR-003 decision; eval data (evaluate_retrieval.py,
               132 pairs) shows reranking hurts R@1 by 30% (0.432 → 0.303 for hybrid).
               Recommend: optional/configurable per ADR-003 Options C or D, not mandatory]
```

---

### Diff 2 — embed.py dependency (Finding A)

**Code citation:** `vector_embeddings.py:L36-L97` — current `_LiteLLMEmbeddingClient` handles query embedding only (no batch ingest embedding). `fsr_pipeline_gt_direct/src/vector_embeddings.py:L115` — `get_text_embeddings()` function exists in the gt_direct version but not in the main pipeline's `vector_embeddings.py` — it would be the basis for an `embed.py` ingest module.

**PDF spec reference:** [Query FSR Spec §Step 2 — Generate query vector internally] requires query embedding. [Query FSR Spec §Embedding persistence] requires ingest embedding stored in Delta. Both require the same model. The production `embed.py` module must handle both use cases.

**Assessment: ⚠️ CONCERN**
The `get_text_embeddings()` function present in `fsr_pipeline_gt_direct/src/vector_embeddings.py:L115` but absent from the main `fsr_pipeline/src/vector_embeddings.py` is a meaningful capability gap. Moving to a self-managed VS index requires batch embedding during ingest. The ADR should flag that the VS index type migration (Delta Sync → self-managed) is a prerequisite for consistent embeddings and a non-trivial infrastructure change.

**Add to "Questions to Resolve":**
> ADR-002 resolution must address VS index type migration: Delta Sync auto-embed (POC) →
> self-managed index (production). Key prerequisites:
> 1. embed.py must call the same LiteLLM model used at query time
>    (vector_embeddings.py `get_text_embeddings()` exists in fsr_pipeline_gt_direct but
>    not in fsr_pipeline — fsr_pipeline_gt_direct/src/vector_embeddings.py:L115)
> 2. Delta table schema must be extended with an embedding array column
>    (currently absent — delta_store.py:L236-L246)
> 3. VS index must be rebuilt as a self-managed type (not Delta Sync)
> 4. EMBEDDING_VECTOR_COLUMN is inconsistent between configs:
>    fsr_pipeline: "embeddings" (config.py:L138) vs.
>    fsr_pipeline_gt_direct: "chunk_embedding" (gt_direct/config.py:L130)
>    These must be reconciled to a single canonical column name before production.

---

## Priority Order for Applying Diffs

1. **Finding A/D** — embedding model mismatch: touches 02, 03, 04, 06, ADR-002, ADR-004 — most pervasive; foundational to production architecture
2. **Finding K** — broken experiments.py and missing evaluate_retrieval import: touches 06, 08 — blocks automated evaluation runs immediately; highest operational risk
3. **Finding C** — ESN 4-layer, verify MIN_ESN_COUNT=1 (doc says 5): touches 02, 03, 06 — factual documentation error
4. **Finding F** — reranking eval numbers: touches 02, 08, ADR-003 — feeds open ADR decision; affects RE Chain design
5. **Finding G** — steps 5/6 deferred markers: touches 03, 07, 08, ADR-006 — prevents reader confusion about what is implemented
6. **Finding H** — pipeline variant documentation: touches 03, 04, 08 — clarifies experimental scope
7. **Finding I** — scraping output table name: touches 07 — prevents wrong table promotion path
