"""Tests for csv_parser module."""

from estship_uploader.csv_parser import parse_csv


def test_valid_csv(sample_csv_path):
    """Valid CSV → 3 rows, 0 skipped, dates normalized to YYYY-MM-DD."""
    rows, skipped, errors, _ = parse_csv(sample_csv_path)
    assert errors == []
    assert skipped == 0
    assert len(rows) == 3
    # Dates normalized from M/D/YYYY to YYYY-MM-DD
    assert rows[0][3] == "2026-03-06"
    assert rows[1][3] == "2026-04-20"
    assert rows[2][3] == "2026-03-11"
    # SO_Number preserves leading spaces
    assert rows[0][0] == "   2873157"
    # Item_Number is stripped
    assert rows[0][2] == "01-0014"


def test_blank_rows(sample_csv_blank_rows):
    """Blank rows → 2 valid rows, 2 skipped."""
    rows, skipped, errors, _ = parse_csv(sample_csv_blank_rows)
    assert errors == []
    assert len(rows) == 2
    assert skipped == 2


def test_bad_dates(sample_csv_bad_dates):
    """Bad dates → errors returned, 0 rows."""
    rows, skipped, errors, _ = parse_csv(sample_csv_bad_dates)
    assert len(errors) > 0
    assert len(rows) == 0
    assert "not-a-date" in errors[0]


def test_wrong_headers(sample_csv_missing_cols):
    """Wrong headers → errors returned."""
    rows, skipped, errors, _ = parse_csv(sample_csv_missing_cols)
    assert len(errors) > 0
    assert len(rows) == 0
    assert "Invalid headers" in errors[0]


def test_iso_dates(sample_csv_iso_dates):
    """YYYY-MM-DD format → accepted as-is."""
    rows, skipped, errors, _ = parse_csv(sample_csv_iso_dates)
    assert errors == []
    assert len(rows) == 2
    assert rows[0][3] == "2026-03-06"
    assert rows[1][3] == "2026-04-20"


def test_missing_required_fields(sample_csv_missing_fields):
    """Missing required fields → error."""
    rows, skipped, errors, _ = parse_csv(sample_csv_missing_fields)
    assert len(errors) > 0
    assert len(rows) == 0
    assert "missing Line_Item" in errors[0]


def test_header_only(sample_csv_header_only):
    """Empty file (header only) → 0 rows, 0 errors."""
    rows, skipped, errors, _ = parse_csv(sample_csv_header_only)
    assert errors == []
    assert len(rows) == 0
    assert skipped == 0


def test_excel_serial_date(sample_csv_excel_serial):
    """Excel serial date numbers → converted to YYYY-MM-DD."""
    rows, skipped, errors, warnings = parse_csv(sample_csv_excel_serial)
    assert errors == []
    assert len(rows) == 2
    # 46112 = 2026-03-31, 46157 = 2026-05-15 in Excel serial
    assert rows[0][3] == "2026-03-31"
    assert rows[1][3] == "2026-05-15"


def test_null_date(sample_csv_null_date):
    """NULL keyword → date set to None, warning emitted."""
    rows, skipped, errors, warnings = parse_csv(sample_csv_null_date)
    assert errors == []
    assert len(rows) == 2
    assert rows[0][3] is None
    assert rows[1][3] == "2026-04-20"
    assert len(warnings) == 1
    assert "cleared" in warnings[0]


def test_duplicate_same_date(sample_csv_duplicate_same_date):
    """Duplicate SO/Line with same date → warning, rows still returned."""
    rows, skipped, errors, warnings = parse_csv(sample_csv_duplicate_same_date)
    assert errors == []
    assert len(rows) == 3
    assert len(warnings) == 1
    assert "Duplicate" in warnings[0]
    assert "same date" in warnings[0]


def test_duplicate_different_dates(sample_csv_duplicate_diff_dates):
    """Duplicate SO/Line with different dates → error, no rows."""
    rows, skipped, errors, warnings = parse_csv(sample_csv_duplicate_diff_dates)
    assert len(errors) == 1
    assert len(rows) == 0
    assert "conflicting dates" in errors[0]
