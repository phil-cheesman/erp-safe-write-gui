"""CSV parsing for item class (cbuyer) uploads."""

import csv

EXPECTED_HEADERS = ["citemno", "cbuyer"]

# Approved values for new assignments.  Non-approved values generate a WARNING
# (not an error) so legacy values already in the DB are not blocked.
APPROVED_CBUYER = {"A", "B", "C", "D", "MTO", "RESTRICTED", "C1", "C2", "RES"}


def _is_blank_row(row: dict) -> bool:
    """Check if all fields in a row are blank or whitespace."""
    return all(not v or not v.strip() for v in row.values())


def parse_itemclass_csv(filepath: str) -> tuple[list[tuple], int, list[str], list[str]]:
    """Parse a citemno/cbuyer CSV file.

    Returns:
        (rows, skipped, errors, warnings) where:
        - rows: list of (citemno, cbuyer) tuples.  Blank cbuyer → empty string.
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
            cbuyer = (row.get("cbuyer", "") or "").strip().upper()

            if not citemno:
                errors.append(f"Row {i}: missing citemno")
                continue

            # Blank cbuyer is valid — means "set to empty string" (wipe)
            rows.append((citemno, cbuyer))

    # Any errors → reject entire file
    if errors:
        return [], skipped, errors, []

    # Build warnings
    warnings: list[str] = []

    # Warn about non-approved values
    non_approved = set()
    for citemno, cbuyer in rows:
        if cbuyer and cbuyer not in APPROVED_CBUYER:
            non_approved.add(cbuyer)
    if non_approved:
        for val in sorted(non_approved):
            count = sum(1 for _, cb in rows if cb == val)
            warnings.append(
                f"Non-approved cbuyer value '{val}' used on {count} item(s)")

    # Warn about blank cbuyer (wipe)
    blank_count = sum(1 for _, cb in rows if not cb)
    if blank_count:
        warnings.append(
            f"{blank_count} item(s) will have cbuyer cleared (set to blank)")

    # Check for duplicate citemno
    seen: dict[str, str] = {}  # citemno -> cbuyer
    for citemno, cbuyer in rows:
        if citemno in seen:
            if seen[citemno] == cbuyer:
                warnings.append(
                    f"Duplicate citemno '{citemno}' with same value '{cbuyer}'")
            else:
                errors.append(
                    f"Duplicate citemno '{citemno}' with conflicting values "
                    f"('{seen[citemno]}' vs '{cbuyer}')")
        else:
            seen[citemno] = cbuyer

    if errors:
        return [], skipped, errors, []

    return rows, skipped, [], warnings
