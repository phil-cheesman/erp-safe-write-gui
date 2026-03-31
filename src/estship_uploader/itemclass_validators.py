"""Validation steps 1-8 for item class (cbuyer) uploads."""

from __future__ import annotations

import logging

from estship_uploader.models import StepResult
from estship_uploader.itemclass_csv_parser import APPROVED_CBUYER

logger = logging.getLogger(__name__)

STAGING_TABLE = "dbo.ItemClassUpload_Staging"


def create_staging_table(conn, database: str) -> StepResult:
    """Step 1: Drop and recreate staging table."""
    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            IF OBJECT_ID('{STAGING_TABLE}', 'U') IS NOT NULL
                DROP TABLE {STAGING_TABLE}
        """)
        cursor.execute(f"""
            CREATE TABLE {STAGING_TABLE} (
                Item_Number   CHAR(20),
                Buyer_Class   CHAR(10)
            )
        """)
        cursor.close()
        return StepResult("PASS", "Staging table created")
    except Exception as e:
        return StepResult("FAIL", f"Failed to create staging table: {e}")


def import_to_staging(conn, rows: list[tuple]) -> StepResult:
    """Step 2: Insert CSV rows into staging table."""
    try:
        cursor = conn.cursor()
        cursor.fast_executemany = True
        cursor.executemany(
            f"INSERT INTO {STAGING_TABLE} "
            "(Item_Number, Buyer_Class) VALUES (?, ?)",
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
        cursor.execute(f"SELECT COUNT(*) FROM {STAGING_TABLE}")
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


def check_items_exist(conn) -> StepResult:
    """Step 4: Check all staging items exist in icitem.

    Missing items are removed from staging and reported as WARNING.
    """
    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT
                s.Item_Number,
                CASE WHEN EXISTS (
                    SELECT 1 FROM icitem t
                    WHERE t.citemno = s.Item_Number
                ) THEN 1 ELSE 0 END AS found
            FROM {STAGING_TABLE} s
        """)
        rows = cursor.fetchall()
        cursor.close()

        missing = [r for r in rows if r[1] == 0]
        total = len(rows)

        if not missing:
            return StepResult("PASS", f"Item check passed ({total}/{total} found)")

        # Remove missing items from staging
        cursor = conn.cursor()
        cursor.execute(f"""
            DELETE s FROM {STAGING_TABLE} s
            WHERE NOT EXISTS (
                SELECT 1 FROM icitem t
                WHERE t.citemno = s.Item_Number
            )
        """)
        removed = cursor.rowcount
        cursor.close()

        remaining = total - removed
        details = [
            f"  {(r[0] or '').strip()} — not found in icitem (removed from staging)"
            for r in missing
        ]
        details.append(f"  {remaining} rows remain in staging for upload")

        return StepResult(
            "WARNING",
            f"Item check: {len(missing)} of {total} not found — removed from staging",
            details,
        )
    except Exception as e:
        return StepResult("FAIL", f"Item check error: {e}")


def validate_cbuyer_values(conn) -> StepResult:
    """Step 5: Validate cbuyer values against approved list. Non-approved → WARNING."""
    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT DISTINCT LTRIM(RTRIM(Buyer_Class)) AS val
            FROM {STAGING_TABLE}
            WHERE LTRIM(RTRIM(Buyer_Class)) != ''
        """)
        db_values = [row[0] for row in cursor.fetchall()]
        cursor.close()

        non_approved = [v for v in db_values if v not in APPROVED_CBUYER]

        if not non_approved:
            return StepResult("PASS", "All cbuyer values are on the approved list")

        details = [f"  Non-approved value: '{v}'" for v in sorted(non_approved)]
        return StepResult(
            "WARNING",
            f"{len(non_approved)} non-approved cbuyer value(s) in staging",
            details,
        )
    except Exception as e:
        return StepResult("FAIL", f"Value validation error: {e}")


def check_value_changes(conn) -> StepResult:
    """Step 6: Show before/after cbuyer comparison (informational)."""
    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT
                s.Item_Number,
                LTRIM(RTRIM(t.cbuyer)) AS current_value,
                LTRIM(RTRIM(s.Buyer_Class)) AS new_value
            FROM {STAGING_TABLE} s
            JOIN icitem t ON t.citemno = s.Item_Number
            ORDER BY s.Item_Number
        """)
        rows = cursor.fetchall()
        cursor.close()

        total = len(rows)
        changed = 0
        details = []
        for r in rows:
            item = (r[0] or "").strip()
            current = r[1] or ""
            new = r[2] or ""
            if not current:
                current = "(blank)"
            if not new:
                new = "(blank)"
            if current == new:
                details.append(f"       {item}: {current} (no change)")
            else:
                changed += 1
                details.append(f"  [>>] {item}: {current} \u2192 {new}")

        return StepResult(
            "PASS",
            f"Value changes: {changed} of {total} rows will change",
            details,
        )
    except Exception as e:
        return StepResult("FAIL", f"Value change check error: {e}")


def check_anomalies(conn) -> StepResult:
    """Step 7: Check for anomalies — blanks being set, value distribution. WARNING only."""
    try:
        cursor = conn.cursor()

        # Count items being blanked
        cursor.execute(f"""
            SELECT COUNT(*) FROM {STAGING_TABLE}
            WHERE LTRIM(RTRIM(Buyer_Class)) = ''
        """)
        blank_count = cursor.fetchone()[0]

        # Value distribution
        cursor.execute(f"""
            SELECT
                CASE WHEN LTRIM(RTRIM(Buyer_Class)) = '' THEN '(blank)' ELSE LTRIM(RTRIM(Buyer_Class)) END AS val,
                COUNT(*) AS cnt
            FROM {STAGING_TABLE}
            GROUP BY LTRIM(RTRIM(Buyer_Class))
            ORDER BY COUNT(*) DESC
        """)
        dist_rows = cursor.fetchall()
        cursor.close()

        details = [f"  {r[0]}: {r[1]} item(s)" for r in dist_rows]

        if blank_count > 0:
            return StepResult(
                "WARNING",
                f"{blank_count} item(s) will have cbuyer cleared (set to blank)",
                details,
            )

        return StepResult(
            "PASS",
            "No anomalies detected",
            details,
        )
    except Exception as e:
        return StepResult("FAIL", f"Anomaly check error: {e}")


def get_summary(conn) -> StepResult:
    """Step 8: Final staging row count."""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {STAGING_TABLE}")
        count = cursor.fetchone()[0]
        cursor.close()
        return StepResult("PASS", f"{count} rows ready for upload")
    except Exception as e:
        return StepResult("FAIL", f"Summary check error: {e}")
