from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ("value", "footnote", "expected"),
    [
        ("12.5", None, "reported"),
        ("12.5", "5, 24", "reported_footnoted"),
        ("Too Few to Report", "1", "suppressed"),
        ("Withheld", "1", "suppressed"),
        ("Not Available", None, "not_available"),
        ("N/A", None, "not_available"),
        ("--", None, "not_available"),
        (None, "1", "missing"),
        ("", None, "missing"),
        ("Descriptive text", None, "categorical"),
    ],
)
def test_cell_status_classification(built_db, value, footnote, expected):
    con, _ = built_db
    actual = con.execute(
        "SELECT cell_status(CAST(? AS VARCHAR), CAST(? AS VARCHAR))", [value, footnote]
    ).fetchone()[0]
    assert actual == expected


def test_fact_measure_has_one_row_per_raw_source_row(built_db):
    con, raw_counts = built_db
    expected = sum(sum(per_release.values()) for per_release in raw_counts.values())
    assert con.execute("SELECT count(*) FROM fact_measure").fetchone()[0] == expected


def test_measure_directions(built_db):
    con, _ = built_db
    directions = dict(con.execute("SELECT measure_id, direction FROM dim_measure").fetchall())
    assert directions["STAR_OVERALL"] == "higher_is_better"
    assert directions["READM-30-HF-HRRP"] == "lower_is_better"
    assert directions["HAI_1_SIR"] == "lower_is_better"
    assert directions["H_COMP_1_A_P"] == "higher_is_better"
    assert directions["OP_18b"] == "lower_is_better"
    assert directions["HAI_1_NUMERATOR"] == "context"


def test_hai_pivot_uses_sir_observed_and_predicted_rows(built_db):
    con, _ = built_db
    row = con.execute(
        """
        SELECT sir, observed, predicted
        FROM mart_hai
        WHERE release = '2026-07' AND facility_id = '100002' AND hai_id = 'HAI_1'
        """
    ).fetchone()
    assert row == (1.5, 9.0, 6.0)


def test_peer_pooling_rules(built_db):
    con, _ = built_db
    values = dict(
        con.execute(
            """
            SELECT kpi, value FROM mart_peer
            WHERE release = '2026-07' AND peer_group = 'National acute care'
            """
        ).fetchall()
    )
    assert values["SIR HAI_1"] == pytest.approx(14 / 12)
    assert values["SIR HAI_1"] != pytest.approx((0.5 + 1.5 + 1.0) / 3)
    assert values["Top box H_COMP_1_A_P"] == pytest.approx((80 * 100 + 60 * 300 + 90 * 100) / 500)
    assert values["ERR (median of hospital mean ERR)"] == pytest.approx(1.0)


def test_percentiles_preserve_null_kpis(built_db):
    con, _ = built_db
    row = con.execute(
        """
        SELECT err_pctile, ed_pctile, hcahps_rating_pctile
        FROM mart_percentile
        WHERE release = '2026-07' AND facility_id = '100003'
        """
    ).fetchone()
    assert row == (None, None, None)
