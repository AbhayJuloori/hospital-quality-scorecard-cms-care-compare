from __future__ import annotations

from openpyxl import load_workbook

from hqs import checks, excel, run


def test_write_workbook_has_expected_sheets(built_db, tmp_path):
    con, raw_counts = built_db
    check_rows = checks.run_all(con, raw_counts)
    report = run.make_report(con, raw_counts, check_rows)
    output = tmp_path / "scorecard.xlsx"

    assert excel.write_workbook(con, report, output) == output
    workbook = load_workbook(output, read_only=True)
    try:
        assert workbook.sheetnames == [
            "Read me",
            "Data dictionary",
            "Requirements",
            "Test cases",
            "Quality flags",
            "Measure changes",
            "IN scorecard",
            "NJ scorecard",
            "Trend",
        ]
    finally:
        workbook.close()
