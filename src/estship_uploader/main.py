"""CLI entry point — logging setup, argparse, pipeline orchestration."""

from __future__ import annotations

import argparse
import logging
import sys

from estship_uploader.config import AppConfig, load_config
from estship_uploader.csv_parser import parse_csv
from estship_uploader.formatting import format_step_result, format_upload_summary


def setup_logging(config: AppConfig) -> None:
    """Configure file + console logging."""
    level = getattr(logging, config.log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # File handler
    try:
        fh = logging.FileHandler(config.log_file, mode="a", encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(formatter)
        root.addHandler(fh)
    except OSError:
        logging.warning("Could not open log file: %s", config.log_file)


def main() -> None:
    """Parse args and run the appropriate pipeline."""
    parser = argparse.ArgumentParser(
        prog="estship-uploader",
        description="Estimated Ship Date bulk uploader for SQL Server ERP systems",
    )
    parser.add_argument("--file", "-f", help="Path to CSV file")
    parser.add_argument("--config", "-c", help="Path to config INI file")
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Run validation only (do not upload)",
    )
    parser.add_argument(
        "--test-connection", action="store_true",
        help="Test database connection and exit",
    )
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)
    setup_logging(config)

    logger = logging.getLogger(__name__)
    logger.info("--- New upload session ---")
    logger.info("Config: DSN=%s, database=%s", config.dsn, config.database)

    # Test connection mode
    if args.test_connection:
        from estship_uploader.connection import test_connection
        success, msg = test_connection(config)
        print(msg)
        sys.exit(0 if success else 1)

    # No --file → launch GUI
    if not args.file:
        from estship_uploader.gui import EstShipApp
        app = EstShipApp(config)
        app.mainloop()
        sys.exit(0)

    # Parse CSV
    logger.info("Loading CSV: %s", args.file)
    rows, skipped, errors, warnings = parse_csv(args.file)

    if errors:
        logger.error("CSV parsing failed:")
        for err in errors:
            logger.error("  %s", err)
            print(f"ERROR: {err}")
        sys.exit(1)

    for w in warnings:
        logger.warning("  %s", w)
        print(f"WARNING: {w}")

    logger.info("CSV loaded: %d rows, %d blank rows skipped", len(rows), skipped)
    print(f"CSV loaded: {len(rows)} rows, {skipped} blank rows skipped")

    if not rows:
        logger.warning("No data rows in CSV")
        print("No data rows found in CSV.")
        sys.exit(0)

    # Connect to database
    from estship_uploader.connection import connect
    try:
        conn = connect(config)
    except ConnectionError as e:
        logger.error("Connection failed: %s", e)
        print(f"Connection failed: {e}")
        sys.exit(1)

    logger.info("Connected to %s (%s)", config.dsn, config.database)

    # Run validation
    from estship_uploader.pipeline import run_validation, run_upload

    print("\n--- Validation ---")
    val_result = run_validation(conn, rows, config.database)
    for step in val_result.steps:
        msg = format_step_result(step)
        print(msg)
        log_level = logging.WARNING if step.status == "WARNING" else logging.INFO
        if step.status == "FAIL":
            log_level = logging.ERROR
        logger.log(log_level, msg.replace("\n", " | "))

    if not val_result.success:
        print("\nValidation FAILED — upload aborted.")
        conn.close()
        sys.exit(1)

    if args.validate_only:
        print("\nValidation passed. (--validate-only: skipping upload)")
        # Cleanup staging table since we won't upload
        from estship_uploader.updater import cleanup_staging
        cleanup_staging(conn)
        conn.close()
        sys.exit(0)

    # Run upload
    print("\n--- Upload ---")
    upload_result = run_upload(conn, val_result.upload_count, database=config.database)
    for step in upload_result.steps:
        msg = format_step_result(step)
        print(msg)
        log_level = logging.WARNING if step.status == "WARNING" else logging.INFO
        if step.status == "FAIL":
            log_level = logging.ERROR
        logger.log(log_level, msg.replace("\n", " | "))

    if upload_result.success:
        print("\nUpload complete.")
        logger.info("Upload complete.")
    else:
        print("\nUpload FAILED — transaction was rolled back.")
        logger.error("Upload failed — transaction was rolled back.")

    conn.close()
    sys.exit(0 if upload_result.success else 1)
