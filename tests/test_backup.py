"""Tests for backup utility."""
from unittest.mock import MagicMock, call
import pytest
from tests.conftest import MockRow
from estship_uploader.backup import create_backup

class TestCreateBackup:
    def test_backup_success(self, mock_connection, mock_cursor):
        # fetchone returns source count then backup count (matching)
        mock_cursor.fetchone.side_effect = [(100,), (100,)]
        # fetchall returns list of backup tables (only today's)
        mock_cursor.fetchall.return_value = [MockRow("icitem_backup_20260331")]
        result = create_backup(mock_connection, "icitem")
        assert result.status == "PASS"
        assert "100 rows" in result.message

    def test_backup_count_mismatch(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.side_effect = [(100,), (99,)]
        result = create_backup(mock_connection, "icitem")
        assert result.status == "FAIL"
        assert "mismatch" in result.message.lower()

    def test_backup_rotation(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.side_effect = [(100,), (100,)]
        # 4 backups exist, max is 3 — oldest should be dropped
        mock_cursor.fetchall.return_value = [
            MockRow("icitem_backup_20260101"),
            MockRow("icitem_backup_20260201"),
            MockRow("icitem_backup_20260301"),
            MockRow("icitem_backup_20260331"),
        ]
        result = create_backup(mock_connection, "icitem", max_backups=3)
        assert result.status == "PASS"
        # Verify DROP was called for the oldest backup
        drop_calls = [c for c in mock_cursor.execute.call_args_list
                      if 'DROP TABLE dbo.icitem_backup_20260101' in str(c)]
        assert len(drop_calls) == 1

    def test_backup_sql_error(self, mock_connection, mock_cursor):
        mock_cursor.execute.side_effect = Exception("SQL error")
        result = create_backup(mock_connection, "icitem")
        assert result.status == "FAIL"
