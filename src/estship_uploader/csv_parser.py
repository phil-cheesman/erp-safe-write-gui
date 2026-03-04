"""CSV parsing — read, normalize dates, validate structure."""

import csv
from datetime import datetime, timedelta

EXPECTED_HEADERS = ["SO_Number", "Line_Item", "Item_Number", "Est_Ship_Date"]


def _normalize_date(value: str, row_num: int) -> str | None:
    """Accept M/D/YYYY, YYYY-MM-DD, or NULL (to clear). Normalize to YYYY-MM-DD.

    Returns normalized date string, None for NULL, or raises ValueError.
    """
    value = value.strip()

    # Explicit NULL → clear the date
    if value.upper() == "NULL":
        return None

    # Try Excel serial date (5-digit number, e.g. 46107)
    if value.isdigit() and 1 <= len(value) <= 6:
        serial = int(value)
        if serial > 59:
            serial -= 1  # Adjust for Excel's Lotus 1-2-3 leap year bug
        dt = datetime(1899, 12, 31) + timedelta(days=serial)
        return dt.strftime("%Y-%m-%d")

    # Try YYYY-MM-DD first
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Try M/D/YYYY
    try:
        dt = datetime.strptime(value, "%m/%d/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Row {row_num}: invalid date '{value}' — expected M/D/YYYY, YYYY-MM-DD, Excel serial, or NULL"
        )


def _is_blank_row(row: dict) -> bool:
    """Check if all fields in a row are blank or whitespace."""
    return all(not v or not v.strip() for v in row.values())


def parse_csv(filepath: str) -> tuple[list[tuple], int, list[str], list[str]]:
    """Parse a CSV file and return normalized rows.

    Returns:
        (rows, skipped, errors, warnings) where:
        - rows: list of (SO_Number, Line_Item, Item_Number, Est_Ship_Date) tuples
        - skipped: count of blank rows skipped
        - errors: list of error messages (if any errors, rows will be empty)
        - warnings: list of warning messages (informational, non-blocking)
    """
    rows: list[tuple] = []
    skipped = 0
    errors: list[str] = []

    with open(filepath, newline="", encoding="utf-8-sig") as f:
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
            # Skip blank rows
            if _is_blank_row(row):
                skipped += 1
                continue

            # Check required fields
            so = row.get("SO_Number", "")
            line = row.get("Line_Item", "")
            item = row.get("Item_Number", "")
            date_str = row.get("Est_Ship_Date", "")

            if not so or not so.strip():
                errors.append(f"Row {i}: missing SO_Number")
                continue
            if not line or not line.strip():
                errors.append(f"Row {i}: missing Line_Item")
                continue
            if not date_str or not date_str.strip():
                errors.append(f"Row {i}: missing Est_Ship_Date")
                continue

            # Normalize date
            try:
                normalized_date = _normalize_date(date_str, i)
            except ValueError as e:
                errors.append(str(e))
                continue

            # Right-justify SO_Number and Line_Item to match the ERP's
            # left-padded CHAR(10) fields.  Strip Item_Number whitespace.
            rows.append((so.strip().rjust(10), line.strip().rjust(10),
                         item.strip(), normalized_date))

    # Any errors → reject entire file
    if errors:
        return [], skipped, errors, []

    # Warn about NULL dates (clearing existing dates)
    warnings: list[str] = []
    null_rows = [r for r in rows if r[3] is None]
    if null_rows:
        for so, line, item, _ in null_rows:
            warnings.append(
                f"SO {so.strip()} / {line.strip()}: date will be cleared (NULL)")

    # Check for duplicate SO/Line pairs
    seen: dict[tuple[str, str], str | None] = {}  # (SO, Line) -> date
    for so, line, item, date in rows:
        key = (so, line)
        if key in seen:
            if seen[key] == date:
                warnings.append(
                    f"Duplicate SO {so.strip()} / {line.strip()} with same date {date}")
            else:
                errors.append(
                    f"Duplicate SO {so.strip()} / {line.strip()} with conflicting dates "
                    f"({seen[key]} vs {date})")
        else:
            seen[key] = date

    if errors:
        return [], skipped, errors, []

    return rows, skipped, [], warnings
