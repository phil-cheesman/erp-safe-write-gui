"""Table backup utility — create date-stamped backups with rotation."""

from __future__ import annotations

import logging
from datetime import datetime

from estship_uploader.models import StepResult

logger = logging.getLogger(__name__)


def create_backup(conn, table_name: str, max_backups: int = 5) -> StepResult:
    """Create a date-stamped backup of a table, rotating old backups.

    Creates ``dbo.{table_name}_backup_YYYYMMDD``.  If today's backup already
    exists it is dropped and recreated.  If more than *max_backups* backups
    exist (matching the naming pattern), the oldest are dropped.

    Returns a StepResult with PASS/FAIL.
    """
    today = datetime.now().strftime("%Y%m%d")
    backup_name = f"{table_name}_backup_{today}"

    try:
        cursor = conn.cursor()

        # Drop today's backup if it already exists (re-run scenario)
        cursor.execute(
            f"IF OBJECT_ID('dbo.{backup_name}', 'U') IS NOT NULL "
            f"DROP TABLE dbo.{backup_name}"
        )

        # Create backup via SELECT INTO
        cursor.execute(f"SELECT * INTO dbo.{backup_name} FROM {table_name}")

        # Verify row counts match
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        source_count = cursor.fetchone()[0]
        cursor.execute(f"SELECT COUNT(*) FROM dbo.{backup_name}")
        backup_count = cursor.fetchone()[0]

        if source_count != backup_count:
            cursor.close()
            return StepResult(
                "FAIL",
                f"Backup count mismatch: {table_name} has {source_count} rows "
                f"but {backup_name} has {backup_count}",
            )

        # Rotate old backups — find all matching the pattern
        cursor.execute(
            "SELECT name FROM sys.tables "
            "WHERE name LIKE ? "
            "ORDER BY name ASC",
            f"{table_name}_backup_%",
        )
        all_backups = [row[0] for row in cursor.fetchall()]

        # Drop oldest backups if over the limit
        while len(all_backups) > max_backups:
            oldest = all_backups.pop(0)
            cursor.execute(f"DROP TABLE dbo.{oldest}")
            logger.info("Rotated old backup: %s", oldest)

        cursor.close()

        return StepResult(
            "PASS",
            f"Backup created: {backup_name} ({backup_count} rows)",
            [f"Source rows: {source_count}",
             f"Backup rows: {backup_count}",
             f"Total backups: {len(all_backups)}"],
        )
    except Exception as e:
        return StepResult("FAIL", f"Backup failed: {e}")
