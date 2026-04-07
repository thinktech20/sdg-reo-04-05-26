## Databricks Connection - Detailed Steps & SQL Scripts

### Prerequist
Step 1: Get Access
Join the appropriate OneIDM Distribution Lists at:
https://oneidm.ge.com/faces/modules/my_groups/distribution_lists_join.xhtml
At minimum, join:
@GE Vernova DBR DS Team (POC environment access)
Plus the relevant data DLs (VGPD/VGPP) depending on what data you need
Step 2: Generate a Personal Access Token (PAT)
Once you have workspace access, generate a PAT one time from:
https://gevernova-nrc-workspace.cloud.databricks.com/#settings/access-tokens

Step 3: Find Your Warehouse ID
    In Databricks console:
    Go to SQL Warehouses (left sidebar)
    Click on dev-ml-sql (or your warehouse name)
    Copy the HTTP Path from "Connection Details" tab
    It will look like: /sql/1.0/warehouses/abc123def456

Step 4: Connect from Your local environment
Option A — Databricks SQL Connector (Python, lightest weight) - see below examples
Option B — REST API (curl or any HTTP client)
Option C — databricks-connect (full Spark from local)

---

### Step 1: Gather Connection Details

From Databricks Console → SQL Warehouses → Connection Details:

| Parameter | Value |
|-----------|-------|
| **Server Hostname** | `gevernova-nrc-workspace.cloud.databricks.com` |
| **HTTP Path** | `/sql/1.0/warehouses/abc123def456` |  
| **Access Token** | `this is your pat from prerequisite steps` |

---

### Step 2: Install Databricks SQL Connector

```bash
# In WSL with venv activated
cd ~/code/unit-risk-agent
source .venv/bin/activate
pip install databricks-sql-connector
```

**Note**: Behind corporate proxy, set:
```bash
export https_proxy=http://PITC-Zscaler-Global-3PRZ.proxy.corporate.ge.com:80
```

---

### Step 3: Basic Connection Test

```python
from databricks import sql

conn = sql.connect(
    server_hostname="gevernova-nrc-workspace.cloud.databricks.com",
    http_path="/sql/1.0/warehouses/daff57b69fee5745",
    access_token="this is your pat from prerequisite steps"
)

cur = conn.cursor()
cur.execute("SELECT 1 as test")
print(cur.fetchone())  # Row(test=1)
cur.close()
conn.close()
```

**Important**: SQL Warehouse must be **Running** (not Stopped). First query after idle takes 30-90 seconds for cold start.

---

### Step 4: SQL Scripts for 4 Data Sources

#### 4.1 ER Cases (Engineering Requests)

**Table**: `vgpd.qlt_std_views.u_pac`

```sql
SELECT 
    number,                    -- ER case ID (e.g., "ER-20220215-0237")
    u_serial_number,           -- ESN
    short_description,         -- Brief issue description
    description_,              -- Full description
    close_notes,               -- Resolution notes
    u_resolve_notes,           -- Resolution details
    u_field_action_taken,      -- Field actions
    u_status,                  -- Status (Open/Closed)
    priority,                  -- Priority level
    u_component,               -- Component (Generator, Stator, Rotor)
    u_sub_component,           -- Sub-component
    equipment_code,            -- Equipment code (7FH2, 9FA, etc.)
    opened_at,                 -- Date opened
    closed_at,                 -- Date closed
    u_type,                    -- Issue type
    work_notes                 -- Work notes
FROM vgpd.qlt_std_views.u_pac
WHERE u_serial_number = '299537'
ORDER BY opened_at DESC
LIMIT 50;
```
---

#### 4.2 IBAT Equipment Metadata

**Tables**: 
- `vgpd.prm_std_views.IBAT_EQUIPMENT_MST` (equipment)
- `vgpd.prm_std_views.IBAT_PLANT_MST` (plant/site)

```sql
SELECT 
    e.equip_serial_number,     -- ESN
    e.equipment_type,          -- "Generator"
    e.equipment_code,          -- "7FH2", "9FA", etc.
    e.equipment_class,         -- Equipment class
    e.equipment_name,          -- Equipment name
    e.duty_cycle,              -- Duty cycle
    e.contract_type,           -- Contract type
    e.sales_channel,           -- Sales channel
    e.equipment_comm_date,     -- Commercial operation date
    e.engine_first_fire_date,  -- First fire date
    e.last_updated_date,       -- Last updated
    e.cooling_system,          -- "Hydrogen - Conventional Cooled Stator"
    p.plant_name,              -- Site name
    p.site_customer_name,      -- Customer name
    p.site_country,            -- Country
    p.site_state,              -- State
    p.industry                 -- Industry
FROM vgpd.prm_std_views.IBAT_EQUIPMENT_MST e
LEFT JOIN vgpd.prm_std_views.IBAT_PLANT_MST p 
    ON e.plant_sys_id_fk = p.plant_sys_id
WHERE e.equip_serial_number = '299537';
```

---

#### 4.3 PRISM Risk Data

**Table**: `vgpd.seg_std_views.sot_seg_fmea_wo_models_gen_psot`

