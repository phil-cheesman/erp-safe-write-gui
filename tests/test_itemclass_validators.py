"""Tests for item class validators."""
from tests.conftest import MockRow
from estship_uploader.itemclass_validators import (
    create_staging_table, import_to_staging, verify_import,
    check_items_exist, validate_cbuyer_values, check_value_changes,
    check_anomalies, get_summary,
)

class TestCreateStagingTable:
    def test_pass(self, mock_connection, mock_cursor):
        result = create_staging_table(mock_connection, "testdb")
        assert result.status == "PASS"

    def test_fail_on_error(self, mock_connection, mock_cursor):
        mock_cursor.execute.side_effect = Exception("SQL error")
        result = create_staging_table(mock_connection, "testdb")
        assert result.status == "FAIL"

class TestImportToStaging:
    def test_pass(self, mock_connection, mock_cursor):
        rows = [("ITEM1", "A"), ("ITEM2", "B")]
        result = import_to_staging(mock_connection, rows)
        assert result.status == "PASS"
        assert "2 rows" in result.message

class TestVerifyImport:
    def test_pass(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.return_value = (5,)
        result = verify_import(mock_connection, 5)
        assert result.status == "PASS"

    def test_fail_mismatch(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.return_value = (3,)
        result = verify_import(mock_connection, 5)
        assert result.status == "FAIL"

class TestCheckItemsExist:
    def test_all_found(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.return_value = [
            MockRow("ITEM1               ", 1),
            MockRow("ITEM2               ", 1),
        ]
        result = check_items_exist(mock_connection)
        assert result.status == "PASS"

    def test_missing_items_warning(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.return_value = [
            MockRow("ITEM1               ", 1),
            MockRow("ITEM-GONE           ", 0),
        ]
        mock_cursor.rowcount = 1
        result = check_items_exist(mock_connection)
        assert result.status == "WARNING"
        assert "1 of 2" in result.message

class TestValidateCbuyerValues:
    def test_all_approved(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.return_value = [MockRow("A"), MockRow("MTO")]
        result = validate_cbuyer_values(mock_connection)
        assert result.status == "PASS"

    def test_non_approved_warning(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.return_value = [MockRow("A"), MockRow("STOCK")]
        result = validate_cbuyer_values(mock_connection)
        assert result.status == "WARNING"

class TestCheckValueChanges:
    def test_changes_shown(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.return_value = [
            MockRow("ITEM1               ", "A", "B"),
            MockRow("ITEM2               ", "D", "D"),
        ]
        result = check_value_changes(mock_connection)
        assert result.status == "PASS"
        assert "1 of 2" in result.message

class TestCheckAnomalies:
    def test_blanks_warning(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.return_value = (5,)  # blank_count
        mock_cursor.fetchall.return_value = [MockRow("(blank)", 5)]
        result = check_anomalies(mock_connection)
        assert result.status == "WARNING"

    def test_no_anomalies(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.return_value = (0,)  # blank_count
        mock_cursor.fetchall.return_value = [MockRow("A", 3)]
        result = check_anomalies(mock_connection)
        assert result.status == "PASS"

class TestGetSummary:
    def test_pass(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.return_value = (10,)
        result = get_summary(mock_connection)
        assert result.status == "PASS"
        assert "10" in result.message
