"""End-to-end run: build the DuckDB model, run checks, write the report JSON, Excel workbook and CSV extracts.

    python -m hqs.run            # uses data/raw (python -m hqs.ingest downloads it)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import build, checks, config, excel, ingest


def _clean(v):
    if isinstance(v, float):
        return None if v != v else round(v, 4)
    return v


def _rows(con, sql, params=None):
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [{c: _clean(v) for c, v in zip(cols, r)} for r in cur.fetchall()]


def make_report(con, raw_counts: dict, check_rows: list[dict]) -> dict:
    releases = list(config.RELEASES)
    latest = releases[-1]
    summary = _rows(con, """
        SELECT release,
               count(DISTINCT facility_id)                                          AS hospitals,
               count(DISTINCT facility_id) FILTER (WHERE hospital_type = 'Acute Care Hospitals') AS acute_hospitals,
               count(overall_star_rating)                                           AS star_rated
        FROM dim_hospital GROUP BY 1 ORDER BY 1""")
    cells = _rows(con, """
        SELECT release, count(*) AS cells, count(DISTINCT source || measure_id) AS measures,
               count(*) FILTER (WHERE status = 'suppressed')          AS suppressed,
               count(*) FILTER (WHERE status = 'reported_footnoted')  AS footnoted,
               count(*) FILTER (WHERE status = 'not_available')       AS not_available,
               count(*) FILTER (WHERE status = 'missing')             AS missing,
               count(*) FILTER (WHERE footnote IS NOT NULL)           AS any_footnote
        FROM fact_measure GROUP BY 1 ORDER BY 1""")
    peer = _rows(con, "SELECT * FROM mart_peer ORDER BY kpi, peer_group, release")
    focus = {}
    for st in config.FOCUS_STATES:
        focus[st] = _rows(con, """
            SELECT s.facility_id, s.facility_name, s.city, s.hospital_type, s.overall_star_rating, s.err_mean,
                   s.err_conditions_above_1, s.err_conditions_reported, s.sir_clabsi, s.sir_cauti, s.sir_mrsa,
                   s.sir_cdiff, s.hcahps_nurse_comm, s.hcahps_rating_9_10, s.hcahps_recommend, s.hcahps_surveys,
                   s.ed_median_minutes, s.ed_left_without_seen_pct, p.err_pctile, p.ed_pctile, p.hcahps_rating_pctile
            FROM mart_scorecard s LEFT JOIN mart_percentile p USING (release, facility_id)
            WHERE s.release = ? AND s.state = ? ORDER BY s.facility_name""", [latest, st])
    dist = {
        "err_mean": [r[0] for r in con.execute(
            "SELECT round(err_mean, 3) FROM mart_scorecard WHERE release = ? AND err_mean IS NOT NULL "
            "AND hospital_type = 'Acute Care Hospitals'", [latest]).fetchall()],
        "ed_median_minutes": [r[0] for r in con.execute(
            "SELECT ed_median_minutes FROM mart_scorecard WHERE release = ? AND ed_median_minutes IS NOT NULL "
            "AND hospital_type = 'Acute Care Hospitals'", [latest]).fetchall()],
    }
    hrrp_by_condition = _rows(con, """
        SELECT release, measure_id, count(*) AS rows,
               count(excess_readmission_ratio) AS err_reported,
               median(excess_readmission_ratio) AS err_median,
               count(*) FILTER (WHERE excess_readmission_ratio > 1) AS err_above_1,
               count(*) FILTER (WHERE status = 'suppressed') AS suppressed
        FROM mart_hrrp GROUP BY ALL ORDER BY 1, 2""")
    star_dist = _rows(con, """
        SELECT release, state_group, overall_star_rating AS stars, count(*) AS hospitals FROM (
            SELECT release, CASE WHEN state IN ('IN', 'NJ') THEN state ELSE 'Other' END AS state_group,
                   overall_star_rating FROM dim_hospital
            WHERE hospital_type = 'Acute Care Hospitals' AND overall_star_rating IS NOT NULL)
        GROUP BY ALL ORDER BY 1, 2, 3""")
    return {
        "releases": releases,
        "latest_release": latest,
        "raw_row_counts": raw_counts,
        "summary": summary,
        "cells": cells,
        "checks": check_rows,
        "checks_passed": sum(c["passed"] for c in check_rows),
        "checks_total": len(check_rows),
        "quality_flags": checks.quality_flags(con),
        "measure_changes": checks.measure_changes(con),
        "peer": peer,
        "focus_states": focus,
        "distributions": dist,
        "hrrp_by_condition": hrrp_by_condition,
        "star_distribution": star_dist,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true", help="fetch CMS files first")
    ap.add_argument("--report", default=str(config.DOCS_DATA / "report.json"))
    ap.add_argument("--xlsx", default=str(config.ROOT / "deliverables" / "hospital_quality_scorecard.xlsx"))
    args = ap.parse_args(argv)
    t0 = time.time()
    if args.download:
        ingest.download()
    ingest.write_manifest()
    con, raw_counts = build.build()
    check_rows = checks.run_all(con, raw_counts)
    report = make_report(con, raw_counts, check_rows)
    report["runtime_seconds"] = round(time.time() - t0, 1)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=1, default=str))
    excel.write_workbook(con, report, Path(args.xlsx))
    build.export(con)
    for c in check_rows:
        print(f"{'PASS' if c['passed'] else 'FAIL'} {c['id']} {c['name']}: {c['detail']}")
    print(f"{report['checks_passed']}/{report['checks_total']} checks passed in {report['runtime_seconds']}s")
    return 0 if report["checks_passed"] == report["checks_total"] else 1


if __name__ == "__main__":
    sys.exit(main())
