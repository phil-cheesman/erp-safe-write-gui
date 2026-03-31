"""Tests for item class updater."""
from unittest.mock import MagicMock
from tests.conftest import MockRow
from estship_uploader.itemclass_updater import (
    execute_update, validate_in_transaction, commit_or_rollback,
    post_commit_verify, cleanup_staging, backup_table,
)

class TestBackupTable:
    def test_calls_create_backup(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.side_effect = [(100,), (100,)]
        mock_cursor.fetchall.return_value = [MockRow("icitem_backup_20260331")]
        result = backup_table(mock_connection)
        assert result.status == "PASS"

class TestExecuteUpdate:
    def test_pass(self, mock_connection, mock_cursor):
        mock_cursor.rowcount = 5
        result = execute_update(mock_connection)
        assert result.status == "PASS"
        assert "5 rows" in result.message
        assert mock_connection.autocommit == False

    def test_fail_rolls_back(self, mock_connection, mock_cursor):
        mock_cursor.execute.side_effect = [None, Exception("SQL error")]
        result = execute_update(mock_connection)
        assert result.status == "FAIL"

class TestValidateInTransaction:
    def test_pass(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.side_effect = [(0,), (5,), (1,)]
        result = validate_in_transaction(mock_connection, 5)
        assert result.status == "PASS"

    def test_fail_mismatches(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.side_effect = [(2,), (5,), (1,)]
        result = validate_in_transaction(mock_connection, 5)
        assert result.status == "FAIL"
        assert "mismatch" in result.message.lower()

    def test_fail_count_mismatch(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.side_effect = [(0,), (3,), (1,)]
        result = validate_in_transaction(mock_connection, 5)
        assert result.status == "FAIL"
        assert "count" in result.message.lower()

class TestCommitOrRollback:
    def test_commit(self, mock_connection, mock_cursor):
        result = commit_or_rollback(mock_connection, True)
        assert result.status == "PASS"
        assert "committed" in result.message.lower()

    def test_rollback(self, mock_connection, mock_cursor):
        result = commit_or_rollback(mock_connection, False)
        assert result.status == "FAIL"
        assert "rolled back" in result.message.lower()

class TestPostCommitVerify:
    def test_pass(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.return_value = MockRow(10, 3)
        result = post_commit_verify(mock_connection)
        assert result.status == "PASS"
        assert "10" in result.message

class TestCleanupStaging:
    def test_pass(self, mock_connection, mock_cursor):
        result = cleanup_staging(mock_connection)
        assert result.status == "PASS"

    def test_error_still_passes(self, mock_connection, mock_cursor):
        mock_cursor.execute.side_effect = Exception("already dropped")
        result = cleanup_staging(mock_connection)
        assert result.status == "PASS"
