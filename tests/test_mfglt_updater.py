"""Tests for mfg lead time updater — SQL shape and tuple-return contracts."""
from estship_uploader.mfglt_updater import (
    execute_update,
    validate_in_transaction,
    post_commit_verify,
)


def _executed_sql(mock_cursor) -> str:
    return " ".join(
        str(call[0][0]) for call in mock_cursor.execute.call_args_list
    )


class TestExecuteUpdate:
    def test_returns_tuple_of_step_and_rowcount(self, mock_connection, mock_cursor):
        mock_cursor.rowcount = 42
        result = execute_update(mock_connection)
        assert isinstance(result, tuple)
        step, rows_affected = result
        assert step.status == "PASS"
        assert rows_affected == 42

    def test_sql_has_no_warehouse_filter(self, mock_connection, mock_cursor):
        mock_cursor.rowcount = 1
        execute_update(mock_connection)
        sql = _executed_sql(mock_cursor)
        assert "cwarehouse" not in sql.lower()

    def test_failure_returns_zero_rows(self, mock_connection, mock_cursor):
        mock_cursor.execute.side_effect = Exception("boom")
        step, rows_affected = execute_update(mock_connection)
        assert step.status == "FAIL"
        assert rows_affected == 0


class TestValidateInTransaction:
    def test_pass_when_actual_matches_expected(self, mock_connection, mock_cursor):
        # mismatches=0, scope_count=10, @@TRANCOUNT=1
        mock_cursor.fetchone.side_effect = [(0,), (10,), (1,)]
        result = validate_in_transaction(
            mock_connection, expected_rows=10, actual_rows=10
        )
        assert result.status == "PASS"

    def test_fail_when_actual_differs_from_expected(
        self, mock_connection, mock_cursor
    ):
        mock_cursor.fetchone.side_effect = [(0,), (10,), (1,)]
        result = validate_in_transaction(
            mock_connection, expected_rows=10, actual_rows=7
        )
        assert result.status == "FAIL"
        assert "row count mismatch" in result.message

    def test_fail_on_mismatch_count(self, mock_connection, mock_cursor):
        # mismatches=3 -> fail immediately
        mock_cursor.fetchone.side_effect = [(3,), (10,), (1,)]
        result = validate_in_transaction(
            mock_connection, expected_rows=10, actual_rows=10
        )
        assert result.status == "FAIL"
        assert "mismatches" in result.message

    def test_fail_on_scope_drift(self, mock_connection, mock_cursor):
        # scope_count drifted away from expected_rows (concurrent insert/delete)
        mock_cursor.fetchone.side_effect = [(0,), (12,), (1,)]
        result = validate_in_transaction(
            mock_connection, expected_rows=10, actual_rows=10
        )
        assert result.status == "FAIL"
        assert "drift" in result.message.lower()

    def test_fail_on_lost_transaction(self, mock_connection, mock_cursor):
        # @@TRANCOUNT=0 means transaction was lost
        mock_cursor.fetchone.side_effect = [(0,), (10,), (0,)]
        result = validate_in_transaction(
            mock_connection, expected_rows=10, actual_rows=10
        )
        assert result.status == "FAIL"
        assert "TRANCOUNT" in result.message

    def test_sql_has_no_warehouse_filter(self, mock_connection, mock_cursor):
        mock_cursor.fetchone.side_effect = [(0,), (10,), (1,)]
        validate_in_transaction(
            mock_connection, expected_rows=10, actual_rows=10
        )
        sql = _executed_sql(mock_cursor)
        assert "cwarehouse" not in sql.lower()


class TestPostCommitVerify:
    def test_sql_has_no_warehouse_filter(self, mock_connection, mock_cursor):
        from tests.conftest import MockRow
        mock_cursor.fetchone.return_value = MockRow(10, 7, 45)
        post_commit_verify(mock_connection)
        sql = _executed_sql(mock_cursor)
        assert "cwarehouse" not in sql.lower()
