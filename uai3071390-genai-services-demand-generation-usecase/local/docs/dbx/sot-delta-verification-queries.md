# SOT vs Delta — Verification Queries
---

## Q1 — FSR SOT prod (vgpp)

```sql
-- Q1_fsr_vgpp: document count per ESN in prod SOT
SELECT esn, COUNT(*) AS fsr_vgpp
FROM vgpp.fsr_std_views.fsr_field_vision_field_services_report_psot
WHERE esn IN (
  '338X408','290T762','338X713','290T543','337X709','337X305','337X330',
  '337X369','761X004','338X425','290T530','290T658','290T532','337X708',
  '338X426','338X427','337X336','290T503','338X722','290T577','337X045',
  '338X424','337X233','290T434','338X765','338X724','290T484','338X714',
  '337X134','337X789'
)
GROUP BY esn
ORDER BY esn;
```

## Q2 — FSR SOT dev (vgpd)

```sql
-- Q2_fsr_vgpd: document count per ESN in dev SOT
SELECT esn, COUNT(*) AS fsr_vgpd
FROM vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot
WHERE esn IN (
  '338X408','290T762','338X713','290T543','337X709','337X305','337X330',
  '337X369','761X004','338X425','290T530','290T658','290T532','337X708',
  '338X426','338X427','337X336','290T503','338X722','290T577','337X045',
  '338X424','337X233','290T434','338X765','338X724','290T484','338X714',
  '337X134','337X789'
)
GROUP BY esn
ORDER BY esn;
```

---

## Q3 — FSR Delta distinct docs

```sql
-- Q3_fsr_doc_delta: distinct documents per ESN in the chunk source table
SELECT generator_serial AS esn, COUNT(DISTINCT pdf_name) AS fsr_doc_delta
FROM main.gp_services_sdg_poc.field_service_report_gt_litellm
WHERE generator_serial IN (
  '338X408','290T762','338X713','290T543','337X709','337X305','337X330',
  '337X369','761X004','338X425','290T530','290T658','290T532','337X708',
  '338X426','338X427','337X336','290T503','338X722','290T577','337X045',
  '338X424','337X233','290T434','338X765','338X724','290T484','338X714',
  '337X134','337X789'
)
GROUP BY generator_serial
ORDER BY generator_serial;
```

---

## Q4 — ER SOT prod (vgpp)

```sql
-- Q4_er_vgpp: case count per ESN in prod SOT
SELECT u_serial_number AS esn, COUNT(*) AS er_vgpp
FROM vgpp.qlt_std_views.u_pac
WHERE u_serial_number IN (
  '338X408','290T762','338X713','290T543','337X709','337X305','337X330',
  '337X369','761X004','338X425','290T530','290T658','290T532','337X708',
  '338X426','338X427','337X336','290T503','338X722','290T577','337X045',
  '338X424','337X233','290T434','338X765','338X724','290T484','338X714',
  '337X134','337X789'
)
GROUP BY u_serial_number
ORDER BY u_serial_number;
```

## Q5 — ER SOT dev (vgpd)

```sql
-- Q5_er_vgpd: case count per ESN in dev SOT
SELECT u_serial_number AS esn, COUNT(*) AS er_vgpd
FROM vgpd.qlt_std_views.u_pac
WHERE u_serial_number IN (
  '338X408','290T762','338X713','290T543','337X709','337X305','337X330',
  '337X369','761X004','338X425','290T530','290T658','290T532','337X708',
  '338X426','338X427','337X336','290T503','338X722','290T577','337X045',
  '338X424','337X233','290T434','338X765','338X724','290T484','338X714',
  '337X134','337X789'
)
GROUP BY u_serial_number
ORDER BY u_serial_number;
```

---

## Q6 — ER Delta distinct cases

```sql
-- Q6_er_case_delta: distinct ER case numbers per ESN in the chunk source table
SELECT serial_number AS esn, COUNT(DISTINCT er_case_number) AS er_case_delta
FROM main.gp_services_sdg_poc.engineering_report_chunk
WHERE serial_number IN (
  '338X408','290T762','338X713','290T543','337X709','337X305','337X330',
  '337X369','761X004','338X425','290T530','290T658','290T532','337X708',
  '338X426','338X427','337X336','290T503','338X722','290T577','337X045',
  '338X424','337X233','290T434','338X765','338X724','290T484','338X714',
  '337X134','337X789'
)
GROUP BY serial_number
ORDER BY serial_number;
```

