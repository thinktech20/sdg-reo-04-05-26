"""
Thorough Naksha FSR Genie Room Test — All Tables
Tests EVERY table visible in the room with multiple query patterns + retries.
Goal: Build a reliability matrix before we hardcode SQL templates into tools.
"""
import requests, json, time, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = "https://qpbq9edtta.execute-api.us-east-1.amazonaws.com/QA/databricks-proxy-chatbot-dev"
HEADERS = {"Content-Type": "application/json"}
SYSTEM = "BUSINESS: gas_power\nDOMAIN: global_services\nSUBDOMAIN: fsr\nUSER_EMAIL: test@ge.com"

RETRIES = 3
DELAY = 4

# ════════════════════════════════════════════════════════════════════
# EXACT 9 tables from the FSR Genie room (confirmed from Naksha UI)
# ════════════════════════════════════════════════════════════════════
TABLES = {
    # 1. fsr_std_views.event_equipment_dtls_event_vision_sot
    "event_equip_dtls": {
        "fqn": "vgpd.fsr_std_views.event_equipment_dtls_event_vision_sot",
        "cols": "ev_equipment_event_id, ev_serial_number, ev_equipment_description, ev_model, ev_technology",
        "where": "ev_serial_number = '296045'",
    },
    # 2. fsr_std_views.eventmgmt_event_vision_sot
    "event_master": {
        "fqn": "vgpd.fsr_std_views.eventmgmt_event_vision_sot",
        "cols": "ev_equipment_event_id, ev_event_type, ev_event_status, ev_event_start_date, ev_event_end_date",
        "where": None,
    },
    # 3. fsr_std_views.fsr_field_vision_field_services_report_psot
    "fsr_reports": {
        "fqn": "vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot",
        "cols": "id, esn, report_name, site_name, customer_name, start_date, end_date",
        "where": "esn = '296045'",
    },
    # 4. fsr_std_views.fsr_unit_risk_matrix_view
    "fsr_unit_risk_matrix": {
        "fqn": "vgpd.fsr_std_views.fsr_unit_risk_matrix_view",
        "cols": "equipment_type, equipment_sub_type, serial_number, risk_component, category, risk_rating, current_risk_score, max_risk_score, risk_factor, risk_driver, as_of_date, site_name, plant_name, applicable_data_objects",
        "where": "serial_number = '296045'",
    },
    # 5. fsr_std_views.scope_schedule_summary_event_vision_sot  ← NEW
    "scope_schedule": {
        "fqn": "vgpd.fsr_std_views.scope_schedule_summary_event_vision_sot",
        "cols": "ev_equipment_event_id, ev_event_type, ev_scope_summary, ev_schedule_summary, ev_event_status",
        "where": None,
    },
    # 6. prm_std_views.ibat_equipment_mst
    "ibat_equipment": {
        "fqn": "vgpd.prm_std_views.ibat_equipment_mst",
        "cols": "serial_number, equipment_type, equipment_model, site_name, plant_name, commercial_operation_date",
        "where": "serial_number = '296045'",
    },
    # 7. prm_std_views.ibat_plant_mst
    "ibat_plant": {
        "fqn": "vgpd.prm_std_views.ibat_plant_mst",
        "cols": "plant_id, plant_name, site_name, country, region",
        "where": None,
    },
    # 8. qlt_std_views.u_pac
    "er_cases": {
        "fqn": "vgpd.qlt_std_views.u_pac",
        "cols": "number, u_serial_number, short_description, u_status, priority, u_component, u_sub_component, equipment_code, opened_at, closed_at, u_type",
        "where": "u_serial_number = '316X953'",
    },
    # 9. seg_std_views.seg_fmea_wo_models_gen_psot
    "prism": {
        "fqn": "vgpd.seg_std_views.seg_fmea_wo_models_gen_psot",
        "cols": "model, component, failure_mode, failure_cause, risk_priority_number",
        "where": None,
    },
}


