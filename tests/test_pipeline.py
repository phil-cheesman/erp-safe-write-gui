"""Tests for pipeline orchestration — step ordering, halt-on-error, cleanup."""

from unittest.mock import MagicMock, patch

from estship_uploader.models import StepResult
from estship_uploader.pipeline import run_validation, run_upload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pass_step(msg="ok"):
    return StepResult("PASS", msg)


def _fail_step(msg="error"):
    return StepResult("FAIL", msg)


def _warn_step(msg="warning"):
    return StepResult("WARNING", msg, ["detail1"])


# ---------------------------------------------------------------------------
# run_validation tests
# ---------------------------------------------------------------------------

@patch("estship_uploader.pipeline.updater")
@patch("estship_uploader.pipeline.validators")
def test_validation_all_pass(mock_validators, mock_updater, mock_connection):
    """All-pass validation → success=True, 8 steps."""
    mock_validators.create_staging_table.return_value = _pass_step("staging created")
    mock_validators.import_to_staging.return_value = _pass_step("3 rows imported")
    mock_validators.verify_import.return_value = _pass_step("verified")
    mock_validators.check_so_line_exists.return_value = _pass_step("all found")
    mock_validators.check_item_numbers.return_value = _pass_step("all match")
    mock_validators.check_date_changes.return_value = _pass_step("0 changes")
    mock_validators.check_date_anomalies.return_value = _pass_step("no anomalies")
    mock_validators.get_summary.return_value = _pass_step("3 rows ready")

    # Mock the cursor for the upload_count query after summary
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (3,)
    mock_connection.cursor.return_value = mock_cursor

    rows = [("SO1", "L1", "ITEM1", "2026-04-15")] * 3
    result = run_validation(mock_connection, rows, "testdb")

    assert result.success is True
    assert result.upload_count == 3
    assert len(result.steps) == 8


@patch("estship_uploader.pipeline.updater")
@patch("estship_uploader.pipeline.validators")
def test_validation_halt_on_error(mock_validators, mock_updater, mock_connection):
    """Halt on error → stops early, cleanup called."""
    mock_validators.create_staging_table.return_value = _pass_step()
    mock_validators.import_to_staging.return_value = _fail_step("import failed")

    rows = [("SO1", "L1", "ITEM1", "2026-04-15")]
    result = run_validation(mock_connection, rows, "testdb")

    assert result.success is False
    assert len(result.steps) == 2  # stopped after step 2
    # Cleanup should have been called (failure path)
    mock_updater.cleanup_staging.assert_called_once()


@patch("estship_uploader.pipeline.updater")
@patch("estship_uploader.pipeline.validators")
def test_validation_warning_passes_through(mock_validators, mock_updater, mock_connection):
    """Warning passes through → continues, success=True."""
    mock_validators.create_staging_table.return_value = _pass_step()
    mock_validators.import_to_staging.return_value = _pass_step()
    mock_validators.verify_import.return_value = _pass_step()
    mock_validators.check_so_line_exists.return_value = _pass_step()
    mock_validators.check_item_numbers.return_value = _pass_step()
    mock_validators.check_date_changes.return_value = _pass_step("0 changes")
    mock_validators.check_date_anomalies.return_value = _warn_step("3 past dates")
    mock_validators.get_summary.return_value = _pass_step("3 rows ready")

    # Mock the cursor for the upload_count query after summary
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (3,)
    mock_connection.cursor.return_value = mock_cursor

    rows = [("SO1", "L1", "ITEM1", "2026-04-15")] * 3
    result = run_validation(mock_connection, rows, "testdb")

    assert result.success is True
    assert result.steps[6].status == "WARNING"


# ---------------------------------------------------------------------------
# run_upload tests
# ---------------------------------------------------------------------------

@patch("estship_uploader.pipeline.updater")
def test_upload_success(mock_updater, mock_connection):
    """Upload success → all steps, cleanup runs."""
    mock_updater.execute_update.return_value = _pass_step("47 rows affected")
    mock_updater.validate_in_transaction.return_value = _pass_step("validated")
    mock_updater.commit_or_rollback.return_value = _pass_step("committed")
    mock_updater.post_commit_verify.return_value = _pass_step("verified")
    mock_updater.cleanup_staging.return_value = _pass_step("cleaned up")

    result = run_upload(mock_connection, 47)

    assert result.success is True
    # 4 steps + cleanup = 5
    assert len(result.steps) == 5
    mock_updater.cleanup_staging.assert_called_once()


@patch("estship_uploader.pipeline.updater")
def test_upload_rollback_on_mismatch(mock_updater, mock_connection):
    """Upload rollback on mismatch → ROLLBACK + cleanup."""
    mock_updater.execute_update.return_value = _pass_step("47 rows affected")
    mock_updater.validate_in_transaction.return_value = _fail_step("mismatches found")
    mock_updater.commit_or_rollback.return_value = _fail_step("rolled back")
    mock_updater.cleanup_staging.return_value = _pass_step("cleaned up")

    result = run_upload(mock_connection, 47)

    assert result.success is False
    # commit_or_rollback called with validation_passed=False
    mock_updater.commit_or_rollback.assert_called_once_with(mock_connection, False)
    mock_updater.cleanup_staging.assert_called_once()


@patch("estship_uploader.pipeline.updater")
def test_upload_cleanup_on_exception(mock_updater, mock_connection):
    """Cleanup always runs even on unexpected exception."""
    mock_updater.execute_update.side_effect = RuntimeError("unexpected!")
    mock_updater.cleanup_staging.return_value = _pass_step("cleaned up")

    result = run_upload(mock_connection, 47)

    assert result.success is False
    # Cleanup must still run
    mock_updater.cleanup_staging.assert_called_once()