---

## Q7 — Combined full comparison

```sql
-- Q7_combined: Full SOT vs Delta comparison table
-- Produces one row per ESN with all 6 counts
WITH esns AS (
  SELECT explode(array(
    '338X408','290T762','338X713','290T543','337X709','337X305','337X330',
    '337X369','761X004','338X425','290T530','290T658','290T532','337X708',
    '338X426','338X427','337X336','290T503','338X722','290T577','337X045',
    '338X424','337X233','290T434','338X765','338X724','290T484','338X714',
    '337X134','337X789'
  )) AS esn
),
fsr_vgpp AS (
  SELECT esn, COUNT(*) AS cnt
  FROM vgpp.fsr_std_views.fsr_field_vision_field_services_report_psot
  GROUP BY esn
),
fsr_vgpd AS (
  SELECT esn, COUNT(*) AS cnt
  FROM vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot
  GROUP BY esn
),
fsr_delta AS (
  SELECT generator_serial AS esn, COUNT(DISTINCT pdf_name) AS cnt
  FROM main.gp_services_sdg_poc.field_service_report_gt_litellm
  GROUP BY generator_serial
),
er_vgpp AS (
  SELECT u_serial_number AS esn, COUNT(*) AS cnt
  FROM vgpp.qlt_std_views.u_pac
  GROUP BY u_serial_number
),
er_vgpd AS (
  SELECT u_serial_number AS esn, COUNT(*) AS cnt
  FROM vgpd.qlt_std_views.u_pac
  GROUP BY u_serial_number
),
er_delta AS (
  SELECT serial_number AS esn, COUNT(DISTINCT er_case_number) AS cnt
  FROM main.gp_services_sdg_poc.engineering_report_chunk
  GROUP BY serial_number
)
SELECT
  e.esn,
  COALESCE(fp.cnt, 0) AS fsr_vgpp,
  COALESCE(fd.cnt, 0) AS fsr_vgpd,
  COALESCE(fdl.cnt, 0) AS fsr_doc_delta,
  COALESCE(ep.cnt, 0) AS er_vgpp,
  COALESCE(ed.cnt, 0) AS er_vgpd,
  COALESCE(edl.cnt, 0) AS er_case_delta
FROM esns e
LEFT JOIN fsr_vgpp fp ON e.esn = fp.esn
LEFT JOIN fsr_vgpd fd ON e.esn = fd.esn
LEFT JOIN fsr_delta fdl ON e.esn = fdl.esn
LEFT JOIN er_vgpp ep ON e.esn = ep.esn
LEFT JOIN er_vgpd ed ON e.esn = ed.esn
LEFT JOIN er_delta edl ON e.esn = edl.esn
ORDER BY e.esn;
```

---

## Notes

- **FSR ESN column:** `esn` in SOT, `generator_serial` in Delta table
- **ER ESN column:** `u_serial_number` in SOT, `serial_number` in Delta table
- **FSR Doc(Δ):** `COUNT(DISTINCT pdf_name)` — confirmed by Feng as "distinct documents"
- **ER Case(Δ):** `COUNT(DISTINCT er_case_number)` — distinct ER case IDs
- If an ESN returns 0 in Delta but has SOT data → ingestion gap (NO CHUNKS scenario)
- If an ESN is missing from results entirely → that column's table has no rows for that ESN at all

### Workspaces

- **Q1-Q5:** Run on **NRC workspace** (`gevernova-nrc-workspace.cloud.databricks.com`) using `gev-gp-dev-warehouse-pmce`
- **Q6:** Run on **AI dev workspace** (`gevernova-ai-dev-dbr.cloud.databricks.com`) — `engineering_report_chunk` table lives here
- Original Q6 used `engineering_report_chunk_litellm` (wrong) — corrected to `engineering_report_chunk` per Feng