def call_naksha(query):
    payload = {"messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": query},
    ]}
    t0 = time.time()
    try:
        resp = requests.post(API_URL, headers=HEADERS, json=payload, verify=False, timeout=120)
    except Exception as e:
        elapsed = time.time() - t0
        return [], "exception", f"Request failed: {e}", "", elapsed
    elapsed = time.time() - t0
    if resp.status_code == 429:
        return [], "rate_limited", "429 Too Many Requests", "", elapsed
    data = resp.json()
    body = data.get("body", data)
    if isinstance(body, str):
        body = json.loads(body)
    if body.get("statusCode") == 429:
        return [], "rate_limited", "429 in body", "", elapsed
    choices = body.get("choices", [])
    if choices:
        c = choices[0].get("message", {}).get("content", "")
        try:
            parsed = json.loads(c)
        except:
            parsed = {"raw_text": c}
    else:
        parsed = body
    status = parsed.get("status", "unknown")
    answer = parsed.get("answer", parsed.get("message", parsed.get("raw_text", "")))
    rows = parsed.get("data", [])
    sql_echo = parsed.get("sql", "")
    return rows, status, str(answer), sql_echo, elapsed


def test_table(name, info):
    fqn = info["fqn"]
    cols = info["cols"]
    where = info.get("where")
    query = f"SELECT {cols} FROM {fqn}"
    if where:
        query += f" WHERE {where}"
    query += " LIMIT 5"
    for attempt in range(1, RETRIES + 1):
        rows, status, answer, sql_echo, elapsed = call_naksha(query)
        if status == "rate_limited":
            print(f"  ... {name:25s} attempt {attempt}/{RETRIES} | 429 — waiting 10s")
            time.sleep(10)
            continue
        ok = len(rows) > 0
        icon = "PASS" if ok else "FAIL"
        print(f"  {icon} {name:25s} attempt {attempt}/{RETRIES} | rows={len(rows):3d} | {elapsed:.1f}s", end="")
        if ok:
            col_names = list(rows[0].keys())[:5]
            print(f" | cols={col_names}")
            return {"name": name, "ok": True, "rows": len(rows), "attempts": attempt,
                    "cols": list(rows[0].keys()), "sql_echo": sql_echo[:200]}
        else:
            short_answer = answer[:100].replace("\n", " ")
            print(f" | {short_answer}")
        if attempt < RETRIES:
            time.sleep(DELAY)
    return {"name": name, "ok": False, "rows": 0, "attempts": RETRIES, "answer": answer[:200]}


def test_select_star(name, fqn):
    query = f"SELECT * FROM {fqn} LIMIT 3"
    rows, status, answer, sql_echo, elapsed = call_naksha(query)
    ok = len(rows) > 0
    icon = "PASS" if ok else "FAIL"
    print(f"  {icon} {name:25s} SELECT *     | rows={len(rows):3d} | {elapsed:.1f}s")
    return ok


def test_count(name, fqn):
    query = f"SELECT COUNT(*) as total FROM {fqn}"
    rows, status, answer, sql_echo, elapsed = call_naksha(query)
    ok = len(rows) > 0
    total = rows[0].get("total", "?") if rows else "?"
    icon = "PASS" if ok else "FAIL"
    print(f"  {icon} {name:25s} COUNT(*)     | total={str(total):>10s} | {elapsed:.1f}s")
    return ok, total


