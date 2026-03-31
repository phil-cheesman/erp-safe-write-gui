"""Upload steps for item class (cbuyer) — transaction-wrapped UPDATE logic."""

from __future__ import annotations

import logging

from estship_uploader.models import StepResult
from estship_uploader.backup import create_backup

logger = logging.getLogger(__name__)

STAGING_TABLE = "dbo.ItemClassUpload_Staging"


def backup_table(conn) -> StepResult:
    """Step 9a: Create a backup of the icitem table before updating."""
    return create_backup(conn, "icitem")


def execute_update(conn) -> StepResult:
    """Step 9b: Begin transaction and execute bulk UPDATE."""
    try:
        conn.autocommit = False
        cursor = conn.cursor()
        cursor.execute("SET NOCOUNT OFF")
        cursor.execute(f"""
            UPDATE t
            SET t.cbuyer = s.Buyer_Class
            FROM icitem t
            JOIN {STAGING_TABLE} s
                ON t.citemno = s.Item_Number
        """)
        rows_affected = cursor.rowcount
        cursor.close()
        return StepResult("PASS", f"UPDATE executed ({rows_affected} rows affected)")
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        try:
            conn.autocommit = True
        except Exception:
            pass
        return StepResult("FAIL", f"UPDATE failed: {e}")


def validate_in_transaction(conn, expected_count: int) -> StepResult:
    """Step 10: In-transaction validation — mismatch count + update count + @@TRANCOUNT."""
    try:
        cursor = conn.cursor()

        # Count mismatches (should be 0 after UPDATE)
        # Use LTRIM/RTRIM for CHAR comparison and handle empty strings
        cursor.execute(f"""
            SELECT COUNT(*) FROM {STAGING_TABLE} s
            JOIN icitem t ON t.citemno = s.Item_Number
            WHERE LTRIM(RTRIM(ISNULL(s.Buyer_Class, '')))
               != LTRIM(RTRIM(ISNULL(t.cbuyer, '')))
        """)
        mismatches = cursor.fetchone()[0]

        # Count updated rows
        cursor.execute(f"""
            SELECT COUNT(*) FROM icitem t
            WHERE EXISTS (
                SELECT 1 FROM {STAGING_TABLE} s
                WHERE s.Item_Number = t.citemno
            )
        """)
        updated_count = cursor.fetchone()[0]

        # Check transaction is still open
        cursor.execute("SELECT @@TRANCOUNT")
        trancount = cursor.fetchone()[0]

        cursor.close()

        details = [
            f"Mismatches: {mismatches}",
            f"Updated rows: {updated_count} (expected {expected_count})",
            f"@@TRANCOUNT: {trancount}",
        ]

        if mismatches > 0:
            return StepResult(
                "FAIL",
                f"In-transaction validation failed: {mismatches} mismatches",
                details,
            )

        if updated_count != expected_count:
            return StepResult(
                "FAIL",
                f"In-transaction validation failed: count mismatch "
                f"({updated_count} vs {expected_count})",
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
    """Step 11: COMMIT or ROLLBACK based on validation result."""
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
    """Step 12: Post-commit verification — count + value distribution."""
    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT
                COUNT(*) AS total_updated,
                COUNT(DISTINCT LTRIM(RTRIM(t.cbuyer))) AS distinct_values
            FROM icitem t
            WHERE EXISTS (
                SELECT 1 FROM {STAGING_TABLE} s
                WHERE s.Item_Number = t.citemno
            )
        """)
        row = cursor.fetchone()
        cursor.close()

        total = row[0]
        distinct = row[1]

        return StepResult(
            "PASS",
            f"Post-commit verified: {total} rows, {distinct} distinct value(s)",
            [f"Total: {total}", f"Distinct values: {distinct}"],
        )
    except Exception as e:
        return StepResult("FAIL", f"Post-commit verification error: {e}")


def cleanup_staging(conn) -> StepResult:
    """Step 13: Drop staging table. Always runs, best-effort."""
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
