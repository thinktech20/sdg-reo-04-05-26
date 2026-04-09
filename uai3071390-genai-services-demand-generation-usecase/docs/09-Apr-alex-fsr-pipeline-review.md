# Review: Alex's FSR Chunking/Embedding Pipeline

**Date:** 2026-04-09
**Reviewer:** Madhurima Saxena
**For:** Tao
**Subject:** Review of `fsr_pipeline`, `fsr_pipeline_gt_direct`, `fsr_scraping` vs. spec docs

---

## Executive Summary

Five things Tao needs to know coming into this conversation:

1. **Embedding model is mismatched** — the full-corpus pipeline (`fsr_pipeline`) uses `databricks-gte-large-en` for the index and `azure-text-embedding-3-large-1` for queries. Different models, different vector spaces. Dense retrieval results from this pipeline are unreliable. ❌
2. **Reranking hurts top-1 recall** — eval data shows R@1 drops from 0.432 → 0.303 with reranking. The spec mandates unconditional reranking. This needs a decision. ⚠️
3. **Two broken code paths** — `experiments.py` has 4 dead imports (hard `ImportError`); `run_pipeline.py` imports an eval module that doesn't exist in its directory. Default pipeline run will crash. ❌
4. **ESN identification is better than the spec documents** — Alex built a 4-layer fallback chain (regex → filename → LLM → ref view). Well-engineered. Our docs describe it incorrectly. ✅
5. **Scraping output exists but is disconnected** — `fsr_scraped_file_mapping_ref` is populated but never read by any retrieval code. Step 6 of the spec is unbuilt. ⚠️

---

## Spec PDF Updates

The two docs Tao shared have been checked against `reference/DS-experimentations/`:

| Document | Status | Action taken |
|---|---|---|
| `4e. Query FSR Tool Specs.pdf` | **NEWER** — corrects `fsr_pdf_ref.filename` → `fsr_pdf_ref.s3_filename` throughout | Replaced in DS-experimentations |
| `Field Service Report (FSR) - Data Attribute Extraction (2).pdf` | **NEW** — no prior version existed | Added to DS-experimentations as `4e-fsr-data-attribute-extraction.pdf` |
| `4e-fsr-chunking-retrieval-reranking-experimentation.pdf` | No replacement in 09-Apr — retained as-is | No change |

The `s3_filename` correction matters: Alex's code uses it correctly (`delta_store.py:L193`), so the new spec version now matches the implementation.

---

## Alex's Pipeline Architecture

### Three separate codebases

| Repo | Purpose |
|---|---|
| `fsr_pipeline` | Full-corpus ingestion (chunking + VS sync) and retrieval smoke test |
| `fsr_pipeline_gt_direct` | 30-ESN ground-truth subset for retrieval evaluation |
| `fsr_scraping` | PDF metadata extraction → `fsr_scraped_file_mapping_ref` table |

### End-to-end flow (`fsr_pipeline`)

```
Volume PDFs (4 paths)                                 [config.py:L109-L114]
  ↓
Step 1: PyMuPDF load → hierarchical semantic chunk (V3, 4000 chars / 200 overlap)
         [recursive_chunking_v3.py, config.py:L174-L175]
         + LLM ESN identification (GPT-4o) in background thread
         [pdf_processor.py:L230-L231, esn_identifier.py:L27]
         + ref view join (fsr_pdf_ref on s3_filename) for ESN + report_date
         [delta_store.py:L181-L223]
         + multi-ESN row expansion (one row per ESN per chunk)
         [delta_store.py:L262-L326]
  ↓
Step 2: Batch write → main.gp_services_sdg_poc.field_service_report (Delta, CDF enabled)
         [delta_store.py:L329-L358, config.py:L118-L120]
  ↓
Step 3: VS delta-sync → main.gp_services_sdg_poc.vs_field_service_report
         (VS auto-embeds chunk_text using databricks-gte-large-en)
         [pipeline.py:L277-L332, config.py:L132-L134]
  ↓
Step 4: Retrieval smoke test (HYBRID + ANN, 5 test queries)
         [pipeline.py:L406-L473]
```

### Chunking parameters

| Parameter | Config value | Actual runtime | Code reference |
|---|---|---|---|
| `chunk_size` | 4000 chars | 4000 ✓ | `config.py:L174` |
| `chunk_overlap` | 200 chars | 200 ✓ | `config.py:L175` |
| Algorithm | Hierarchical semantic (V3) | TOC-driven hierarchy, 5 levels, LangChain splitter within sections | `recursive_chunking_v3.py` |
| `min_chunk_size` | 100 (config) | **20 chars hardcoded — config ignored** | `config.py:L179` vs `recursive_chunking_v3.py:L805` |
| `separator_patterns` | Defined in config | **Unused** — chunking file has its own hardcoded separators | `config.py:L180-L182` vs `recursive_chunking_v3.py:L659-L671` |
| `max_chunk_tokens` | 4000 (config) | **Unused — never enforced** | `config.py:L176` |

