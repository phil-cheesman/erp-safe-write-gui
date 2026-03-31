"""Tests for mfg lead time validators."""
from tests.conftest import MockRow
from estship_uploader.mfglt_validators import (
    create_staging_table, import_to_staging, verify_import,
    check_items_exist, check_value_changes, check_anomalies, get_summary,
)

class TestCreateStagingTable:
    def test_pass(self, mock_connection, mock_cursor):
        result = create_staging_table(mock_connection, "testdb")
        assert result.status == "PASS"

    def test_fail(self, mock_connection, mock_cursor):
        mock_cursor.execute.side_effect = Exception("error")
        result = create_staging_table(mock_connection, "testdb")
        assert result.status == "FAIL"

class TestImportToStaging:
    def test_pass(self, mock_connection, mock_cursor):
        rows = [("ITEM1", 14), ("ITEM2", 30)]
        result = import_to_staging(mock_connection, rows)
        assert result.status == "PASS"

class TestVerifyImport:
    def test_pass(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.return_value = (3,)
        result = verify_import(mock_connection, 3)
        assert result.status == "PASS"

    def test_fail(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.return_value = (2,)
        result = verify_import(mock_connection, 3)
        assert result.status == "FAIL"

class TestCheckItemsExist:
    def test_all_found(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.return_value = [
            MockRow("ITEM1               ", 1),
            MockRow("ITEM2               ", 1),
        ]
        result = check_items_exist(mock_connection)
        assert result.status == "PASS"
        assert "MAIN" in result.message

    def test_missing_warning(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.return_value = [
            MockRow("ITEM1               ", 1),
            MockRow("MISSING             ", 0),
        ]
        mock_cursor.rowcount = 1
        result = check_items_exist(mock_connection)
        assert result.status == "WARNING"

class TestCheckValueChanges:
    def test_changes_shown(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.return_value = [
            MockRow("ITEM1               ", 14, 30),
            MockRow("ITEM2               ", 7, 7),
        ]
        result = check_value_changes(mock_connection)
        assert result.status == "PASS"
        assert "1 of 2" in result.message

class TestCheckAnomalies:
    def test_zero_warning(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.side_effect = [(2,), (0,), (0,)]
        result = check_anomalies(mock_connection)
        assert result.status == "WARNING"
        assert "0 days" in result.message

    def test_no_anomalies(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.side_effect = [(0,), (0,), (0,)]
        result = check_anomalies(mock_connection)
        assert result.status == "PASS"

class TestGetSummary:
    def test_pass(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.return_value = (10,)
        result = get_summary(mock_connection)
        assert result.status == "PASS"
