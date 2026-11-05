"""Data quality checks and KPI tie-outs against the published CMS values.

Each check returns a dict: id, area, name, passed, detail, plus numeric fields.
A failed check does not stop the pipeline; run.py reports and exits non-zero.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import duckdb

ALLOWED_STATUS = ("reported", "reported_footnoted", "suppressed", "not_available", "missing", "categorical")


@dataclass
class Check:
    id: str
    area: str
    name: str
    passed: bool
    detail: str
    checked: int = 0
    failed: int = 0
    extra: dict = field(default_factory=dict)


def _one(con, sql):
    return con.execute(sql).fetchone()


def row_counts(con, raw_counts: dict) -> Check:
    bad = []
    total = 0
    for source, per in raw_counts.items():
        got = dict(con.execute(f"SELECT release, count(*) FROM stg_{source} GROUP BY 1").fetchall())
        fact = dict(con.execute(
            f"SELECT release, count(*) FROM fact_measure WHERE source = '{source}' GROUP BY 1").fetchall())
        for rel, n in per.items():
            total += n
            if got.get(rel) != n or fact.get(rel) != n:
                bad.append(f"{source}/{rel}: raw {n} stg {got.get(rel)} fact {fact.get(rel)}")
    return Check("DQ01", "completeness", "Raw rows = staged rows = fact rows, per file and release",
                 not bad, "; ".join(bad) or f"{total:,} rows carried through", total, len(bad))


def key_unique(con) -> Check:
    n, d = _one(con, """
        SELECT count(*), count(*) - count(DISTINCT (release, source, facility_id, measure_id)) FROM fact_measure""")
    return Check("DQ02", "uniqueness", "One fact row per release x source x hospital x measure",
                 d == 0, f"{d} duplicate keys", n, d)


def orphans(con) -> Check:
    rows = con.execute("""
        SELECT f.source, count(DISTINCT f.release || f.facility_id) AS orphan_hospitals
        FROM fact_measure f
        LEFT JOIN dim_hospital d USING (release, facility_id)
        WHERE d.facility_id IS NULL
        GROUP BY 1 ORDER BY 1""").fetchall()
    n = _one(con, "SELECT count(DISTINCT release || facility_id) FROM fact_measure")[0]
    o = sum(r[1] for r in rows)
    # Measure files can list facilities that dropped out of General Information; report, tolerate < 2%.
    return Check("DQ03", "integrity", "Measure-file hospitals found in General Information (same release)",
                 o / n < 0.02, ", ".join(f"{s}: {k}" for s, k in rows) or "none", n, o,
                 {"orphan_pct": round(100 * o / n, 2)})


def status_coverage(con) -> Check:
    bad = _one(con, f"SELECT count(*) FROM fact_measure WHERE status NOT IN {ALLOWED_STATUS}")[0]
    # numeric KPIs must never land in "categorical" (that would mean an unparsed value)
    cat = _one(con, """
        SELECT count(*) FROM fact_measure
        WHERE status = 'categorical' AND (source IN ('hrrp', 'hai', 'hcahps', 'general')
              OR measure_id IN ('OP_18b', 'OP_22'))""")[0]
    n = _one(con, "SELECT count(*) FROM fact_measure")[0]
    return Check("DQ04", "validity", "Every cell gets a status; no numeric KPI left unparsed",
                 bad == 0 and cat == 0, f"{bad} unknown status, {cat} unparsed numeric KPI cells", n, bad + cat)


def star_range(con) -> Check:
    n, bad = _one(con, """
        SELECT count(overall_star_rating), count(*) FILTER (WHERE overall_star_rating NOT IN (1, 2, 3, 4, 5))
        FROM dim_hospital""")
    return Check("DQ05", "validity", "Overall star rating is an integer 1-5 when reported", bad == 0,
                 f"{bad} out of range", n, bad)


def single_period(con) -> Check:
    rows = con.execute("""
        SELECT release, source, count(DISTINCT period_end) AS ends
        FROM fact_measure WHERE source IN ('hrrp', 'hai') AND period_end IS NOT NULL
        GROUP BY 1, 2 HAVING count(DISTINCT period_end) > 1""").fetchall()
    return Check("DQ06", "consistency", "HRRP and HAI each cover one reporting period per release",
                 not rows, str(rows) if rows else "one period each", 6, len(rows))


def hrrp_suppression(con) -> Check:
    n, bad = _one(con, """
        SELECT count(*),
               count(*) FILTER (WHERE (readmissions IS NULL) <> (discharges IS NULL))
        FROM mart_hrrp WHERE excess_readmission_ratio IS NOT NULL""")
    return Check("DQ07", "consistency",
                 "HRRP: discharges are hidden exactly when readmissions are 'Too Few to Report'",
                 bad == 0, f"{bad} rows where only one of the two is suppressed", n, bad)


def err_tieout(con, tol: float = 0.001) -> Check:
    n, bad, worst = _one(con, f"""
        SELECT count(*), count(*) FILTER (WHERE abs(excess_readmission_ratio - predicted_rate / expected_rate) > {tol}),
               max(abs(excess_readmission_ratio - predicted_rate / expected_rate))
        FROM mart_hrrp
        WHERE excess_readmission_ratio IS NOT NULL AND predicted_rate IS NOT NULL AND expected_rate > 0""")
    return Check("TO01", "tie-out", f"ERR = predicted rate / expected rate (|diff| <= {tol})", bad == 0,
                 f"max abs diff {worst:.5f}", n, bad, {"max_abs_diff": worst})


def sir_tieout(con, tol: float = 0.002) -> Check:
    # SIR and predicted are both published rounded to 3 dp; skip tiny denominators where rounding dominates
    n, bad, worst = _one(con, f"""
        SELECT count(*), count(*) FILTER (WHERE abs(sir - observed / predicted) > {tol}),
               max(abs(sir - observed / predicted))
        FROM mart_hai WHERE sir IS NOT NULL AND observed IS NOT NULL AND predicted >= 1""")
    return Check("TO02", "tie-out", f"HAI SIR = observed / predicted infections (|diff| <= {tol}, predicted >= 1)",
                 bad == 0, f"max abs diff {worst:.5f}", n, bad, {"max_abs_diff": worst})


def sir_in_ci(con) -> Check:
    n, bad = _one(con, """
        SELECT count(*), count(*) FILTER (WHERE sir < coalesce(ci_lower, 0) - 1e-9 OR sir > ci_upper + 1e-9)
        FROM mart_hai WHERE sir IS NOT NULL AND ci_upper IS NOT NULL""")
    return Check("TO03", "tie-out", "HAI SIR lies inside its published 95% confidence interval", bad == 0,
                 f"{bad} outside", n, bad)


def sir_benchmark_label(con) -> Check:
    n, bad = _one(con, """
        SELECT count(*), count(*) FILTER (WHERE
            (c.compared_to_national LIKE 'Better%' AND NOT h.ci_upper < 1)
         OR (c.compared_to_national LIKE 'Worse%' AND NOT coalesce(h.ci_lower, 0) > 1)
         OR (c.compared_to_national LIKE 'No Different%' AND (h.ci_upper < 1 OR coalesce(h.ci_lower, 0) > 1)))
        FROM mart_hai h JOIN mart_hai_compared c USING (release, facility_id, hai_id)
        WHERE h.sir IS NOT NULL AND h.ci_upper IS NOT NULL""")
    return Check("TO04", "tie-out", "CMS 'compared to national' label agrees with the SIR CI vs 1.0", bad == 0,
                 f"{bad} disagreements", n, bad)


def hcahps_sums(con, tol: float = 2.0) -> Check:
    n, bad = _one(con, f"""
        WITH x AS (
            SELECT release, facility_id, regexp_extract(measure_id, '^(H_.*)_(A|U|SN)_P$', 1) AS q,
                   sum(value_num) AS s, count(value_num) AS k
            FROM fact_measure
            WHERE source = 'hcahps' AND regexp_matches(measure_id, '_(A|U|SN)_P$')
            GROUP BY ALL)
        SELECT count(*), count(*) FILTER (WHERE abs(s - 100) > {tol}) FROM x WHERE k = 3""")
    return Check("TO05", "tie-out", f"HCAHPS always + usually + sometimes/never = 100% (+/- {tol}, rounding)",
                 bad == 0, f"{bad} questions off", n, bad)


def scorecard_tieout(con, states=("IN", "NJ")) -> Check:
    """Re-derive scorecard cells straight from the raw staged text, independent of the fact table."""
    st = ", ".join(f"'{s}'" for s in states)
    n, bad = _one(con, f"""
        WITH raw AS (
            SELECT g.release, g."Facility ID" AS facility_id,
                   try_cast(g."Hospital overall rating" AS DOUBLE) AS star,
                   (SELECT try_cast(h."Excess Readmission Ratio" AS DOUBLE) FROM stg_hrrp h
                     WHERE h.release = g.release AND h."Facility ID" = g."Facility ID"
                       AND h."Measure Name" = 'READM-30-HF-HRRP') AS err_hf,
                   (SELECT try_cast(i."Score" AS DOUBLE) FROM stg_hai i
                     WHERE i.release = g.release AND i."Facility ID" = g."Facility ID"
                       AND i."Measure ID" = 'HAI_1_SIR') AS sir_clabsi,
                   (SELECT try_cast(p."HCAHPS Answer Percent" AS DOUBLE) FROM stg_hcahps p
                     WHERE p.release = g.release AND p."Facility ID" = g."Facility ID"
                       AND p."HCAHPS Measure ID" = 'H_HSP_RATING_9_10') AS rating_9_10,
                   (SELECT try_cast(t."Score" AS DOUBLE) FROM stg_tec t
                     WHERE t.release = g.release AND t."Facility ID" = g."Facility ID"
                       AND t."Measure ID" = 'OP_18b') AS op18b
            FROM stg_general g WHERE g."State" IN ({st}))
        SELECT count(*) * 5,
               sum((r.star IS DISTINCT FROM s.overall_star_rating)::INT
                 + (r.err_hf IS DISTINCT FROM s.err_hf)::INT
                 + (r.sir_clabsi IS DISTINCT FROM s.sir_clabsi)::INT
                 + (r.rating_9_10 IS DISTINCT FROM s.hcahps_rating_9_10)::INT
                 + (r.op18b IS DISTINCT FROM s.ed_median_minutes)::INT)
        FROM raw r JOIN mart_scorecard s USING (release, facility_id)""")
    return Check("TO06", "tie-out", f"Scorecard cells for {'/'.join(states)} hospitals equal raw CMS cells",
                 bad == 0, f"{bad} mismatched cells", n, int(bad or 0))


def run_all(con: duckdb.DuckDBPyConnection, raw_counts: dict) -> list[dict]:
    checks = [
        row_counts(con, raw_counts), key_unique(con), orphans(con), status_coverage(con), star_range(con),
        single_period(con), hrrp_suppression(con), err_tieout(con), sir_tieout(con), sir_in_ci(con),
        sir_benchmark_label(con), hcahps_sums(con), scorecard_tieout(con),
    ]
    return [asdict(c) for c in checks]


def quality_flags(con) -> list[dict]:
    """Per release x source: how many cells are reported, footnoted, suppressed, unavailable or missing."""
    rows = con.execute("""
        WITH c AS (SELECT release, source, status, count(*) AS cells FROM fact_measure GROUP BY ALL)
        SELECT release, source, status, cells,
               round(100.0 * cells / sum(cells) OVER (PARTITION BY release, source), 2) AS pct
        FROM c ORDER BY release, source, status""").fetchall()
    return [dict(zip(["release", "source", "status", "cells", "pct"], r)) for r in rows]


def measure_changes(con) -> list[dict]:
    """Measures that appear or disappear between releases (e.g. the 2025 HCAHPS survey update)."""
    rows = con.execute("""
        SELECT source, measure_id, measure_name, first_release, last_release
        FROM dim_measure
        WHERE first_release > (SELECT min(release) FROM fact_measure)
           OR last_release < (SELECT max(release) FROM fact_measure)
        ORDER BY source, measure_id""").fetchall()
    return [dict(zip(["source", "measure_id", "measure_name", "first_release", "last_release"], r)) for r in rows]
