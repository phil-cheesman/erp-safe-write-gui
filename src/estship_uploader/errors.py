"""Error handling, SQLSTATE mapping, and credential sanitization."""

import re

_CREDENTIAL_RE = re.compile(
    r"(PWD|PASSWORD|UID|uid|pwd|password)\s*=\s*[^;]*",
    re.IGNORECASE,
)

SQLSTATE_MAP = {
    "08001": "Cannot connect to server. Check host/port and network.",
    "08S01": "Connection lost during operation. Try again.",
    "28000": "Authentication failed. Check credentials.",
    "42000": "SQL syntax error or access denied.",
    "42S02": "Table not found.",
    "HY000": "Driver error: {message}",
    "HYT00": "Query timed out.",
    "HYT01": "Connection timed out.",
    "IM002": "Data source not found. Check DSN configuration.",
}


def sanitize_error_message(msg: str) -> str:
    """Strip PWD/PASSWORD/UID values from error strings."""
    return _CREDENTIAL_RE.sub(r"\1=***", msg)


def handle_odbc_error(error: Exception) -> str:
    """Extract SQLSTATE + message from pyodbc.Error, sanitize, return friendly string."""
    sqlstate = error.args[0] if error.args else "unknown"
    message = error.args[1] if len(error.args) > 1 else str(error)

    message = sanitize_error_message(message)

    template = SQLSTATE_MAP.get(sqlstate, "ODBC error ({sqlstate}): {message}")
    return template.format(sqlstate=sqlstate, message=message)
