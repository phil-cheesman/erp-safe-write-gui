"""Pipeline orchestration for reorder point uploads."""

from __future__ import annotations

import logging

from estship_uploader import reordpt_validators as validators, reordpt_updater as updater
from estship_uploader.models import StepResult, PipelineResult
from estship_uploader.pipeline import _emit

logger = logging.getLogger(__name__)


def run_validation(conn, rows: list[tuple], database: str, on_step=None) -> PipelineResult:
    """Run validation steps for reorder point upload.

    Halts on FAIL, passes WARNING through.
    Cleans up staging table on failure.
    """
    result = PipelineResult()

    try:
        conn.execute(f"USE {database}")

        # Step 1: Create staging table
        step = validators.create_staging_table(conn, database)
        _emit(result, step, on_step)
        if step.status == "FAIL":
            return result

        # Step 2: Import CSV rows to staging
        step = validators.import_to_staging(conn, rows)
        _emit(result, step, on_step)
        if step.status == "FAIL":
            return result

        # Step 3: Verify import count
        step = validators.verify_import(conn, len(rows))
        _emit(result, step, on_step)
        if step.status == "FAIL":
            return result

        # Step 4: Check items exist in iciwhs
        step = validators.check_items_exist(conn)
        _emit(result, step, on_step)
        if step.status == "FAIL":
            return result

        # Step 5: Before/after reorder point comparison (informational)
        step = validators.check_value_changes(conn)
        _emit(result, step, on_step)

        # Step 6: Anomaly check (WARNING doesn't block)
        step = validators.check_anomalies(conn)
        _emit(result, step, on_step)

        # Step 7: Summary
        step = validators.get_summary(conn)
        _emit(result, step, on_step)

        # Get final staging count
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {validators.STAGING_TABLE}")
        result.upload_count = cursor.fetchone()[0]
        cursor.close()

        if result.upload_count == 0:
            _emit(result, StepResult(
                "FAIL", "No rows remaining in staging after validation"), on_step)
            return result

        # Step 8: Compute the (item x warehouse) fan-out scope.
        scope_step, expected_rows, _warehouses = validators.compute_update_scope(conn)
        _emit(result, scope_step, on_step)
        if scope_step.status == "FAIL":
            return result
        result.expected_rows = expected_rows

        if result.expected_rows == 0:
            _emit(result, StepResult(
                "FAIL",
                "No iciwhs rows would be updated for the staged items"),
                on_step)
            return result

        result.success = True

    except Exception as e:
        step = StepResult("FAIL", f"Unexpected error: {e}")
        _emit(result, step, on_step)
    finally:
        if not result.success:
            try:
                updater.cleanup_staging(conn)
            except Exception:
                pass

    return result


def run_upload(conn, expected_rows: int, database: str = "", on_step=None) -> PipelineResult:
    """Run upload steps for reorder point. ROLLBACK on error, cleanup in finally."""
    result = PipelineResult()

    try:
        if database:
            conn.execute(f"USE {database}")

        # Backup iciwhs table
        step = updater.backup_table(conn)
        _emit(result, step, on_step)
        if step.status == "FAIL":
            return result

        # Execute UPDATE in transaction
        step, actual_rows = updater.execute_update(conn)
        _emit(result, step, on_step)
        if step.status == "FAIL":
            return result

        # In-transaction validation — compare actual vs expected row count
        step = updater.validate_in_transaction(conn, expected_rows, actual_rows)
        _emit(result, step, on_step)
        validation_passed = step.status != "FAIL"

        # Commit or rollback
        step = updater.commit_or_rollback(conn, validation_passed)
        _emit(result, step, on_step)
        if step.status == "FAIL":
            return result

        # Post-commit verify (only if committed)
        if validation_passed:
            step = updater.post_commit_verify(conn)
            _emit(result, step, on_step)

        result.success = validation_passed

    except Exception as e:
        step = StepResult("FAIL", f"Unexpected error: {e}")
        _emit(result, step, on_step)
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        try:
            conn.autocommit = True
        except Exception:
            pass
    finally:
        # Always cleanup staging
        step = updater.cleanup_staging(conn)
        _emit(result, step, on_step)

    return result