def main():
    print("=" * 80)
    print("  NAKSHA FSR GENIE ROOM — THOROUGH TABLE TEST")
    print(f"  {len(TABLES)} tables x named-cols query with {RETRIES} retries")
    print("=" * 80)

    # Phase 1
    print(f"\n{'─'*80}")
    print("  PHASE 1: Named-column queries (primary pattern for tools)")
    print(f"{'─'*80}")
    phase1 = {}
    for name, info in TABLES.items():
        result = test_table(name, info)
        phase1[name] = result
        time.sleep(DELAY)

    # Phase 2
    print(f"\n{'─'*80}")
    print("  PHASE 2: SELECT * queries (single attempt)")
    print(f"{'─'*80}")
    phase2 = {}
    for name, info in TABLES.items():
        ok = test_select_star(name, info["fqn"])
        phase2[name] = ok
        time.sleep(DELAY)

    # Phase 3
    print(f"\n{'─'*80}")
    print("  PHASE 3: COUNT(*) queries (single attempt)")
    print(f"{'─'*80}")
    phase3 = {}
    for name, info in TABLES.items():
        ok, total = test_count(name, info["fqn"])
        phase3[name] = {"ok": ok, "total": total}
        time.sleep(DELAY)

    # Phase 4
    print(f"\n{'─'*80}")
    print("  PHASE 4: JOIN queries")
    print(f"{'─'*80}")
    joins = [
        ("Event + Event dtls",
         "SELECT e.ev_equipment_event_id, e.ev_event_type, d.ev_serial_number, d.ev_model "
         "FROM vgpd.fsr_std_views.eventmgmt_event_vision_sot e "
         "JOIN vgpd.fsr_std_views.event_equipment_dtls_event_vision_sot d "
         "ON e.ev_equipment_event_id = d.ev_equipment_event_id LIMIT 5"),
        ("Event + Scope Sched",
         "SELECT e.ev_equipment_event_id, e.ev_event_type, s.ev_scope_summary, s.ev_schedule_summary "
         "FROM vgpd.fsr_std_views.eventmgmt_event_vision_sot e "
         "JOIN vgpd.fsr_std_views.scope_schedule_summary_event_vision_sot s "
         "ON e.ev_equipment_event_id = s.ev_equipment_event_id LIMIT 5"),
        ("IBAT equip + plant",
         "SELECT e.serial_number, e.equipment_type, p.plant_name, p.site_name "
         "FROM vgpd.prm_std_views.ibat_equipment_mst e "
         "JOIN vgpd.prm_std_views.ibat_plant_mst p ON e.plant_name = p.plant_name LIMIT 5"),
        ("FSR + Event equip",
         "SELECT f.report_name, f.esn, d.ev_model, d.ev_technology "
         "FROM vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot f "
         "JOIN vgpd.fsr_std_views.event_equipment_dtls_event_vision_sot d "
         "ON f.esn = d.ev_serial_number LIMIT 5"),
    ]
    phase4 = {}
    for label, query in joins:
        rows, status, answer, sql_echo, elapsed = call_naksha(query)
        ok = len(rows) > 0
        icon = "PASS" if ok else "FAIL"
        print(f"  {icon} {label:25s} | rows={len(rows):3d} | {elapsed:.1f}s")
        if not ok:
            print(f"     {answer[:120]}")
        phase4[label] = ok
        time.sleep(DELAY)

    # Final Report
    print(f"\n{'='*80}")
    print("  FINAL RELIABILITY MATRIX")
    print(f"{'='*80}")
    print(f"  {'Table':<25s} | {'Named cols':^12s} | {'SELECT *':^10s} | {'COUNT(*)':^10s} | {'Row Count':>10s}")
    print(f"  {'─'*25}-+-{'─'*12}-+-{'─'*10}-+-{'─'*10}-+-{'─'*10}")
    for name in TABLES:
        p1 = "PASS" if phase1[name]["ok"] else f"FAIL({phase1[name]['attempts']})"
        p2 = "PASS" if phase2[name] else "FAIL"
        p3_ok = phase3[name]["ok"]
        p3 = "PASS" if p3_ok else "FAIL"
        total = str(phase3[name]["total"]) if p3_ok else "?"
        print(f"  {name:<25s} | {p1:^12s} | {p2:^10s} | {p3:^10s} | {total:>10s}")

    print(f"\n  {'JOIN Test':<25s} | {'Result':^12s}")
    print(f"  {'─'*25}-+-{'─'*12}")
    for label, ok in phase4.items():
        icon = "PASS" if ok else "FAIL"
        print(f"  {label:<25s} | {icon:^12s}")

    p1_pass = sum(1 for v in phase1.values() if v["ok"])
    p2_pass = sum(1 for v in phase2.values() if v)
    p3_pass = sum(1 for v in phase3.values() if v["ok"])
    p4_pass = sum(1 for v in phase4.values() if v)
    total_tables = len(TABLES)

    print(f"\n  PASS RATES:")
    print(f"    Named-cols (with retry): {p1_pass}/{total_tables}")
    print(f"    SELECT * (no retry):     {p2_pass}/{total_tables}")
    print(f"    COUNT(*) (no retry):     {p3_pass}/{total_tables}")
    print(f"    JOINs:                   {p4_pass}/{len(joins)}")

    never_worked = [n for n, v in phase1.items() if not v["ok"]]
    flaky = [n for n in TABLES if phase1[n]["ok"] and phase1[n]["attempts"] > 1]
    reliable = [n for n in TABLES if phase1[n]["ok"] and phase1[n]["attempts"] == 1]

    print(f"\n  TOOL DESIGN RECOMMENDATIONS:")
    if reliable:
        print(f"    RELIABLE (1st attempt): {', '.join(reliable)}")
    if flaky:
        print(f"    FLAKY (needed retry):   {', '.join(flaky)}")
    if never_worked:
        print(f"    FAILED (all retries):   {', '.join(never_worked)}")


if __name__ == "__main__":
    main()
