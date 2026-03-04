"""Upload steps 9-13 — transaction-wrapped UPDATE logic."""

from __future__ import annotations

import logging
from datetime import datetime

from estship_uploader.models import StepResult

logger = logging.getLogger(__name__)


def execute_update(conn) -> StepResult:
    """Step 8: Begin transaction and execute bulk UPDATE."""
    try:
        conn.autocommit = False
        cursor = conn.cursor()
        cursor.execute("SET NOCOUNT OFF")
        cursor.execute("""
            UPDATE t
            SET t.idestship = s.Est_Ship_Date
            FROM sostrs t
            JOIN dbo.EstShipUpload_Staging s
                ON t.csono = s.SO_Number
                AND t.clineitem = s.Line_Item
        """)
        rows_affected = cursor.rowcount
        cursor.close()
        return StepResult("PASS", f"UPDATE executed ({rows_affected} rows affected)")
    except Exception as e:
        # Attempt rollback on SQL error
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
    """Step 9: In-transaction validation — mismatch count + update count + @@TRANCOUNT."""
    try:
        cursor = conn.cursor()

        # 3A/3C: Count mismatches (should be 0)
        cursor.execute("""
            SELECT COUNT(*) FROM dbo.EstShipUpload_Staging s
            JOIN sostrs t ON t.csono = s.SO_Number AND t.clineitem = s.Line_Item
            WHERE s.Est_Ship_Date != t.idestship
        """)
        mismatches = cursor.fetchone()[0]

        # 3B: Count updated rows matches staging count
        cursor.execute("""
            SELECT COUNT(*) FROM sostrs t
            WHERE EXISTS (
                SELECT 1 FROM dbo.EstShipUpload_Staging s
                WHERE s.SO_Number = t.csono AND s.Line_Item = t.clineitem
            )
        """)
        updated_count = cursor.fetchone()[0]

        # 3D: Check transaction is still open
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
    """Step 10: COMMIT or ROLLBACK based on validation result."""
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
    """Step 11: Post-commit verification — count + date range."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) AS total_updated,
                MIN(t.idestship) AS earliest_date,
                MAX(t.idestship) AS latest_date
            FROM sostrs t
            WHERE EXISTS (
                SELECT 1 FROM dbo.EstShipUpload_Staging s
                WHERE s.SO_Number = t.csono AND s.Line_Item = t.clineitem
            )
        """)
        row = cursor.fetchone()
        cursor.close()

        total = row[0]
        earliest = row[1]
        latest = row[2]

        # Strip time portion if datetime
        if isinstance(earliest, datetime):
            earliest = earliest.date()
        if isinstance(latest, datetime):
            latest = latest.date()

        return StepResult(
            "PASS",
            f"Post-commit verified: {total} rows, {earliest} to {latest}",
            [f"Total: {total}", f"Earliest: {earliest}", f"Latest: {latest}"],
        )
    except Exception as e:
        return StepResult("FAIL", f"Post-commit verification error: {e}")


def cleanup_staging(conn) -> StepResult:
    """Step 12: Drop staging table. Always runs, best-effort."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            IF OBJECT_ID('dbo.EstShipUpload_Staging', 'U') IS NOT NULL
                DROP TABLE dbo.EstShipUpload_Staging
        """)
        cursor.close()
        return StepResult("PASS", "Staging table cleaned up")
    except Exception:
        # Cleanup failure is non-fatal
        return StepResult("PASS", "Staging table cleanup attempted (may already be dropped)")
