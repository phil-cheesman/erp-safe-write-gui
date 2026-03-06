"""Pipeline orchestration — step runners."""

from __future__ import annotations

import logging

from estship_uploader import validators, updater
from estship_uploader.models import StepResult, PipelineResult

logger = logging.getLogger(__name__)


def _emit(result, step, on_step):
    """Append step to result and call on_step callback if provided."""
    result.steps.append(step)
    if on_step:
        on_step(step)


def run_validation(conn, rows: list[tuple], database: str, on_step=None) -> PipelineResult:
    """Run validation Steps 1-8. Halts on FAIL, passes WARNING through.

    Cleans up staging table on failure.
    If on_step is provided, it is called after each step with the StepResult.
    """
    result = PipelineResult()

    try:
        # Ensure we're in the correct database context (may drift after
        # autocommit toggles in previous upload cycles).
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

        # Step 4: Check SO/Line exists in sostrs
        # WARNING = some rows removed from staging; FAIL = SQL error
        step = validators.check_so_line_exists(conn)
        _emit(result, step, on_step)
        if step.status == "FAIL":
            return result

        # Step 5: Item number cross-check
        step = validators.check_item_numbers(conn)
        _emit(result, step, on_step)
        if step.status == "FAIL":
            return result

        # Step 6: Before/after date comparison (informational)
        step = validators.check_date_changes(conn)
        _emit(result, step, on_step)
        # Informational only — no halt logic

        # Step 7: Date anomaly check (WARNING doesn't block)
        step = validators.check_date_anomalies(conn)
        _emit(result, step, on_step)
        # WARNING is OK — continue

        # Step 8: Summary — also captures final staging count for upload
        step = validators.get_summary(conn)
        _emit(result, step, on_step)

        # Extract the upload count from staging (after any removals in step 4)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM dbo.EstShipUpload_Staging")
        result.upload_count = cursor.fetchone()[0]
        cursor.close()

        if result.upload_count == 0:
            _emit(result, StepResult(
                "FAIL", "No rows remaining in staging after validation"), on_step)
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


def run_upload(conn, expected_count: int, database: str = "", on_step=None) -> PipelineResult:
    """Run upload Steps 9-13. ROLLBACK on error, cleanup in finally.

    Expects staging table to already exist with validated data.
    If on_step is provided, it is called after each step with the StepResult.
    """
    result = PipelineResult()

    try:
        # Re-assert database context before upload
        if database:
            conn.execute(f"USE {database}")

        # Step 9: Execute UPDATE in transaction
        step = updater.execute_update(conn)
        _emit(result, step, on_step)
        if step.status == "FAIL":
            return result

        # Step 10: In-transaction validation
        step = updater.validate_in_transaction(conn, expected_count)
        _emit(result, step, on_step)
        validation_passed = step.status != "FAIL"

        # Step 11: Commit or rollback
        step = updater.commit_or_rollback(conn, validation_passed)
        _emit(result, step, on_step)
        if step.status == "FAIL":
            return result

        # Step 12: Post-commit verify (only if committed)
        if validation_passed:
            step = updater.post_commit_verify(conn)
            _emit(result, step, on_step)

        result.success = validation_passed

    except Exception as e:
        step = StepResult("FAIL", f"Unexpected error: {e}")
        _emit(result, step, on_step)
        # Attempt rollback on unexpected error
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        try:
            conn.autocommit = True
        except Exception:
            pass
    finally:
        # Step 13: Always cleanup staging
        step = updater.cleanup_staging(conn)
        _emit(result, step, on_step)

    return result
