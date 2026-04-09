"""Upload steps for manufacturing lead time — transaction-wrapped UPDATE logic."""

from __future__ import annotations

import logging

from estship_uploader.models import StepResult
from estship_uploader.backup import create_backup

logger = logging.getLogger(__name__)

STAGING_TABLE = "dbo.MfgLTUpload_Staging"


def backup_table(conn) -> StepResult:
    """Create a backup of the iciwhs table before updating."""
    return create_backup(conn, "iciwhs")


def execute_update(conn) -> tuple[StepResult, int]:
    """Begin transaction and execute bulk UPDATE on iciwhs across all warehouses.

    Every warehouse row that matches a staged item gets the new lead time.
    Returns (StepResult, rows_affected) so the caller can verify the row count
    against the value computed during validation.
    """
    try:
        conn.autocommit = False
        cursor = conn.cursor()
        cursor.execute("SET NOCOUNT OFF")
        cursor.execute(f"""
            UPDATE t
            SET t.nmfgltime = s.Mfg_Lead_Time
            FROM iciwhs t
            JOIN {STAGING_TABLE} s
                ON t.citemno = s.Item_Number
        """)
        rows_affected = cursor.rowcount
        cursor.close()
        return (
            StepResult("PASS", f"UPDATE executed ({rows_affected} rows affected)"),
            rows_affected,
        )
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        try:
            conn.autocommit = True
        except Exception:
            pass
        return StepResult("FAIL", f"UPDATE failed: {e}"), 0


def validate_in_transaction(
    conn, expected_rows: int, actual_rows: int
) -> StepResult:
    """In-transaction validation — mismatch count + actual-vs-expected + @@TRANCOUNT.

    `expected_rows` is the (item x warehouse) fan-out computed during
    validation by `mfglt_validators.compute_update_scope`. `actual_rows` is
    the cursor.rowcount returned by the UPDATE. The two MUST match exactly,
    or we roll back — anything else means the world changed under us
    (concurrent insert/delete, etc.).
    """
    try:
        cursor = conn.cursor()

        # Count mismatches (should be 0 after UPDATE)
        cursor.execute(f"""
            SELECT COUNT(*) FROM {STAGING_TABLE} s
            JOIN iciwhs t ON t.citemno = s.Item_Number
            WHERE ISNULL(s.Mfg_Lead_Time, -1) != ISNULL(t.nmfgltime, -1)
        """)
        mismatches = cursor.fetchone()[0]

        # Re-count touched rows (defense in depth — should equal actual_rows
        # AND expected_rows; any drift signals a concurrent change)
        cursor.execute(f"""
            SELECT COUNT(*) FROM iciwhs t
            WHERE EXISTS (
                SELECT 1 FROM {STAGING_TABLE} s
                WHERE s.Item_Number = t.citemno
            )
        """)
        scope_count = cursor.fetchone()[0]

        # Check transaction is still open
        cursor.execute("SELECT @@TRANCOUNT")
        trancount = cursor.fetchone()[0]

        cursor.close()

        details = [
            f"Mismatches: {mismatches}",
            f"Rows updated: {actual_rows} (expected {expected_rows})",
            f"In-scope rows now: {scope_count}",
            f"@@TRANCOUNT: {trancount}",
        ]

        if mismatches > 0:
            return StepResult(
                "FAIL",
                f"In-transaction validation failed: {mismatches} mismatches",
                details,
            )

        if actual_rows != expected_rows:
            return StepResult(
                "FAIL",
                f"In-transaction validation failed: row count mismatch "
                f"(updated {actual_rows}, expected {expected_rows})",
                details,
            )

        if scope_count != expected_rows:
            return StepResult(
                "FAIL",
                f"In-transaction validation failed: in-scope row count drifted "
                f"({scope_count} vs {expected_rows})",
                details,
            )

        if trancount != 1:
            return StepResult(
                "FAIL",
                f"In-transaction validation failed: unexpected @@TRANCOUNT={trancount}",
                details,
            )

        return StepResult("PASS", "In-transaction validation passed", details)
    except Exception as e:
        return StepResult("FAIL", f"In-transaction validation error: {e}")


def commit_or_rollback(conn, validation_passed: bool) -> StepResult:
    """COMMIT or ROLLBACK based on validation result."""
    try:
        cursor = conn.cursor()
        if validation_passed:
            cursor.execute("COMMIT")
            cursor.close()
            conn.autocommit = True
            return StepResult("PASS", "Transaction committed")
        else:
            cursor.execute("ROLLBACK")
            cursor.close()
            conn.autocommit = True
            return StepResult("FAIL", "Transaction rolled back due to validation failure")
    except Exception as e:
        try:
            conn.autocommit = True
        except Exception:
            pass
        return StepResult("FAIL", f"Commit/rollback error: {e}")


def post_commit_verify(conn) -> StepResult:
    """Post-commit verification — count + value range across all warehouses."""
    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT
                COUNT(*) AS total_updated,
                MIN(t.nmfgltime) AS min_lt,
                MAX(t.nmfgltime) AS max_lt
            FROM iciwhs t
            WHERE EXISTS (
                SELECT 1 FROM {STAGING_TABLE} s
                WHERE s.Item_Number = t.citemno
            )
        """)
        row = cursor.fetchone()
        cursor.close()

        total = row[0]
        min_lt = row[1]
        max_lt = row[2]

        return StepResult(
            "PASS",
            f"Post-commit verified: {total} rows, lead times {min_lt} to {max_lt}",
            [f"Total: {total}", f"Min: {min_lt}", f"Max: {max_lt}"],
        )
    except Exception as e:
        return StepResult("FAIL", f"Post-commit verification error: {e}")


def cleanup_staging(conn) -> StepResult:
    """Drop staging table. Always runs, best-effort."""
    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            IF OBJECT_ID('{STAGING_TABLE}', 'U') IS NOT NULL
                DROP TABLE {STAGING_TABLE}
        """)
        cursor.close()
        return StepResult("PASS", "Staging table cleaned up")
    except Exception:
        return StepResult("PASS", "Staging table cleanup attempted (may already be dropped)")
