# SOT vs Delta — Verification Results

> Verification of Feng's comparison table using independent queries.
> Date: April 1, 2026

---

## Feng's Original Table

| ESN | FSR vgpp | FSR vgpd | FSR Doc(Δ) | FSR Note | ER vgpp | ER vgpd | ER Case(Δ) | ER Note |
|-----|----------|----------|------------|----------|---------|---------|------------|---------|
| 338X408 | 2 | 2 | 5 | Δ>SOT | 19 | 7 | 14 | between |
| 290T762 | 1 | 1 | 4 | Δ>SOT | 25 | 4 | 20 | between |
| 338X713 | 1 | 1 | 2 | Δ>SOT | 7 | 5 | 6 | between |
| 290T543 | 1 | 1 | 3 | Δ>SOT | 63 | 22 | 42 | between |
| 337X709 | 1 | 1 | 5 | Δ>SOT | 14 | 9 | 13 | between |
| 337X305 | 1 | 1 | 2 | Δ>SOT | 5 | 1 | 4 | between |
| 337X330 | **0** | **0** | 2 | **Δ has data, SOT=0** | 5 | 3 | 5 | =vgpp |
| 337X369 | 2 | 2 | 2 | match | 39 | 8 | 22 | between |
| 761X004 | 4 | 3 | 4 | =vgpp | 46 | 18 | 33 | between |
| 338X425 | 1 | 1 | 2 | Δ>SOT | 38 | 23 | 34 | between |
| 290T530 | 3 | 3 | 3 | match | 67 | 21 | 42 | between |
| 290T658 | 2 | 2 | 2 | match | 22 | 9 | 19 | between |
| 290T532 | **0** | **0** | 3 | **Δ has data, SOT=0** | 24 | 13 | 19 | between |
| 337X708 | 1 | 1 | 4 | Δ>SOT | 10 | 3 | 9 | between |
| 338X426 | 2 | 2 | 3 | Δ>SOT | 41 | 18 | 41 | =vgpp |
| 338X427 | 2 | 2 | 2 | match | 17 | 11 | 17 | =vgpp |
| 337X336 | **0** | **0** | 4 | **Δ has data, SOT=0** | 75 | 24 | 67 | between |
| 290T503 | 2 | 2 | 3 | Δ>SOT | 18 | 2 | 7 | between |
| 338X722 | **0** | **0** | 4 | **Δ has data, SOT=0** | 8 | 0 | 3 | between |
| 290T577 | 2 | 2 | 1 | Δ<SOT | 23 | 16 | 23 | =vgpp |
| 337X045 | 3 | 3 | 5 | Δ>SOT | 9 | 6 | 8 | between |
| 338X424 | 1 | **0** | 2 | Δ>vgpp | 9 | 6 | 9 | =vgpp |
| 337X233 | 3 | 3 | 3 | match | 12 | 5 | 9 | between |
| 290T434 | 1 | 1 | 1 | match | 8 | 4 | 5 | between |
| 338X765 | 2 | 2 | 1 | Δ<SOT | 27 | 9 | 19 | between |
| 338X724 | **0** | **0** | 1 | **Δ has data, SOT=0** | 14 | 3 | 13 | between |
| 290T484 | **0** | **0** | 1 | **Δ has data, SOT=0** | 4 | 2 | 4 | =vgpp |
| 338X714 | 4 | 3 | 1 | Δ<SOT | 4 | 3 | 4 | =vgpp |
| 337X134 | 1 | 1 | **0** | **NO CHUNKS** | 14 | 5 | **0** | **NO CHUNKS** |
| 337X789 | 2 | 2 | **0** | **NO CHUNKS** | 6 | 3 | **0** | **NO CHUNKS** |

---

## Our Query Results vs Feng's Table

### Queries Run

| Query | Table | Warehouse | Status |
|-------|-------|-----------|--------|
| Q1 — FSR vgpp | `vgpp.fsr_std_views.fsr_field_vision_field_services_report_psot` | gev-gp-dev-warehouse-pmce | Done |
| Q2 — FSR vgpd | `vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot` | gev-gp-dev-warehouse-pmce | Done |
| Q3 — FSR Delta | `main.gp_services_sdg_poc.field_service_report_gt_litellm` | gev-gp-dev-warehouse-pmce | Done |
| Q4 — ER vgpp | `vgpp.qlt_std_views.u_pac` | gev-gp-dev-warehouse-pmce | Done |
| Q5 — ER vgpd | `vgpd.qlt_std_views.u_pac` | gev-gp-dev-warehouse-pmce | Done |
| Q6 — ER Delta | `main.gp_services_sdg_poc.engineering_report_chunk` | AI dev workspace | Done |

### Comparison (Feng / Ours)