### ESN identification (4-layer)

1. **Regex on first 2 pages** — 7 patterns in priority order (ESN/SY:, ESN:, Equipment Serial Number:, Serial Number:, Generator Serial:, Unit Serial Number:, GAS TURBINE) — `pdf_processor.py:L40-L55`, `L84-L116`
2. **Filename parsing** — first token if matches `[A-Z0-9]{4,12}` and not a date — `pdf_processor.py:L64-L81`
3. **LLM (GPT-4o)** — full doc text → JSON `{ESN: count}`, qualified if `count >= MIN_ESN_COUNT=1` AND `count/total >= MIN_ESN_FRACTION=10%` — `esn_identifier.py:L27`, `L30-L31`, `L293-L358`, `L373-L387`
4. **Ref view join** — `vgpd.fsr_std_views.fsr_pdf_ref` pre-loaded and joined on UUID stem; ref ESNs + dates **take priority** over layers 1–3 — `delta_store.py:L181-L223`

> Our existing docs (02, 03, 06) describe this as "LLM + regex" (2-layer) or "3-phase". The correct count is 4 layers. Also: doc 06 states MIN_ESN_COUNT=5 — **verified wrong**, actual value is 1 (`esn_identifier.py:L30`). [Query FSR Spec §Acceptance Criteria]

### Delta table schema (`field_service_report`)

Columns: `chunk_id`, `pdf_name`, `page_number`, `generator_serial`, `report_date`, `chunk_text`, `metadata` (JSON), `created_at`, `uploaded_at` — `delta_store.py:L226-L246`

> **No `embedding` column.** VS auto-embeds at sync time using `databricks-gte-large-en` (`pipeline.py:L301`). `config.py:L138` defines `EMBEDDING_VECTOR_COLUMN = "embeddings"` but this variable is never written to Delta — dead code. Production spec requires an `embedding ARRAY` column. [Query FSR Spec §3.2]

### `fsr_pipeline_gt_direct` vs `fsr_pipeline`

| Dimension | `fsr_pipeline` | `fsr_pipeline_gt_direct` | Code reference |
|---|---|---|---|
| Target table | `field_service_report` | `field_service_report_gt_litellm` | `fsr_pipeline/config.py:L118`; `gt_direct/config.py:L117` |
| Target VS index | `vs_field_service_report` | `vs_field_service_report_gt_litellm` | `fsr_pipeline/config.py:L128`; `gt_direct/config.py:L127` |
| Embedding vector column name | `"embeddings"` | `"chunk_embedding"` | `fsr_pipeline/config.py:L138`; `gt_direct/config.py:L130` |
| Volume scope | 4 paths (incl. UAT_Files) | 3 paths | `fsr_pipeline/config.py:L109-L114`; `gt_direct/config.py:L109-L113` |
| Evaluation | Smoke test only | Full GT eval harness (Recall@K, Precision@K, 4 modes) | `pipeline.py:L406-L473`; `evaluate_retrieval.py` |
| Auto-creates VS index | Yes | No (assumes pre-existing) | `pipeline.py:L277-L332` |
| `get_text_embeddings()` batch fn | **Absent** | Present | `gt_direct/src/vector_embeddings.py:L115` |

### `fsr_scraping`

3-stage pipeline (`run_scraping_pipeline.py`):
1. `pdfplumber` first-page extraction → raw fields
2. LLM normalization (`gemini-3-flash`, `run_scraping_pipeline.py:L102`) → canonical 15-field schema
3. PySpark enrichment via IBAT + Event Vision SOT

Output: `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref` (`run_scraping_pipeline.py:L70`)

> Output is in `main.gp_services_sdg_poc`, not `vgpd.fsr_std_views.*`. Promotion to the canonical view is not yet implemented. This table is populated but **not connected to any retrieval code**. [Data Extraction Spec §3]

---

## Code vs. Spec Analysis

### ✅ Matches spec

