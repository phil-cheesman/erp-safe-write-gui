"""Tests for validators module — each step tested for pass + fail."""

from unittest.mock import MagicMock

from estship_uploader.validators import (
    create_staging_table,
    import_to_staging,
    verify_import,
    check_so_line_exists,
    check_item_numbers,
    check_date_anomalies,
    get_summary,
)


# -- Step 1: create_staging_table --

def test_create_staging_pass(mock_connection, mock_cursor):
    result = create_staging_table(mock_connection, "testdb")
    assert result.status == "PASS"
    assert "created" in result.message.lower()


def test_create_staging_fail(mock_connection, mock_cursor):
    mock_cursor.execute.side_effect = Exception("permission denied")
    result = create_staging_table(mock_connection, "testdb")
    assert result.status == "FAIL"


# -- Step 2: import_to_staging --

def test_import_pass(mock_connection, mock_cursor):
    rows = [("SO1", "L1", "ITEM1", "2026-04-15")]
    result = import_to_staging(mock_connection, rows)
    assert result.status == "PASS"
    assert "1 rows" in result.message


def test_import_fail(mock_connection, mock_cursor):
    mock_cursor.executemany.side_effect = Exception("insert error")
    result = import_to_staging(mock_connection, [("SO1", "L1", "ITEM1", "2026-04-15")])
    assert result.status == "FAIL"


# -- Step 3: verify_import --

def test_verify_import_pass(mock_connection, mock_cursor):
    mock_cursor.fetchone.return_value = (5,)
    result = verify_import(mock_connection, 5)
    assert result.status == "PASS"
    assert "5" in result.message


def test_verify_import_fail(mock_connection, mock_cursor):
    mock_cursor.fetchone.return_value = (3,)
    result = verify_import(mock_connection, 5)
    assert result.status == "FAIL"
    assert "mismatch" in result.message.lower()


# -- Step 4: check_so_line_exists --

def test_so_line_all_found(mock_connection, mock_cursor):
    # All rows found (last column = 1)
    mock_cursor.fetchall.return_value = [
        ("SO1", "L1", "ITEM1", "2026-04-15", 1),
        ("SO2", "L2", "ITEM2", "2026-04-16", 1),
    ]
    result = check_so_line_exists(mock_connection)
    assert result.status == "PASS"


def test_so_line_some_missing(mock_connection, mock_cursor):
    mock_cursor.fetchall.return_value = [
        ("  SO1     ", "  L1      ", "ITEM1", "2026-04-15", 1),
        ("  SO2     ", "  L2      ", "ITEM2", "2026-04-16", 0),  # not found
    ]
    result = check_so_line_exists(mock_connection)
    assert result.status == "FAIL"
    assert "1 of 2" in result.message


# -- Step 5: check_item_numbers --

def test_items_all_match(mock_connection, mock_cursor):
    mock_cursor.fetchall.return_value = [
        ("SO1", "L1", "ITEM1", "ITEM1", 1),
        ("SO2", "L2", "ITEM2", "ITEM2", 1),
    ]
    result = check_item_numbers(mock_connection)
    assert result.status == "PASS"


def test_items_mismatch(mock_connection, mock_cursor):
    mock_cursor.fetchall.return_value = [
        ("  SO1     ", "  L1      ", "ITEM1", "ITEM-WRONG", 0),
    ]
    result = check_item_numbers(mock_connection)
    assert result.status == "FAIL"
    assert "mismatch" in result.message.lower()
    assert len(result.details) == 1


# -- Step 6: check_date_anomalies --

def test_no_anomalies(mock_connection, mock_cursor):
    mock_cursor.fetchall.return_value = []
    result = check_date_anomalies(mock_connection)
    assert result.status == "PASS"


def test_date_anomalies_returns_warning(mock_connection, mock_cursor):
    """Date anomalies should return WARNING, not FAIL."""
    mock_cursor.fetchall.return_value = [
        ("  SO1     ", "  L1      ", "2026-01-01", -60),
    ]
    result = check_date_anomalies(mock_connection)
    assert result.status == "WARNING"
    assert len(result.details) == 1


# -- Step 7: get_summary --

def test_summary_pass(mock_connection, mock_cursor):
    mock_cursor.fetchone.return_value = (47,)
    result = get_summary(mock_connection)
    assert result.status == "PASS"
    assert "47" in result.message
