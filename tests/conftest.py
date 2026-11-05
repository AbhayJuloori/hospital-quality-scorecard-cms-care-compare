from __future__ import annotations

import csv
from pathlib import Path

import pytest

from hqs import build

GENERAL_FIELDS = [
    "Facility ID",
    "Facility Name",
    "City/Town",
    "State",
    "County/Parish",
    "Hospital Type",
    "Hospital Ownership",
    "Emergency Services",
    "Hospital overall rating",
    "Hospital overall rating footnote",
]
HRRP_FIELDS = [
    "Facility ID",
    "Measure Name",
    "Number of Discharges",
    "Excess Readmission Ratio",
    "Predicted Readmission Rate",
    "Expected Readmission Rate",
    "Number of Readmissions",
    "Footnote",
    "Start Date",
    "End Date",
]
HCAHPS_FIELDS = [
    "Facility ID",
    "HCAHPS Measure ID",
    "HCAHPS Answer Description",
    "Patient Survey Star Rating",
    "HCAHPS Linear Mean Value",
    "HCAHPS Answer Percent",
    "Patient Survey Star Rating Footnote",
    "Number of Completed Surveys Footnote",
    "HCAHPS Answer Percent Footnote",
    "Start Date",
    "End Date",
    "Number of Completed Surveys",
]
HAI_FIELDS = [
    "Facility ID",
    "Measure ID",
    "Measure Name",
    "Score",
    "Footnote",
    "Start Date",
    "End Date",
    "Compared to National",
]
TEC_FIELDS = [
    "Facility ID",
    "Measure ID",
    "Measure Name",
    "Score",
    "Footnote",
    "Start Date",
    "End Date",
    "Sample",
]


HOSPITALS = [
    {
        "Facility ID": "100001",
        "Facility Name": "Alpha Hospital",
        "City/Town": "Indianapolis",
        "State": "IN",
        "County/Parish": "Marion",
        "Hospital overall rating": "5",
        "Hospital overall rating footnote": "",
    },
    {
        "Facility ID": "100002",
        "Facility Name": "Bravo Hospital",
        "City/Town": "Newark",
        "State": "NJ",
        "County/Parish": "Essex",
        "Hospital overall rating": "3",
        "Hospital overall rating footnote": "5, 24",
    },
    {
        "Facility ID": "100003",
        "Facility Name": "Charlie Hospital",
        "City/Town": "Columbus",
        "State": "OH",
        "County/Parish": "Franklin",
        "Hospital overall rating": "Not Available",
        "Hospital overall rating footnote": "",
    },
    {
        "Facility ID": "100004",
        "Facility Name": "Delta Hospital",
        "City/Town": "Fort Wayne",
        "State": "IN",
        "County/Parish": "Allen",
        "Hospital overall rating": "4",
        "Hospital overall rating footnote": "",
    },
]


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _general_rows() -> list[dict[str, str]]:
    return [
        {
            **hospital,
            "Hospital Type": "Acute Care Hospitals",
            "Hospital Ownership": "Voluntary non-profit - Private",
            "Emergency Services": "Yes",
        }
        for hospital in HOSPITALS
    ]


def _hrrp_rows(start: str, end: str) -> list[dict[str, str]]:
    values = [
        ("100001", "100", "0.8", "8", "10", "8", ""),
        ("100002", "200", "1.2", "12", "10", "24", ""),
        ("100003", "N/A", "Not Available", "N/A", "N/A", "N/A", ""),
        ("100004", "Too Few to Report", "1.0", "10", "10", "Too Few to Report", "1"),
    ]
    return [
        {
            "Facility ID": facility_id,
            "Measure Name": "READM-30-HF-HRRP",
            "Number of Discharges": discharges,
            "Excess Readmission Ratio": err,
            "Predicted Readmission Rate": predicted,
            "Expected Readmission Rate": expected,
            "Number of Readmissions": readmissions,
            "Footnote": footnote,
            "Start Date": start,
            "End Date": end,
        }
        for facility_id, discharges, err, predicted, expected, readmissions, footnote in values
    ]


def _hcahps_rows(start: str, end: str) -> list[dict[str, str]]:
    values = {
        "100001": ("100", ("80", "15", "5"), "70"),
        "100002": ("300", ("60", "30", "10"), "50"),
        "100003": ("200", ("Not Available", "70", "30"), "Not Available"),
        "100004": ("100", ("90", "8", "2"), "80"),
    }
    rows = []
    for facility_id, (surveys, answers, rating) in values.items():
        for measure_id, description, score in zip(
            ("H_COMP_1_A_P", "H_COMP_1_U_P", "H_COMP_1_SN_P"),
            ("Always", "Usually", "Sometimes or never"),
            answers,
        ):
            rows.append(
                {
                    "Facility ID": facility_id,
                    "HCAHPS Measure ID": measure_id,
                    "HCAHPS Answer Description": description,
                    "HCAHPS Answer Percent": score,
                    "HCAHPS Answer Percent Footnote": "5, 24"
                    if facility_id == "100002" and measure_id == "H_COMP_1_A_P"
                    else "",
                    "Start Date": start,
                    "End Date": end,
                    "Number of Completed Surveys": surveys,
                }
            )
        rows.append(
            {
                "Facility ID": facility_id,
                "HCAHPS Measure ID": "H_HSP_RATING_9_10",
                "HCAHPS Answer Description": "Overall rating of 9 or 10",
                "HCAHPS Answer Percent": rating,
                "HCAHPS Answer Percent Footnote": "",
                "Start Date": start,
                "End Date": end,
                "Number of Completed Surveys": surveys,
            }
        )
    return rows