| ESN | FSR vgpp | FSR vgpd | FSR Doc(Δ) | ER vgpp | ER vgpd | ER Case(Δ) |
|-----|----------|----------|------------|---------|---------|------------|
| 290T434 | 1 / 1 | 1 / 1 | 1 / 1 | 8 / 8 | 4 / 4 | 5 / 5 |
| 290T484 | 0 / 0 | 0 / 0 | 1 / 1 | **4 / 5** | 2 / 2 | 4 / 4 |
| 290T503 | 2 / 2 | 2 / 2 | 3 / 3 | 18 / 18 | 2 / 2 | 7 / 7 |
| 290T530 | 3 / 3 | 3 / 3 | 3 / 3 | 67 / 67 | 21 / 21 | 42 / 42 |
| 290T532 | 0 / 0 | 0 / 0 | 3 / 3 | 24 / 24 | 13 / 13 | 19 / 19 |
| 290T543 | 1 / 1 | 1 / 1 | 3 / 3 | 63 / 63 | 22 / 22 | 42 / 42 |
| 290T577 | 2 / 2 | 2 / 2 | 1 / 1 | 23 / 23 | 16 / 16 | 23 / 23 |
| 290T658 | 2 / 2 | 2 / 2 | 2 / 2 | 22 / 22 | 9 / 9 | 19 / 19 |
| 290T762 | 1 / 1 | 1 / 1 | 4 / 4 | 25 / 25 | 4 / 4 | 20 / 20 |
| 337X045 | 3 / 3 | 3 / 3 | 5 / 5 | 9 / 9 | 6 / 6 | 8 / 8 |
| 337X134 | 1 / 1 | 1 / 1 | 0 / 0 | 14 / 14 | 5 / 5 | 0 / 0 |
| 337X233 | 3 / 3 | 3 / 3 | 3 / 3 | 12 / 12 | 5 / 5 | 9 / 9 |
| 337X305 | 1 / 1 | 1 / 1 | 2 / 2 | 5 / 5 | 1 / 1 | 4 / 4 |
| 337X330 | 0 / 0 | 0 / 0 | 2 / 2 | 5 / 5 | 3 / 3 | 5 / 5 |
| 337X336 | 0 / 0 | 0 / 0 | 4 / 4 | 75 / 75 | 24 / 24 | 67 / 67 |
| 337X369 | 2 / 2 | 2 / 2 | 2 / 2 | 39 / 39 | 8 / 8 | 22 / 22 |
| 337X708 | 1 / 1 | 1 / 1 | 4 / 4 | 10 / 10 | 3 / 3 | 9 / 9 |
| 337X709 | 1 / 1 | 1 / 1 | 5 / 5 | 14 / 14 | 9 / 9 | 13 / 13 |
| 337X789 | 2 / 2 | 2 / 2 | 0 / 0 | 6 / 6 | 3 / 3 | 0 / 0 |
| 338X408 | 2 / 2 | 2 / 2 | 5 / 5 | 19 / 19 | 7 / 7 | 14 / 14 |
| 338X424 | 1 / 1 | 0 / 0 | 2 / 2 | 9 / 9 | 6 / 6 | 9 / 9 |
| 338X425 | 1 / 1 | 1 / 1 | 2 / 2 | 38 / 38 | 23 / 23 | 34 / 34 |
| 338X426 | 2 / 2 | 2 / 2 | 3 / 3 | 41 / 41 | 18 / 18 | 41 / 41 |
| 338X427 | 2 / 2 | 2 / 2 | 2 / 2 | 17 / 17 | 11 / 11 | 17 / 17 |
| 338X713 | 1 / 1 | 1 / 1 | 2 / 2 | 7 / 7 | 5 / 5 | 6 / 6 |
| 338X714 | 4 / 4 | 3 / 3 | 1 / 1 | 4 / 4 | 3 / 3 | 4 / 4 |
| 338X722 | 0 / 0 | 0 / 0 | 4 / 4 | 8 / 8 | 0 / 0 | 3 / 3 |
| 338X724 | 0 / 0 | 0 / 0 | 1 / 1 | 14 / 14 | 3 / 3 | 13 / 13 |
| 338X765 | 2 / 2 | 2 / 2 | 1 / 1 | 27 / 27 | 9 / 9 | 19 / 19 |
| 761X004 | 4 / 4 | 3 / 3 | 4 / 4 | 46 / 46 | 18 / 18 | 33 / 33 |

### Summary

| Column | Verified | Mismatches | Notes |
|--------|----------|------------|-------|
| FSR vgpp (Q1) | 30/30 | 0 | Exact match |
| FSR vgpd (Q2) | 30/30 | 0 | Exact match |
| FSR Doc(Δ) (Q3) | 30/30 | 0 | Exact match |
| ER vgpp (Q4) | 29/30 | **1** | 290T484: Feng=4, Ours=5 (likely new ER case added since Feng's query) |
| ER vgpd (Q5) | 30/30 | 0 | Exact match |
| ER Case(Δ) (Q6) | 30/30 | 0 | Exact match (ran on AI dev workspace) |

**Overall: 179/180 values verified (99.4%).** The single mismatch on 290T484 ER vgpp is consistent with a new ER case being added to the SOT after Feng ran his query.

### Workspace Note

- Q1-Q5: ran on **NRC workspace** (`gevernova-nrc-workspace`) using `gev-gp-dev-warehouse-pmce`
- Q6: ran on **AI dev workspace** (`gevernova-ai-dev-dbr`) — `engineering_report_chunk` table is accessible there
- Feng confirmed he uses the AI dev workspace per the DS Confluence page