```sql
SELECT 
    TURBINE_NUMBER,            -- ESN
    MODEL_ID,                  -- Model ID
    MODEL_DESC,                -- Model description
    REF_DATE,                  -- Reference date
    PER_PROB_FLR,              -- Probability of failure
    ADJ_RISK,                  -- Adjusted risk score (0-100)
    GEN_COD,                   -- Generator code
    LAST_REWIND,               -- Last rewind date (if any)
    RISK_PROFILE,              -- "Rotor Low Risk", "Stator High Risk"
    RISK_RULE                  -- Risk rule applied
FROM vgpd.seg_std_views.sot_seg_fmea_wo_models_gen_psot
WHERE TURBINE_NUMBER = '299537'
ORDER BY REF_DATE DESC
LIMIT 1;
```

**Sample Result**:
```
Turbine: 299537
Model: 7FH2, 7FH2B Generator Rotor Rewind - Schenectady C Coil
Adj Risk: 0.039 (Low)
Risk Profile: Rotor Low Risk
Last Rewind: None

```

---

#### 4.4 FSR Reports (Field Service Reports)

**Table**: `vgpd.fsr_std_views.fsr_pdf_ref`
**Table**: `vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot`


```sql
SELECT 
    id,                        -- Unique report ID (can join with fsr_pdf_ref.rd_report_id)
    esn,                       -- ESN
    start_date,                -- Event start date (NOT event_start_date)
    end_date,                  -- Event end date
    report_name,               -- Report name/title
    outage_type,               -- Outage type
    executive_summary,         -- The content you need (exists for ~14% of records)
    site_name,                 -- Site name
    customer_name,             -- Customer name
    technology_type            -- Technology type
FROM vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot
WHERE esn = '299537'
ORDER BY start_date DESC
LIMIT 20;
```
```sql
SELECT 
    fv.id,
    fv.esn,
    fv.start_date,
    fv.report_name,
    fv.outage_type,
    fv.executive_summary,
    pdf.filename
FROM vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot fv
LEFT JOIN vgpd.fsr_std_views.fsr_pdf_ref pdf 
    ON fv.id = pdf.rd_report_id
WHERE fv.esn = '299537'
ORDER BY fv.start_date DESC
LIMIT 20;
```
**Query Time**: ~10s


---

### Step 5: Complete Python Test Script 

```python
#!/usr/bin/env python3
"""Test all 4 Databricks data sources"""

from databricks import sql
import time

# Connection config
DATABRICKS_HOST = "gevernova-nrc-workspace.cloud.databricks.com"
DATABRICKS_HTTP_PATH = "/sql/1.0/warehouses/abc123def456"
DATABRICKS_TOKEN = "this is your pat from prerequisite steps"

def get_connection():
    return sql.connect(
        server_hostname=DATABRICKS_HOST,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN
    )

def test_er_cases(esn: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
            SELECT number, u_serial_number, short_description,
                    description_, close_notes, u_resolve_notes,
                    u_field_action_taken, u_status, priority,
                    u_component, u_sub_component, equipment_code,
                    opened_at, closed_at, u_type, work_notes
            FROM vgpd.qlt_std_views.u_pac
            WHERE u_serial_number = '{esn}'
            ORDER BY opened_at DESC LIMIT 50
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def test_ibat(esn: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
            SELECT 
                e.equip_serial_number,
                e.equipment_type,
                e.equipment_code,
                e.equipment_class,
                e.equipment_name,
                e.duty_cycle,
                e.contract_type,
                e.sales_channel,
                e.equipment_comm_date,
                e.engine_first_fire_date,
                e.last_updated_date,
                e.cooling_system,
                p.plant_name,
                p.site_customer_name,
                p.site_country,
                p.site_state,
                p.industry
            FROM vgpd.prm_std_views.IBAT_EQUIPMENT_MST e
            LEFT JOIN vgpd.prm_std_views.IBAT_PLANT_MST p 
                ON e.plant_sys_id_fk = p.plant_sys_id
            WHERE e.equip_serial_number = '{esn}'
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows[0] if rows else None

def test_prism(esn: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
            SELECT TURBINE_NUMBER, MODEL_ID, MODEL_DESC,
                    REF_DATE, PER_PROB_FLR, ADJ_RISK,
                    GEN_COD, LAST_REWIND, RISK_PROFILE, RISK_RULE
            FROM vgpd.seg_std_views.sot_seg_fmea_wo_models_gen_psot
            WHERE TURBINE_NUMBER = '{esn}'
            ORDER BY REF_DATE DESC LIMIT 1
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows[0] if rows else None

def test_fsr(esn: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
            SELECT id, esn, start_date, end_date, report_name, outage_type,
                    executive_summary, site_name, customer_name, technology_type
            FROM vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot
            WHERE esn = '{esn}'
            ORDER BY event_start_date DESC LIMIT 20
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

if __name__ == "__main__":
    esn = "299537"
    
    print(f"Testing data sources for ESN: {esn}\n")
    
    print("1. ER Cases:", test_er_cases(esn))
    print("2. IBAT:", test_ibat(esn))
    print("3. PRISM:", test_prism(esn))
    print("4. FSR:", test_fsr(esn))
```

---

### Summary: What We Learned

| Issue Encountered | Solution |
|-------------------|----------|
| Proxy blocking pip install | Set `https_proxy` environment variable |
| Query hangs forever | SQL Warehouse was stopped → Start it in Databricks Console |
| Cold start delay | First query takes 30-90s while warehouse warms up |
| use vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot as main table for FSR |
| To get the PDF filename, join with vgpd.fsr_std_views.fsr_pdf_ref on the id = rd_report_id: |

---