def _hai_rows(start: str, end: str) -> list[dict[str, str]]:
    values = {
        "100001": (("0.5", "1", "2", "0.4", "0.8"), "Better Than National", ""),
        "100002": (("1.5", "9", "6", "1.2", "1.8"), "Worse Than National", ""),
        "100003": (
            ("Too Few to Report", "N/A", "N/A", "--", "Not Available"),
            "",
            "1",
        ),
        "100004": (("1.0", "4", "4", "0.8", "1.2"), "No Different Than National", ""),
    }
    suffixes = ("SIR", "NUMERATOR", "ELIGCASES", "CILOWER", "CIUPPER")
    rows = []
    for facility_id, (scores, comparison, sir_footnote) in values.items():
        for suffix, score in zip(suffixes, scores):
            rows.append(
                {
                    "Facility ID": facility_id,
                    "Measure ID": f"HAI_1_{suffix}",
                    "Measure Name": f"CLABSI {suffix}",
                    "Score": score,
                    "Footnote": sir_footnote if suffix == "SIR" else "",
                    "Start Date": start,
                    "End Date": end,
                    "Compared to National": comparison if suffix == "SIR" else "",
                }
            )
    return rows


def _tec_rows(start: str, end: str) -> list[dict[str, str]]:
    values = {
        "100001": ("100", "2"),
        "100002": ("200", "5"),
        "100003": ("--", "N/A"),
        "100004": ("150", "3"),
    }
    rows = []
    for facility_id, (op18b, op22) in values.items():
        for measure_id, name, score in (
            ("OP_18b", "Median time in emergency department", op18b),
            ("OP_22", "Left before being seen", op22),
        ):
            rows.append(
                {
                    "Facility ID": facility_id,
                    "Measure ID": measure_id,
                    "Measure Name": name,
                    "Score": score,
                    "Footnote": "5" if facility_id == "100002" and measure_id == "OP_22" else "",
                    "Start Date": start,
                    "End Date": end,
                    "Sample": "100",
                }
            )
    return rows


@pytest.fixture(scope="session")
def synthetic_raw(tmp_path_factory: pytest.TempPathFactory) -> Path:
    raw = tmp_path_factory.mktemp("raw")
    for release in ("2024-07", "2025-07", "2026-07"):
        release_dir = raw / release
        release_dir.mkdir()
        year = release[:4]
        start = f"01/01/{year}"
        end = f"12/31/{year}"
        _write_csv(release_dir / "Hospital_General_Information.csv", GENERAL_FIELDS, _general_rows())
        _write_csv(
            release_dir / f"FY_{year}_Hospital_Readmissions_Reduction_Program_Hospital.csv",
            HRRP_FIELDS,
            _hrrp_rows(start, end),
        )
        _write_csv(release_dir / "HCAHPS-Hospital.csv", HCAHPS_FIELDS, _hcahps_rows(start, end))
        _write_csv(
            release_dir / "Healthcare_Associated_Infections-Hospital.csv",
            HAI_FIELDS,
            _hai_rows(start, end),
        )
        _write_csv(
            release_dir / "Timely_and_Effective_Care-Hospital.csv",
            TEC_FIELDS,
            _tec_rows(start, end),
        )
    _write_csv(
        raw / "Footnote_Crosswalk.csv",
        ["Footnote", "Footnote Text"],
        [
            {"Footnote": "1", "Footnote Text": "Too few cases to report"},
            {"Footnote": "5", "Footnote Text": "Results are based on a shorter period"},
            {"Footnote": "24", "Footnote Text": "Data suppressed by request"},
        ],
    )
    return raw


@pytest.fixture(scope="session")
def built_db(tmp_path_factory: pytest.TempPathFactory, synthetic_raw: Path):
    db_path = tmp_path_factory.mktemp("db") / "t.duckdb"
    con, raw_counts = build.build(db_path=db_path, raw=synthetic_raw)
    yield con, raw_counts
    con.close()


@pytest.fixture
def mutable_db(built_db):
    con, raw_counts = built_db
    con.execute("BEGIN TRANSACTION")
    try:
        yield con, raw_counts
    finally:
        con.execute("ROLLBACK")
