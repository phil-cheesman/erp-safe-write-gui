"""Tests for mfg lead time pipeline."""
from tests.conftest import MockRow
from estship_uploader.mfglt_pipeline import run_validation, run_upload

class TestRunValidation:
    def test_success(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            MockRow("ITEM1", 1), MockRow("ITEM2", 1), MockRow("ITEM3", 1)
        ]
        rows = [("ITEM1", 14), ("ITEM2", 30), ("ITEM3", 7)]
        result = run_validation(mock_connection, rows, "testdb")
        assert len(result.steps) > 0

    def test_halts_on_fail(self, mock_connection, mock_cursor):
        mock_cursor.execute.side_effect = Exception("SQL error")
        rows = [("ITEM1", 14)]
        result = run_validation(mock_connection, rows, "testdb")
        assert not result.success

class TestRunUpload:
    def test_success(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.side_effect = [
            (5,), (5,),       # backup counts
            (0,), (5,), (1,), # validate_in_transaction
            MockRow(5, 7, 45),# post_commit_verify
        ]
        mock_cursor.fetchall.return_value = [MockRow("iciwhs_backup_20260331")]
        mock_cursor.rowcount = 5
        result = run_upload(mock_connection, 5, database="testdb")
        assert result.success

    def test_rollback_on_mismatch(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.side_effect = [
            (5,), (5,),       # backup
            (1,), (5,), (1,), # validate: 1 mismatch
        ]
        mock_cursor.fetchall.return_value = [MockRow("iciwhs_backup_20260331")]
        mock_cursor.rowcount = 5
        result = run_upload(mock_connection, 5, database="testdb")
        assert not result.success
