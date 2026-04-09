"""Tests for mfg lead time pipeline."""
from tests.conftest import MockRow
from estship_uploader.mfglt_pipeline import run_validation, run_upload

class TestRunValidation:
    def test_success(self, mock_connection, mock_cursor):
        # All fetchone calls return (3,). That serves verify_import,
        # check_anomalies (3 counts), get_summary, the final staging count
        # query, AND compute_update_scope's expected_rows query.
        mock_cursor.fetchone.return_value = (3,)
        # fetchall is called in this order by run_validation:
        #   1. check_items_exist           -> [(item, found), ...]
        #   2. check_value_changes         -> [(item, current, new, wh_count), ...]
        #   3. compute_update_scope second -> [(warehouse,), ...]
        mock_cursor.fetchall.side_effect = [
            [MockRow("ITEM1", 1), MockRow("ITEM2", 1), MockRow("ITEM3", 1)],
            [
                MockRow("ITEM1", 14, 14, 2),
                MockRow("ITEM2", 30, 30, 2),
                MockRow("ITEM3", 7, 7, 2),
            ],
            [MockRow("HUDSON"), MockRow("MAIN")],
        ]
        rows = [("ITEM1", 14), ("ITEM2", 30), ("ITEM3", 7)]
        result = run_validation(mock_connection, rows, "testdb")
        assert result.success
        assert result.upload_count == 3
        # expected_rows comes from compute_update_scope (3 from fetchone).
        assert result.expected_rows == 3
        # The scope summary message must mention the warehouse fan-out so the
        # user can see what's about to happen.
        scope_messages = [
            s.message for s in result.steps if "rows across" in s.message
        ]
        assert scope_messages, "Expected a 'rows across N warehouses' summary step"
        assert "HUDSON" in scope_messages[0]
        assert "MAIN" in scope_messages[0]

    def test_halts_on_fail(self, mock_connection, mock_cursor):
        mock_cursor.execute.side_effect = Exception("SQL error")
        rows = [("ITEM1", 14)]
        result = run_validation(mock_connection, rows, "testdb")
        assert not result.success

class TestRunUpload:
    def test_success(self, mock_connection, mock_cursor):
        # fetchone order:
        #   (5,), (5,)        backup source/target counts
        #   (0,)              validate_in_transaction: mismatches
        #   (5,)              validate_in_transaction: scope_count
        #   (1,)              validate_in_transaction: @@TRANCOUNT
        #   MockRow(5, 7, 45) post_commit_verify
        mock_cursor.fetchone.side_effect = [
            (5,), (5,),
            (0,), (5,), (1,),
            MockRow(5, 7, 45),
        ]
        mock_cursor.fetchall.return_value = [MockRow("iciwhs_backup_20260331")]
        mock_cursor.rowcount = 5  # actual_rows from execute_update
        result = run_upload(mock_connection, 5, database="testdb")
        assert result.success

    def test_rollback_on_mismatch(self, mock_connection, mock_cursor):
        # 1 mismatch -> validate_in_transaction FAIL -> rollback.
        mock_cursor.fetchone.side_effect = [
            (5,), (5,),
            (1,), (5,), (1,),
        ]
        mock_cursor.fetchall.return_value = [MockRow("iciwhs_backup_20260331")]
        mock_cursor.rowcount = 5
        result = run_upload(mock_connection, 5, database="testdb")
        assert not result.success

    def test_rollback_when_actual_rows_differs_from_expected(
        self, mock_connection, mock_cursor
    ):
        # No mismatches, but the UPDATE touched a different number of rows
        # than the validation phase predicted -> rollback.
        mock_cursor.fetchone.side_effect = [
            (5,), (5,),       # backup
            (0,),             # mismatches
            (5,),             # scope_count
            (1,),             # @@TRANCOUNT
        ]
        mock_cursor.fetchall.return_value = [MockRow("iciwhs_backup_20260331")]
        mock_cursor.rowcount = 7  # UPDATE touched 7, but expected is 5
        result = run_upload(mock_connection, 5, database="testdb")
        assert not result.success
        # The failing step must explain the row count drift.
        failing = [s for s in result.steps if s.status == "FAIL"]
        assert any("row count mismatch" in s.message for s in failing)
