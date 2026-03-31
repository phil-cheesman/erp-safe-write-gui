"""Validation steps for manufacturing lead time (nmfgltime) uploads."""

from __future__ import annotations

import logging

from estship_uploader.models import StepResult

logger = logging.getLogger(__name__)

STAGING_TABLE = "dbo.MfgLTUpload_Staging"


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
                Item_Number    CHAR(20),
                Mfg_Lead_Time  INT NULL
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
            "(Item_Number, Mfg_Lead_Time) VALUES (?, ?)",
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
    """Step 4: Check all staging items exist in iciwhs WHERE cwarehouse='MAIN'.

    Missing items are removed from staging and reported as WARNING.
    """
    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT
                s.Item_Number,
                CASE WHEN EXISTS (
                    SELECT 1 FROM iciwhs t
                    WHERE t.citemno = s.Item_Number
                      AND t.cwarehouse = 'MAIN'
                ) THEN 1 ELSE 0 END AS found
            FROM {STAGING_TABLE} s
        """)
        rows = cursor.fetchall()
        cursor.close()

        missing = [r for r in rows if r[1] == 0]
        total = len(rows)

        if not missing:
            return StepResult(
                "PASS", f"Item check passed ({total}/{total} found in MAIN warehouse)")

        # Remove missing items from staging
        cursor = conn.cursor()
        cursor.execute(f"""
            DELETE s FROM {STAGING_TABLE} s
            WHERE NOT EXISTS (
                SELECT 1 FROM iciwhs t
                WHERE t.citemno = s.Item_Number
                  AND t.cwarehouse = 'MAIN'
            )
        """)
        removed = cursor.rowcount
        cursor.close()

        remaining = total - removed
        details = [
            f"  {(r[0] or '').strip()} — not found in iciwhs/MAIN (removed from staging)"
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


def check_value_changes(conn) -> StepResult:
    """Step 5: Show before/after lead time comparison (informational)."""
    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT
                s.Item_Number,
                t.nmfgltime AS current_value,
                s.Mfg_Lead_Time AS new_value
            FROM {STAGING_TABLE} s
            JOIN iciwhs t ON t.citemno = s.Item_Number AND t.cwarehouse = 'MAIN'
            ORDER BY s.Item_Number
        """)
        rows = cursor.fetchall()
        cursor.close()

        total = len(rows)
        changed = 0
        details = []
        for r in rows:
            item = (r[0] or "").strip()
            current = r[1]
            new = r[2]
            current_str = str(current) if current is not None else "NULL"
            new_str = str(new) if new is not None else "NULL"
            if current_str == new_str:
                details.append(f"       {item}: {current_str} (no change)")
            else:
                changed += 1
                details.append(f"  [>>] {item}: {current_str} \u2192 {new_str}")

        return StepResult(
            "PASS",
            f"Lead time changes: {changed} of {total} rows will change",
            details,
        )
    except Exception as e:
        return StepResult("FAIL", f"Value change check error: {e}")


def check_anomalies(conn) -> StepResult:
    """Step 6: Check for anomalies — zero values, very large values. WARNING only."""
    try:
        cursor = conn.cursor()

        # Count zeros
        cursor.execute(f"""
            SELECT COUNT(*) FROM {STAGING_TABLE}
            WHERE Mfg_Lead_Time = 0
        """)
        zero_count = cursor.fetchone()[0]

        # Count NULLs
        cursor.execute(f"""
            SELECT COUNT(*) FROM {STAGING_TABLE}
            WHERE Mfg_Lead_Time IS NULL
        """)
        null_count = cursor.fetchone()[0]

        # Count very large (>365 days)
        cursor.execute(f"""
            SELECT COUNT(*) FROM {STAGING_TABLE}
            WHERE Mfg_Lead_Time > 365
        """)
        large_count = cursor.fetchone()[0]

        cursor.close()

        issues = []
        if null_count:
            issues.append(f"{null_count} item(s) will have lead time cleared (NULL)")
        if zero_count:
            issues.append(f"{zero_count} item(s) set to 0 days")
        if large_count:
            issues.append(f"{large_count} item(s) > 365 days")

        if issues:
            return StepResult("WARNING", "; ".join(issues), issues)

        return StepResult("PASS", "No anomalies detected")
    except Exception as e:
        return StepResult("FAIL", f"Anomaly check error: {e}")


def get_summary(conn) -> StepResult:
    """Step 7: Final staging row count."""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {STAGING_TABLE}")
        count = cursor.fetchone()[0]
        cursor.close()
        return StepResult("PASS", f"{count} rows ready for upload")
    except Exception as e:
        return StepResult("FAIL", f"Summary check error: {e}")
