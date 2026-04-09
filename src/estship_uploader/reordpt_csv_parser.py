"""CSV parsing for reorder point (nreordpt) uploads."""

import csv

EXPECTED_HEADERS = ["citemno", "nreordpt"]


def _is_blank_row(row: dict) -> bool:
    """Check if all fields in a row are blank or whitespace."""
    return all(not v or not v.strip() for v in row.values())


def parse_reordpt_csv(filepath: str) -> tuple[list[tuple], int, list[str], list[str]]:
    """Parse a citemno/nreordpt CSV file.

    Returns:
        (rows, skipped, errors, warnings) where:
        - rows: list of (citemno, nreordpt) tuples.  nreordpt is int or None.
        - skipped: count of blank rows skipped
        - errors: list of error messages (if any errors, rows will be empty)
        - warnings: list of warning messages (informational, non-blocking)
    """
    rows: list[tuple] = []
    skipped = 0
    errors: list[str] = []

    # Detect encoding
    try:
        with open(filepath, newline="", encoding="utf-8-sig") as f:
            f.read()
    except UnicodeDecodeError:
        encoding = "cp1252"
    else:
        encoding = "utf-8-sig"

    with open(filepath, newline="", encoding=encoding) as f:
        reader = csv.DictReader(f)

        # Validate headers
        if reader.fieldnames is None:
            return [], 0, ["CSV file is empty or has no header row"], []

        actual = [h.strip() for h in reader.fieldnames]
        if actual != EXPECTED_HEADERS:
            return [], 0, [
                f"Invalid headers: expected {EXPECTED_HEADERS}, got {actual}"
            ], []

        for i, row in enumerate(reader, start=2):  # row 1 is header
            if _is_blank_row(row):
                skipped += 1
                continue

            citemno = (row.get("citemno", "") or "").strip()
            val_str = (row.get("nreordpt", "") or "").strip()

            if not citemno:
                errors.append(f"Row {i}: missing citemno")
                continue

            # Parse reorder point — blank means None (clear/set to NULL)
            if not val_str:
                val = None
            else:
                try:
                    val = int(val_str)
                except ValueError:
                    errors.append(
                        f"Row {i}: invalid nreordpt '{val_str}' — must be a whole number")
                    continue

                if val < 0:
                    errors.append(
                        f"Row {i}: nreordpt cannot be negative ({val})")
                    continue

            rows.append((citemno, val))

    # Any errors → reject entire file
    if errors:
        return [], skipped, errors, []

    # Build warnings
    warnings: list[str] = []

    # Warn about clearing values
    none_count = sum(1 for _, v in rows if v is None)
    if none_count:
        warnings.append(
            f"{none_count} item(s) will have nreordpt cleared (set to NULL)")

    # Warn about zero values
    zero_count = sum(1 for _, v in rows if v == 0)
    if zero_count:
        warnings.append(f"{zero_count} item(s) have nreordpt set to 0")

    # Warn about very large values (>1000)
    large = [(it, v) for it, v in rows if v is not None and v > 1000]
    if large:
        warnings.append(
            f"{len(large)} item(s) have nreordpt > 1,000")

    # Check for duplicate citemno
    seen: dict[str, int | None] = {}
    for citemno, val in rows:
        if citemno in seen:
            if seen[citemno] == val:
                warnings.append(
                    f"Duplicate citemno '{citemno}' with same value {val}")
            else:
                errors.append(
                    f"Duplicate citemno '{citemno}' with conflicting values "
                    f"({seen[citemno]} vs {val})")
        else:
            seen[citemno] = val

    if errors:
        return [], skipped, errors, []

    return rows, skipped, [], warnings
