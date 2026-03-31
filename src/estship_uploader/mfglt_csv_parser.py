"""CSV parsing for manufacturing lead time (nmfgltime) uploads."""

import csv

EXPECTED_HEADERS = ["citemno", "nmfgltime"]


def _is_blank_row(row: dict) -> bool:
    """Check if all fields in a row are blank or whitespace."""
    return all(not v or not v.strip() for v in row.values())


def parse_mfglt_csv(filepath: str) -> tuple[list[tuple], int, list[str], list[str]]:
    """Parse a citemno/nmfgltime CSV file.

    Returns:
        (rows, skipped, errors, warnings) where:
        - rows: list of (citemno, nmfgltime) tuples.  nmfgltime is int or None.
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
            lt_str = (row.get("nmfgltime", "") or "").strip()

            if not citemno:
                errors.append(f"Row {i}: missing citemno")
                continue

            # Parse lead time — blank means None (clear/set to 0)
            if not lt_str:
                lt_value = None
            else:
                try:
                    lt_value = int(lt_str)
                except ValueError:
                    errors.append(
                        f"Row {i}: invalid nmfgltime '{lt_str}' — must be a whole number")
                    continue

                if lt_value < 0:
                    errors.append(
                        f"Row {i}: nmfgltime cannot be negative ({lt_value})")
                    continue

            rows.append((citemno, lt_value))

    # Any errors → reject entire file
    if errors:
        return [], skipped, errors, []

    # Build warnings
    warnings: list[str] = []

    # Warn about clearing lead times
    none_count = sum(1 for _, lt in rows if lt is None)
    if none_count:
        warnings.append(
            f"{none_count} item(s) will have nmfgltime cleared (set to NULL)")

    # Warn about zero values
    zero_count = sum(1 for _, lt in rows if lt == 0)
    if zero_count:
        warnings.append(f"{zero_count} item(s) have nmfgltime set to 0")

    # Warn about very large values (>365 days)
    large = [(it, lt) for it, lt in rows if lt is not None and lt > 365]
    if large:
        warnings.append(
            f"{len(large)} item(s) have nmfgltime > 365 days")

    # Check for duplicate citemno
    seen: dict[str, int | None] = {}
    for citemno, lt_value in rows:
        if citemno in seen:
            if seen[citemno] == lt_value:
                warnings.append(
                    f"Duplicate citemno '{citemno}' with same value {lt_value}")
            else:
                errors.append(
                    f"Duplicate citemno '{citemno}' with conflicting values "
                    f"({seen[citemno]} vs {lt_value})")
        else:
            seen[citemno] = lt_value

    if errors:
        return [], skipped, errors, []

    return rows, skipped, [], warnings