| Area | Detail | Code reference |
|---|---|---|
| Chunk size / overlap | 4000 chars / 200 — within spec's recommended range | `config.py:L174-L175` |
| Multi-ESN row expansion | One row per ESN per chunk; `chunk_id` suffixed `__{esn}` | `delta_store.py:L262-L326`, `L311` |
| Hybrid retrieval mode | `query_type="hybrid"` default | `retrieval.py:L69` |
| Reranking present | `DatabricksReranker(columns_to_rerank=["chunk_text"])` in eval | `evaluate_retrieval.py:L252-L289` |
| ESN filter in evaluation | Always passes `{"generator_serial": serial}` | `evaluate_retrieval.py:L87-L89` |
| `s3_filename` join key | Used correctly — matches new spec version | `delta_store.py:L193` |

### Deviations from spec

| Area | Spec | Alex's code | Assessment | Code reference | Spec ref |
|---|---|---|---|---|---|
| Embedding model | Same `azure-text-embedding-3-large-1` for both ingest + query via LiteLLM | Index: `databricks-gte-large-en` (auto-embed). Query: `azure-text-embedding-3-large-1` | ❌ **WRONG** — Different vector spaces (768-dim vs 3072-dim). Dense retrieval leg compares incompatible vectors. Cosine similarity scores are meaningless. Must be fixed before production. | `config.py:L132-L137`; `pipeline.py:L301` | [Query FSR Spec §3.2] |
| Stored embedding column | `embedding ARRAY` in Delta table | Not stored. `EMBEDDING_VECTOR_COLUMN = "embeddings"` defined but never written — dead config | ❌ **WRONG** — Dead config field gives false confidence. Delta Sync index type cannot satisfy production spec. Must close before self-managed index migration. | `config.py:L138`; `delta_store.py:L226-L246` | [Query FSR Spec §3.2] |
| ESN filter mandatory | `equipment_serial_number` is a required input | Optional in `retrieval.py` — filter accepted but not enforced | ⚠️ **CONCERN** — No guard at notebook level. Risk if retrieval.py is called directly. REST wrapper must enforce this. | `retrieval.py:L43-L91` | [Query FSR Spec §2.1] |
| Chunk hydration (Step 5) | Secondary Delta SQL lookup by `chunk_id` after VS call | Not implemented — reads directly from VS response | ⚠️ **CONCERN** — `metadata` column and other Delta-only fields are unavailable at query time. Acceptable for DEV phase if REST team implements it. | `retrieval.py:L20`; `pipeline.py:L406-L473` | [Query FSR Spec §5] |
| Metadata join at query time (Step 6) | Join 3 views at query time | Only `fsr_pdf_ref` joined at ingest time. Scraping output not connected. | ⚠️ **CONCERN** — Scraping table lives in `main.*` not `vgpd.*`, so a catalog promotion step is also outstanding before Step 6 can be closed. | `delta_store.py:L181-L223`; `run_scraping_pipeline.py:L70` | [Query FSR Spec §6] |
| REST service wrapper | FastAPI endpoint with error codes | Not implemented (notebook workflow) | ✅ **ACCEPTABLE** — Explicitly DEV team responsibility. Notebook is appropriate for DS pipeline phase. | N/A | [Query FSR Spec §2, §7] |

### Bugs / broken code

| Issue | Assessment | Code reference |
|---|---|---|
| **`experiments.py` broken imports** — `BM25RetrieverWrapper`, `VectorSearchRetriever`, `WeightedEnsembleRetriever`, `rerank_by_keywords` imported from `retrieval.py`; none exist there | ❌ **WRONG** — Hard `ImportError` on execution. Leftover from superseded BM25/FAISS experiment. Delete or archive before any automated runs. | `experiments.py:L14-L18` |
| **Missing `evaluate_retrieval` module** — `run_pipeline.py` imports `evaluate_all` from `evaluate_retrieval`; that module only exists in `fsr_pipeline_gt_direct/src/`, not in `fsr_pipeline/src/` | ❌ **WRONG** — `RUN_EVALUATION=True` is the default (`run_pipeline.py:L162`). Every standard pipeline run will crash at the eval step. | `run_pipeline.py:L251-L252`, `L162` |
| **Dead config fields** — `separator_patterns`, `min_chunk_size=100`, `max_chunk_tokens=4000` defined in `ChunkingConfig` but chunking code ignores all three; uses hardcoded values instead | ⚠️ **CONCERN** — Misleads anyone tuning the pipeline. Changing `min_chunk_size` in config has zero effect. Remove or wire up. | `config.py:L176`, `L179`, `L180-L182`; `recursive_chunking_v3.py:L805`, `L659-L671` |
| **Hardcoded Windows path** — `C:\Users\560060297\Downloads\...` in `__main__` block | ⚠️ **CONCERN** — Code hygiene. Leaks developer's local path. No runtime impact (guarded by `if __name__ == "__main__"`). | `recursive_chunking_v3.py:L832-L835` |
| **SSL verify=False** in scraping — `requests.get(..., verify=False)` for volume discovery; main pipeline correctly builds a CA bundle | ⚠️ **CONCERN** — Inconsistent security posture between the two pipelines. Should be unified. | `run_scraping_pipeline.py:L272`; vs `config.py:L83-L89` |

