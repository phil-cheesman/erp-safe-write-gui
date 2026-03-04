"""Validation steps 1-8 — each returns a StepResult."""

from __future__ import annotations

import logging
from datetime import date, datetime

from estship_uploader.models import StepResult

logger = logging.getLogger(__name__)


def create_staging_table(conn, database: str) -> StepResult:
    """Step 1: Drop and recreate staging table."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            IF OBJECT_ID('dbo.EstShipUpload_Staging', 'U') IS NOT NULL
                DROP TABLE dbo.EstShipUpload_Staging
        """)
        cursor.execute("""
            CREATE TABLE dbo.EstShipUpload_Staging (
                SO_Number     CHAR(10),
                Line_Item     CHAR(10),
                Item_Number   CHAR(20),
                Est_Ship_Date DATE
            )
        """)
        cursor.close()
        return StepResult("PASS", "Staging table created")
    except Exception as e:
        return StepResult("FAIL", f"Failed to create staging table: {e}")


def import_to_staging(conn, rows: list[tuple]) -> StepResult:
    """Step 2: Insert CSV rows into staging table via parameterized executemany."""
    try:
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT INTO dbo.EstShipUpload_Staging "
            "(SO_Number, Line_Item, Item_Number, Est_Ship_Date) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )
        cursor.close()
        return StepResult("PASS", f"{len(rows)} rows imported to staging")
    except Exception as e:
        return StepResult("FAIL", f"Failed to import rows: {e}")


def verify_import(conn, expected_count: int) -> StepResult:
    """Step 3: Verify staging row count matches expected."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM dbo.EstShipUpload_Staging")
        actual = cursor.fetchone()[0]
        cursor.close()
        if actual == expected_count:
            return StepResult("PASS", f"Import verified ({actual} rows)")
        else:
            return StepResult(
                "FAIL",
                f"Row count mismatch: expected {expected_count}, got {actual}",
            )
    except Exception as e:
        return StepResult("FAIL", f"Failed to verify import: {e}")


def check_so_line_exists(conn) -> StepResult:
    """Step 4: Check all staging SO/Line pairs exist in sostrs."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                s.SO_Number, s.Line_Item, s.Item_Number, s.Est_Ship_Date,
                CASE WHEN EXISTS (
                    SELECT 1 FROM sostrs t
                    WHERE t.csono = s.SO_Number AND t.clineitem = s.Line_Item
                ) THEN 1 ELSE 0 END AS found
            FROM dbo.EstShipUpload_Staging s
        """)
        rows = cursor.fetchall()
        cursor.close()

        missing = [r for r in rows if r[4] == 0]
        total = len(rows)

        if not missing:
            return StepResult("PASS", f"SO/Line check passed ({total}/{total} found)")

        details = [
            f"  SO {r[0].strip()} / {r[2].strip()} — not found in sostrs"
            for r in missing
        ]
        return StepResult(
            "FAIL",
            f"SO/Line check failed: {len(missing)} of {total} not found",
            details,
        )
    except Exception as e:
        return StepResult("FAIL", f"SO/Line check error: {e}")


def check_item_numbers(conn) -> StepResult:
    """Step 5: Cross-check item numbers between staging and sostrs."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                s.SO_Number, s.Line_Item,
                LTRIM(RTRIM(s.Item_Number)) AS csv_item,
                LTRIM(RTRIM(t.citemno)) AS db_item,
                CASE WHEN LTRIM(RTRIM(s.Item_Number)) = LTRIM(RTRIM(t.citemno))
                    THEN 1 ELSE 0 END AS match
            FROM dbo.EstShipUpload_Staging s
            JOIN sostrs t ON t.csono = s.SO_Number AND t.clineitem = s.Line_Item
        """)
        rows = cursor.fetchall()
        cursor.close()

        mismatches = [r for r in rows if r[4] == 0]
        total = len(rows)

        if not mismatches:
            return StepResult("PASS", f"Item cross-check passed ({total}/{total} match)")

        details = [
            f"  SO {r[0].strip()} / CSV item '{r[2]}' != DB item '{r[3]}'"
            for r in mismatches
        ]
        return StepResult(
            "FAIL",
            f"Item mismatch: {len(mismatches)} of {total} don't match",
            details,
        )
    except Exception as e:
        return StepResult("FAIL", f"Item cross-check error: {e}")


def check_date_changes(conn) -> StepResult:
    """Step 6: Compare current vs new dates (informational)."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                s.SO_Number, s.Line_Item,
                LTRIM(RTRIM(s.Item_Number)),
                t.idestship, s.Est_Ship_Date
            FROM dbo.EstShipUpload_Staging s
            JOIN sostrs t ON t.csono = s.SO_Number AND t.clineitem = s.Line_Item
            ORDER BY s.SO_Number
        """)
        rows = cursor.fetchall()
        cursor.close()

        total = len(rows)
        changed = 0
        details = []
        for r in rows:
            so = r[0].strip() if r[0] else "?"
            item = r[2].strip() if r[2] else "?"
            current = r[3]
            new = r[4]
            # Strip time portion — DB returns datetime, we only care about date
            if isinstance(current, datetime):
                current = current.date()
            current_str = str(current) if current else "NULL"
            new_str = str(new) if new else "NULL"
            if current_str == new_str:
                details.append(f"       SO {so} / {item}: {current_str} (no change)")
            else:
                changed += 1
                details.append(f"  [>>] SO {so} / {item}: {current_str} \u2192 {new_str}")

        return StepResult(
            "PASS",
            f"Date changes: {changed} of {total} rows will change",
            details,
        )
    except Exception as e:
        return StepResult("FAIL", f"Date change check error: {e}")


def check_date_anomalies(conn) -> StepResult:
    """Step 7: Check for past, far-future, or null dates. Returns WARNING, not FAIL."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                SO_Number, Line_Item, Est_Ship_Date,
                DATEDIFF(day, GETDATE(), Est_Ship_Date) AS days_from_now
            FROM dbo.EstShipUpload_Staging
            WHERE Est_Ship_Date < CAST(GETDATE() AS DATE)
               OR Est_Ship_Date > DATEADD(year, 1, GETDATE())
               OR Est_Ship_Date IS NULL
        """)
        anomalies = cursor.fetchall()
        cursor.close()

        if not anomalies:
            return StepResult("PASS", "No date anomalies")

        # Query item numbers for display
        cursor = conn.cursor()
        cursor.execute("""
            SELECT SO_Number, Item_Number FROM dbo.EstShipUpload_Staging
        """)
        item_lookup = {r[0].strip(): r[1].strip() for r in cursor.fetchall()}
        cursor.close()

        details = []
        for r in anomalies:
            so = r[0].strip() if r[0] else "?"
            item = item_lookup.get(so, "?")
            date = r[2]
            days = r[3]
            if date is None:
                details.append(f"  SO {so} / {item} — NULL date")
            elif days < 0:
                details.append(f"  SO {so} / {item} — {date} ({abs(days)} days past)")
            else:
                details.append(f"  SO {so} / {item} — {date} ({days} days future, >1 year)")

        return StepResult(
            "WARNING",
            f"Date anomalies: {len(anomalies)} rows",
            details,
        )
    except Exception as e:
        return StepResult("FAIL", f"Date anomaly check error: {e}")


def get_summary(conn) -> StepResult:
    """Step 8: Final staging row count — ready for upload."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM dbo.EstShipUpload_Staging")
        count = cursor.fetchone()[0]
        cursor.close()
        return StepResult("PASS", f"{count} rows ready for upload")
    except Exception as e:
        return StepResult("FAIL", f"Summary check error: {e}")
