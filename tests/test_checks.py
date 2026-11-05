from __future__ import annotations

import pytest

from hqs import checks


def test_all_checks_pass_on_clean_fixture(built_db):
    con, raw_counts = built_db
    results = checks.run_all(con, raw_counts)
    assert len(results) == 13
    assert all(result["passed"] for result in results), results


@pytest.mark.parametrize(
    ("check_name", "corruption"),
    [
        (
            "row_counts",
            "DELETE FROM fact_measure WHERE release = '2026-07' AND source = 'general' AND facility_id = '100001'",
        ),
        ("key_unique", "INSERT INTO fact_measure SELECT * FROM fact_measure LIMIT 1"),
        (
            "orphans",
            "UPDATE fact_measure SET facility_id = '999999' WHERE release = '2026-07' "
            "AND source = 'general' AND facility_id = '100001'",
        ),
        (
            "status_coverage",
            "UPDATE fact_measure SET status = 'invalid' WHERE release = '2026-07' "
            "AND source = 'general' AND facility_id = '100001'",
        ),
        (
            "star_range",
            "UPDATE dim_hospital SET overall_star_rating = 6 WHERE release = '2026-07' AND facility_id = '100001'",
        ),
        (
            "single_period",
            "UPDATE fact_measure SET period_end = DATE '2026-11-30' WHERE release = '2026-07' "
            "AND source = 'hrrp' AND facility_id = '100001'",
        ),
        (
            "hrrp_suppression",
            "UPDATE mart_hrrp SET readmissions = NULL WHERE release = '2026-07' AND facility_id = '100001'",
        ),
        (
            "err_tieout",
            "UPDATE mart_hrrp SET excess_readmission_ratio = 2 WHERE release = '2026-07' "
            "AND facility_id = '100001'",
        ),
        (
            "sir_tieout",
            "UPDATE mart_hai SET sir = 2 WHERE release = '2026-07' AND facility_id = '100001' "
            "AND hai_id = 'HAI_1'",
        ),
        (
            "sir_in_ci",
            "UPDATE mart_hai SET ci_lower = 0.6 WHERE release = '2026-07' AND facility_id = '100001' "
            "AND hai_id = 'HAI_1'",
        ),
        (
            "sir_benchmark_label",
            "UPDATE mart_hai_compared SET compared_to_national = 'Worse Than National' "
            "WHERE release = '2026-07' AND facility_id = '100001' AND hai_id = 'HAI_1'",
        ),
        (
            "hcahps_sums",
            "UPDATE fact_measure SET value_num = 0 WHERE release = '2026-07' AND facility_id = '100001' "
            "AND measure_id = 'H_COMP_1_A_P'",
        ),
        (
            "scorecard_tieout",
            "UPDATE mart_scorecard SET overall_star_rating = 1 WHERE release = '2026-07' "
            "AND facility_id = '100001'",
        ),
    ],
)
def test_each_check_detects_targeted_corruption(mutable_db, check_name, corruption):
    con, raw_counts = mutable_db
    con.execute(corruption)
    check = getattr(checks, check_name)
    result = check(con, raw_counts) if check_name == "row_counts" else check(con)
    assert not result.passed, result
