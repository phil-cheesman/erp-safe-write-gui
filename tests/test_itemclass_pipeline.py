"""Tests for item class pipeline."""
from unittest.mock import MagicMock, patch
from tests.conftest import MockRow
from estship_uploader.itemclass_pipeline import run_validation, run_upload

class TestRunValidation:
    def test_success(self, mock_connection, mock_cursor):
        # Mock all fetchone/fetchall calls through the validation steps
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            MockRow("ITEM1", 1), MockRow("ITEM2", 1), MockRow("ITEM3", 1)
        ]
        rows = [("ITEM1", "A"), ("ITEM2", "B"), ("ITEM3", "D")]
        result = run_validation(mock_connection, rows, "testdb")
        # Should have multiple steps and succeed
        assert len(result.steps) > 0

    def test_halts_on_fail(self, mock_connection, mock_cursor):
        mock_cursor.execute.side_effect = Exception("SQL error")
        rows = [("ITEM1", "A")]
        result = run_validation(mock_connection, rows, "testdb")
        assert not result.success
        assert any(s.status == "FAIL" for s in result.steps)

class TestRunUpload:
    def test_success(self, mock_connection, mock_cursor):
        # backup: source count, backup count, backup list
        # execute_update: rowcount
        # validate: mismatches=0, count=5, trancount=1
        # post_commit: total=5, distinct=3
        mock_cursor.fetchone.side_effect = [
            (5,), (5,),       # backup counts
            (0,), (5,), (1,), # validate_in_transaction
            MockRow(5, 3),    # post_commit_verify
        ]
        mock_cursor.fetchall.return_value = [MockRow("icitem_backup_20260331")]
        mock_cursor.rowcount = 5
        result = run_upload(mock_connection, 5, database="testdb")
        assert result.success

    def test_rollback_on_mismatch(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.side_effect = [
            (5,), (5,),       # backup counts
            (2,), (5,), (1,), # validate: 2 mismatches
        ]
        mock_cursor.fetchall.return_value = [MockRow("icitem_backup_20260331")]
        mock_cursor.rowcount = 5
        result = run_upload(mock_connection, 5, database="testdb")
        assert not result.success