---

## Evaluation Results

From `eval_summary_20260311_182906.csv` — `fsr_pipeline_gt_direct`, 132 serial/issue pairs, GT subset:

| Mode | Recall@1 | Recall@5 | Recall@20 |
|---|---|---|---|
| hybrid_retrieval | **0.432** | 0.667 | 0.841 |
| ann_retrieval | 0.379 | 0.614 | 0.795 |
| hybrid_reranking | 0.303 | 0.667 | 0.841 |
| ann_reranking | 0.235 | 0.614 | 0.795 |

**Key finding:** Reranking hurts R@1 by ~30% (0.432 → 0.303) and is neutral at R@5 (identical 0.667). Reranking does not help for top-1 or top-3 retrieval. The spec mandates unconditional reranking — this data challenges that. (`evaluate_retrieval.py:L712-L718`, `L252-L289`) [Query FSR Spec §4.2]

> **Important caveat:** These numbers come from `fsr_pipeline_gt_direct` (self-managed LiteLLM index — consistent embedding spaces). The main `fsr_pipeline` has a confirmed embedding mismatch (`config.py:L132-L137`), so its dense retrieval results would be even lower. The GT-direct results are the more trustworthy signal for the Tao conversation.

---

## Questions for Tao

1. **Embedding model unification** [`config.py:L132-L137`, `pipeline.py:L301`] — `fsr_pipeline` uses `databricks-gte-large-en` for the index, `azure-text-embedding-3-large-1` for queries. These are incompatible vector spaces. Should production ingest generate and store LiteLLM embeddings in Delta (as `fsr_pipeline_gt_direct` is structured to do)? Or is Databricks-managed GTE acceptable for now? [Query FSR Spec §3.2]

2. **Which pipeline variant becomes production?** — `fsr_pipeline` has more complete infrastructure (auto-creates VS index, full corpus, 4 paths). `fsr_pipeline_gt_direct` is the only variant with consistent LiteLLM embeddings and a full eval harness. They even use different column names: `"embeddings"` vs `"chunk_embedding"` (`config.py:L138`; `gt_direct/config.py:L130`). What is the production path?

3. **Reranking mandatory?** [`evaluate_retrieval.py:L252-L289`] — Eval data shows reranking reduces R@1 by 30%. Should reranking be optional/configurable rather than unconditional? This directly affects ADR-003 Options C or D. [Query FSR Spec §4.2]

4. **`experiments.py` — remove or fix?** [`experiments.py:L14-L18`] — 4 broken imports, entire file is dead code from a superseded experiment. Delete?

5. **Steps 5–6 scope** [`retrieval.py:L20`, `pipeline.py:L406-L473`] — Chunk hydration and 3-view metadata join are not in Alex's code. Are these deferred to the DEV team's REST service, or does DS need to build them for the notebook too? [Query FSR Spec §5-6]

6. **`fsr_scraped_file_mapping_ref` readiness** [`run_scraping_pipeline.py:L70`] — Table exists at `main.gp_services_sdg_poc.*` but is not connected to retrieval. Is the scraping output stable enough to wire up? Who owns the promotion to `vgpd.fsr_std_views.*`? [Data Extraction Spec §3]

7. **Config cleanup** [`config.py:L176`, `L179`, `L180-L182`] — Three dead config fields (`separator_patterns`, `min_chunk_size`, `max_chunk_tokens`) that the chunking code ignores. Remove them or fix the chunking code to honour them?

---

## Documentation Corrections Needed

Our existing docs 01–08 and ADRs need updates based on today's findings. Priority order and what to fix per doc.

**No changes needed:** `01-project-overview`, `05-app-code-analysis`, ADR-001, ADR-005, ADR README

### Priority 1 — Fix first (factual errors / runtime blockers)

