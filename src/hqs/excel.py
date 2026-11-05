"""Excel deliverable: data dictionary, requirements, test cases, quality flags, state scorecards, trend."""
from __future__ import annotations

from pathlib import Path

import duckdb
from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import kpis

HEAD = PatternFill("solid", fgColor="1F3A5F")
GOOD = PatternFill("solid", fgColor="D8EFD9")
BAD = PatternFill("solid", fgColor="F6D5D2")

SCORECARD_COLS = [
    ("facility_id", "CCN"), ("facility_name", "Hospital"), ("city", "City"), ("hospital_type", "Type"),
    ("overall_star_rating", "Stars"), ("err_mean", "ERR mean"), ("err_conditions_above_1", "Conditions ERR>1"),
    ("err_conditions_reported", "Conditions reported"), ("sir_clabsi", "CLABSI SIR"), ("sir_cauti", "CAUTI SIR"),
    ("sir_mrsa", "MRSA SIR"), ("sir_cdiff", "C.diff SIR"), ("hcahps_nurse_comm", "Nurse comm %"),
    ("hcahps_rating_9_10", "Rating 9-10 %"), ("hcahps_recommend", "Recommend %"), ("hcahps_surveys", "Surveys"),
    ("ed_median_minutes", "ED median min"), ("ed_left_without_seen_pct", "LWBS %"),
    ("flagged_cells", "Flagged cells"),
]
# column key -> (benchmark kpi in mart_peer, lower_is_better)
BENCH = {
    "overall_star_rating": ("Overall star rating (mean)", False),
    "err_mean": ("ERR (median of hospital mean ERR)", True),
    "sir_clabsi": ("SIR HAI_1", True), "sir_cauti": ("SIR HAI_2", True),
    "sir_mrsa": ("SIR HAI_5", True), "sir_cdiff": ("SIR HAI_6", True),
    "hcahps_nurse_comm": ("Top box H_COMP_1_A_P", False),
    "hcahps_rating_9_10": ("Top box H_HSP_RATING_9_10", False),
    "hcahps_recommend": ("Top box H_RECMND_DY", False),
    "ed_median_minutes": ("ED median minutes (OP_18b)", True),
}
KEY_MEASURES = ("STAR_OVERALL", "READM-30-HF-HRRP", "READM-30-PN-HRRP", "READM-30-AMI-HRRP", "READM-30-COPD-HRRP",
                "HAI_1_SIR", "HAI_2_SIR", "HAI_5_SIR", "HAI_6_SIR", "H_COMP_1_A_P", "H_HSP_RATING_9_10",
                "H_RECMND_DY", "OP_18b", "OP_22")


def _header(ws, row, labels):
    for j, lab in enumerate(labels, 1):
        c = ws.cell(row=row, column=j, value=lab)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = HEAD
        c.alignment = Alignment(wrap_text=True, vertical="top")


