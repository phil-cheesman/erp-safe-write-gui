"""Tests for mfg lead time validators."""
from tests.conftest import MockRow
from estship_uploader.mfglt_validators import (
    create_staging_table, import_to_staging, verify_import,
    check_items_exist, check_value_changes, check_anomalies, get_summary,
    compute_update_scope,
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
        assert "iciwhs" in result.message

    def test_missing_warning(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.return_value = [
            MockRow("ITEM1               ", 1),
            MockRow("MISSING             ", 0),
        ]
        mock_cursor.rowcount = 1
        result = check_items_exist(mock_connection)
        assert result.status == "WARNING"

    def test_item_in_non_main_warehouse_passes(self, mock_connection, mock_cursor):
        # An item that exists only in HUDSON (not MAIN) is found, because the
        # EXISTS check has no warehouse filter.
        mock_cursor.fetchall.return_value = [
            MockRow("HUDSON_ONLY         ", 1),
            MockRow("MAIN_ONLY           ", 1),
        ]
        result = check_items_exist(mock_connection)
        assert result.status == "PASS"
        # The SQL must NOT pin to any specific warehouse.
        executed_sql = " ".join(
            str(call[0][0]) for call in mock_cursor.execute.call_args_list
        )
        assert "cwarehouse = 'MAIN'" not in executed_sql
        assert "NOT IN" not in executed_sql

class TestCheckValueChanges:
    def test_changes_shown(self, mock_connection, mock_cursor):
        # Each row is now (item, current_value, new_value, wh_count) — grouped
        # by (item, current_value) so warehouse drift surfaces naturally.
        mock_cursor.fetchall.return_value = [
            MockRow("ITEM1               ", 14, 30, 3),  # 3 wh, all change
            MockRow("ITEM2               ", 7, 7, 2),    # 2 wh, no change
        ]
        result = check_value_changes(mock_connection)
        assert result.status == "PASS"
        assert "1 of 2" in result.message
        joined_details = " ".join(result.details)
        assert "3 wh" in joined_details
        assert "2 wh" in joined_details

    def test_warehouse_drift_shown_as_separate_groups(
        self, mock_connection, mock_cursor
    ):
        # Same item with different current values across warehouses produces
        # one row per (item, current_value) group.
        mock_cursor.fetchall.return_value = [
            MockRow("DRIFT               ", 14, 30, 1),  # MAIN at 14
            MockRow("DRIFT               ", 21, 30, 2),  # 2 other wh at 21
        ]
        result = check_value_changes(mock_connection)
        assert result.status == "PASS"
        # Both groups change (14 -> 30 and 21 -> 30).
        assert "2 of 2" in result.message


class TestComputeUpdateScope:
    def test_pass_with_warehouses(self, mock_connection, mock_cursor):
        # First fetchone -> expected_rows count, then fetchall -> warehouses.
        mock_cursor.fetchone.return_value = (137,)
        mock_cursor.fetchall.return_value = [
            MockRow("2377      "),
            MockRow("CA        "),
            MockRow("HUDSON    "),
            MockRow("MAIN      "),
        ]
        step, expected_rows, warehouses = compute_update_scope(mock_connection)
        assert step.status == "PASS"
        assert expected_rows == 137
        assert warehouses == ["2377", "CA", "HUDSON", "MAIN"]
        assert "137 rows across 4 warehouses" in step.message

    def test_no_warehouse_filter_in_sql(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.return_value = (10,)
        mock_cursor.fetchall.return_value = [MockRow("MAIN      ")]
        compute_update_scope(mock_connection)
        executed_sql = " ".join(
            str(call[0][0]) for call in mock_cursor.execute.call_args_list
        )
        assert "cwarehouse = 'MAIN'" not in executed_sql
        assert "NOT IN" not in executed_sql

    def test_empty_returns_zero(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.return_value = (0,)
        mock_cursor.fetchall.return_value = []
        step, expected_rows, warehouses = compute_update_scope(mock_connection)
        assert step.status == "PASS"
        assert expected_rows == 0
        assert warehouses == []

    def test_fail_on_sql_error(self, mock_connection, mock_cursor):
        mock_cursor.execute.side_effect = Exception("boom")
        step, expected_rows, warehouses = compute_update_scope(mock_connection)
        assert step.status == "FAIL"
        assert expected_rows == 0
        assert warehouses == []

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
