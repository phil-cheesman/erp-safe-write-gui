"""Tests for updater module — transaction flow, commit, rollback, cleanup."""

from unittest.mock import MagicMock, call

from estship_uploader.updater import (
    execute_update,
    validate_in_transaction,
    commit_or_rollback,
    post_commit_verify,
    cleanup_staging,
)


# -- Step 8: execute_update --

def test_execute_update_success(mock_connection, mock_cursor):
    mock_cursor.rowcount = 47
    result = execute_update(mock_connection)
    assert result.status == "PASS"
    assert "47" in result.message


def test_execute_update_sql_error(mock_connection, mock_cursor):
    mock_cursor.execute.side_effect = Exception("deadlock")
    result = execute_update(mock_connection)
    assert result.status == "FAIL"
    assert "deadlock" in result.message
    # Verify rollback was attempted
    mock_connection.execute.assert_called_with("ROLLBACK")


# -- Step 9: validate_in_transaction --

def test_validate_in_transaction_pass(mock_connection, mock_cursor):
    # mismatches=0, updated_count=5, trancount=1
    mock_cursor.fetchone.side_effect = [(0,), (5,), (1,)]
    result = validate_in_transaction(mock_connection, 5)
    assert result.status == "PASS"


def test_validate_in_transaction_mismatch(mock_connection, mock_cursor):
    # mismatches=2, updated_count=5, trancount=1
    mock_cursor.fetchone.side_effect = [(2,), (5,), (1,)]
    result = validate_in_transaction(mock_connection, 5)
    assert result.status == "FAIL"
    assert "mismatch" in result.message.lower()


def test_validate_in_transaction_count_mismatch(mock_connection, mock_cursor):
    # mismatches=0, updated_count=3 (expected 5), trancount=1
    mock_cursor.fetchone.side_effect = [(0,), (3,), (1,)]
    result = validate_in_transaction(mock_connection, 5)
    assert result.status == "FAIL"
    assert "count mismatch" in result.message.lower()


# -- Step 10: commit_or_rollback --

def test_commit_on_success(mock_connection, mock_cursor):
    result = commit_or_rollback(mock_connection, True)
    assert result.status == "PASS"
    assert "committed" in result.message.lower()
    # Verify COMMIT was executed
    mock_cursor.execute.assert_called_with("COMMIT")


def test_rollback_on_failure(mock_connection, mock_cursor):
    result = commit_or_rollback(mock_connection, False)
    assert result.status == "FAIL"
    assert "rolled back" in result.message.lower()
    mock_cursor.execute.assert_called_with("ROLLBACK")


# -- Step 11: post_commit_verify --

def test_post_commit_verify(mock_connection, mock_cursor):
    mock_cursor.fetchone.return_value = (47, "2026-04-15", "2026-06-30")
    result = post_commit_verify(mock_connection)
    assert result.status == "PASS"
    assert "47" in result.message


# -- Step 12: cleanup_staging --

def test_cleanup_success(mock_connection, mock_cursor):
    result = cleanup_staging(mock_connection)
    assert result.status == "PASS"


def test_cleanup_error_still_passes(mock_connection, mock_cursor):
    """Cleanup failure is non-fatal — should still return PASS."""
    mock_cursor.execute.side_effect = Exception("table already dropped")
    result = cleanup_staging(mock_connection)
    assert result.status == "PASS"