def _table(ws, labels, rows, widths=None, start=1):
    _header(ws, start, labels)
    for i, r in enumerate(rows, start + 1):
        for j, v in enumerate(r, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.alignment = Alignment(wrap_text=isinstance(v, str) and len(v) > 40, vertical="top")
    for j in range(1, len(labels) + 1):
        ws.column_dimensions[get_column_letter(j)].width = (widths or {}).get(j, 16)
    ws.freeze_panes = ws.cell(row=start + 1, column=1)


def scorecard_rows(con, release: str, state: str) -> list[dict]:
    keys = ", ".join(f"'{k}'" for k in KEY_MEASURES)
    df = con.execute(f"""
        WITH flags AS (
            SELECT facility_id, count(*) FILTER (WHERE status IN ('suppressed', 'not_available', 'missing',
                                                               'reported_footnoted')) AS flagged_cells
            FROM fact_measure WHERE release = ? AND measure_id IN ({keys}) GROUP BY 1)
        SELECT s.*, coalesce(f.flagged_cells, 0) AS flagged_cells
        FROM mart_scorecard s LEFT JOIN flags f USING (facility_id)
        WHERE s.release = ? AND s.state = ?
        ORDER BY s.hospital_type, s.facility_name""", [release, release, state]).df()
    return df.to_dict("records")


def peer_values(con, release: str, group: str) -> dict:
    return dict(con.execute("SELECT kpi, value FROM mart_peer WHERE release = ? AND peer_group = ?",
                            [release, group]).fetchall())


def write_workbook(con: duckdb.DuckDBPyConnection, report: dict, path: Path, states=("IN", "NJ")) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Read me"
    latest = report["latest_release"]
    lines = [
        "Hospital Quality Scorecard (CMS Care Compare)",
        f"Releases: {', '.join(report['releases'])}. Latest release on the state tabs: {latest}.",
        "Source: CMS Provider Data Catalog, hospitals theme (public CSV). Built by src/hqs/run.py from DuckDB.",
        "Tabs: Data dictionary, Requirements, Test cases, Quality flags, Measure changes, <state> scorecard, Trend.",
        "Green / red on the scorecard = better / worse than the national acute care benchmark for that KPI.",
        "Blank KPI cells are suppressed, unavailable or missing at CMS; 'Flagged cells' counts them per hospital.",
    ]
    for i, t in enumerate(lines, 1):
        ws.cell(row=i, column=1, value=t).font = Font(bold=(i == 1), size=14 if i == 1 else 11)
    ws.column_dimensions["A"].width = 120

    ws = wb.create_sheet("Data dictionary")
    cols = ["kpi", "domain", "definition", "source_file", "cms_field", "hospital_formula", "peer_rule",
            "direction", "column", "dax"]
    _table(ws, [c.replace("_", " ").title() for c in cols], [[d[c] for c in cols] for d in kpis.KPI_DEFS],
           {1: 26, 3: 50, 4: 34, 5: 40, 6: 44, 7: 44, 9: 30, 10: 30})

    ws = wb.create_sheet("Requirements")
    _table(ws, ["Requirement", "Description", "Evidenced by"],
           [[r, d, ", ".join(k for k, v in kpis.CHECK_REQ.items() if v == r)] for r, d in kpis.REQUIREMENTS],
           {2: 90, 3: 30})

    ws = wb.create_sheet("Test cases")
    rows = [[c["id"], kpis.CHECK_REQ.get(c["id"], ""), c["area"], c["name"], c["checked"], c["failed"],
             "PASS" if c["passed"] else "FAIL", c["detail"]] for c in report["checks"]]
    _table(ws, ["Test", "Requirement", "Area", "Test case", "Rows checked", "Rows failed", "Result", "Detail"],
           rows, {4: 60, 8: 50})
    ws.conditional_formatting.add(f"G2:G{len(rows) + 1}", CellIsRule(operator="equal", formula=['"PASS"'], fill=GOOD))
    ws.conditional_formatting.add(f"G2:G{len(rows) + 1}", CellIsRule(operator="equal", formula=['"FAIL"'], fill=BAD))

    ws = wb.create_sheet("Quality flags")
    _table(ws, ["Release", "Source file", "Cell status", "Cells", "% of file"],
           [[q["release"], q["source"], q["status"], q["cells"], q["pct"]] for q in report["quality_flags"]])
    r0 = len(report["quality_flags"]) + 4
    ws.cell(row=r0 - 1, column=1, value="Footnote codes (CMS Footnote Crosswalk)").font = Font(bold=True)
    fns = con.execute(
        "SELECT footnote_code, footnote_text FROM dim_footnote ORDER BY try_cast(footnote_code AS INT)").fetchall()
    _table(ws, ["Footnote", "Meaning"], fns, {2: 100}, start=r0)
    ws.freeze_panes = "A2"

    ws = wb.create_sheet("Measure changes")
    _table(ws, ["Source", "Measure ID", "Measure name", "First release", "Last release"],
           [[m["source"], m["measure_id"], m["measure_name"], m["first_release"], m["last_release"]]
            for m in report["measure_changes"]], {2: 30, 3: 90})

    nat = peer_values(con, latest, "National acute care")
    for st in states:
        ws = wb.create_sheet(f"{st} scorecard")
        rows = scorecard_rows(con, latest, st)
        stp = peer_values(con, latest, f"{st} acute care")
        bench = []
        for label, pv in [(f"{st} acute care benchmark", stp), ("National acute care benchmark", nat)]:
            bench.append([None, label] + [None] * 2 + [
                (round(pv[BENCH[k][0]], 3) if k in BENCH and pv.get(BENCH[k][0]) is not None else None)
                for k, _ in SCORECARD_COLS[4:]])
        data = [[r.get(k) if r.get(k) == r.get(k) else None for k, _ in SCORECARD_COLS] for r in rows]
        _table(ws, [lab for _, lab in SCORECARD_COLS], bench + data, {2: 40, 3: 16, 4: 24})
        for r in (2, 3):
            for j in range(1, len(SCORECARD_COLS) + 1):
                ws.cell(row=r, column=j).font = Font(bold=True, italic=True)
        n = len(data) + 3
        for j, (k, _) in enumerate(SCORECARD_COLS, 1):
            if k not in BENCH or nat.get(BENCH[k][0]) is None:
                continue
            col = get_column_letter(j)
            ref = f"${col}$3"
            better, worse = ("lessThan", "greaterThan") if BENCH[k][1] else ("greaterThan", "lessThan")
            rng = f"{col}4:{col}{n}"
            ws.conditional_formatting.add(rng, CellIsRule(operator=better, formula=[ref], fill=GOOD))
            ws.conditional_formatting.add(rng, CellIsRule(operator=worse, formula=[ref], fill=BAD))
        ws.freeze_panes = "C4"

    ws = wb.create_sheet("Trend")
    tr = con.execute("""
        SELECT kpi, peer_group, release, round(value, 3), hospitals FROM mart_peer
        WHERE peer_group IN ('National acute care', 'IN acute care', 'NJ acute care')
        ORDER BY kpi, peer_group, release""").fetchall()
    _table(ws, ["KPI", "Peer group", "Release", "Value", "Hospitals"], tr, {1: 36, 2: 24})

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path