| Doc | Section | What's wrong | Finding | Assessment |
|---|---|---|---|---|
| `06-pipeline-code-analysis` | Embedding architecture table | Says VS sync uses `azure-text-embedding-3-large-1` — wrong, POC uses `databricks-gte-large-en` | A | ❌ WRONG |
| `06-pipeline-code-analysis` | ESN qualification filter | States `MIN_ESN_COUNT=5` — verified wrong, actual is `1` (`esn_identifier.py:L30`) | C | ❌ WRONG |
| `ADR-004` | Pipeline context, Step 4 | Lists "Generate embeddings (LiteLLM)" as a pipeline step — pipeline never generates embeddings | A | ❌ WRONG |
| `06-pipeline-code-analysis` | (new section needed) | No mention of broken `experiments.py` imports or missing `evaluate_retrieval` module | K | ❌ WRONG |
| `08-known-gaps-and-risks` | Recommended Next Steps | Broken imports in `experiments.py:L14-L18` and `run_pipeline.py:L251` are runtime blockers — not documented | K | ❌ WRONG |

### Priority 2 — High impact on architecture understanding

| Doc | Section | What's wrong | Finding | Assessment |
|---|---|---|---|---|
| `02-fsr-findings` | Chunk schema table | Shows `embedding` column as stored — it isn't | D | ⚠️ CONCERN |
| `02-fsr-findings` | ESN description | Says "LLM + regex" — actually 4-layer | C | ⚠️ CONCERN |
| `03-fsr-implementation-plan` | Phase 1, Step 4 | Presents production embedding spec as current state | A | ⚠️ CONCERN |
| `04-data-catalog` | Embedding Configuration table | "Stored in Delta at ingestion" — not true for POC | A, D | ⚠️ CONCERN |
| `ADR-002` | Context section | No mention of confirmed POC embedding space mismatch | A | ❌ WRONG |
| `ADR-003` | Eval numbers table | Old recall numbers; new data (R@1=0.432 hybrid, R@1=0.303 reranking) strengthens Options C/D | F | ⚠️ CONCERN |

### Priority 3 — Deferred step markers and scope clarity

| Doc | Section | What's wrong | Finding | Assessment |
|---|---|---|---|---|
| `03-fsr-implementation-plan` | Steps 5 and 6 | Listed as standard steps with no "NOT IN POC" marker | G | ⚠️ CONCERN |
| `07-fsr-metadata-extraction` | Output table name | Says `vgpd.fsr_std_views.*` — POC writes to `main.gp_services_sdg_poc.*` | I | ⚠️ CONCERN |
| `07-fsr-metadata-extraction` | Top of doc | No note that table is not connected to retrieval pipeline | G | ⚠️ CONCERN |
| `08-known-gaps-and-risks` | Gap list | Missing Gap 6: reranking hurts R@1 by 30% — feeds ADR-003 | F | ⚠️ CONCERN |
| `08-known-gaps-and-risks` | Gap 3 | No mention that GT subset pipeline is scoped to 30 ESNs only | H | ⚠️ CONCERN |
| `ADR-006` | Proposed structure | `hydrate.py`, `enrich.py`, `rerank.py` not marked as deferred/conditional | G, F | ⚠️ CONCERN |

> **Full diff detail** (exact current text → corrected text for each doc) is in `sdg-use-case/09-Apr/doc-diffs-from-alex-review.md` — use that when applying corrections.

---

## Appendix: Key File Locations

All paths relative to `sdg-use-case/09-Apr/alex-work/alex.seidel@ge.com/`

| What | Path |
|---|---|
| Main pipeline config | `fsr_pipeline/src/config.py` |
| Chunking algorithm | `fsr_pipeline/src/recursive_chunking_v3.py` |
| Delta write + ref join | `fsr_pipeline/src/delta_store.py` |
| ESN identification | `fsr_pipeline/src/esn_identifier.py` |
| PDF loading + ESN orchestration | `fsr_pipeline/src/pdf_processor.py` |
| Retrieval (no ESN guard, no hydration) | `fsr_pipeline/src/retrieval.py` |
| **Broken code (dead imports)** | `fsr_pipeline/src/experiments.py` |
| **Broken eval import** | `fsr_pipeline/run_pipeline.py:L251-L252` |
| GT-direct config (LiteLLM embeddings) | `fsr_pipeline_gt_direct/src/config.py` |
| Eval harness | `fsr_pipeline_gt_direct/src/evaluate_retrieval.py` |
| Scraping pipeline | `fsr_scraping/run_scraping_pipeline.py` |
| Eval results | `fsr_pipeline/results/eval_summary_20260311_182906.csv` |
| Updated Query FSR Spec | `reference/DS-experimentations/4e-query-fsr-tool-specs.pdf` |
| New Data Attribute Extraction doc | `reference/DS-experimentations/4e-fsr-data-attribute-extraction.pdf` |
| Full diff detail for docs 01-08 + ADRs | `sdg-use-case/09-Apr/doc-diffs-from-alex-review.md` |
