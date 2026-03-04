"""ODBC connection management — single connection, explicit lifecycle."""

import pyodbc

from estship_uploader.config import AppConfig
from estship_uploader.errors import handle_odbc_error

# Disable ODBC-level pooling — we manage lifecycle explicitly.
pyodbc.pooling = False


def connect(config: AppConfig) -> pyodbc.Connection:
    """Connect to SQL Server using config, run USE database, return connection.

    Connection starts with autocommit=True for setup/validation phases.
    The upload phase will toggle autocommit=False explicitly.
    """
    conn_string = config.build_connection_string()

    try:
        conn = pyodbc.connect(conn_string, autocommit=True, timeout=config.query_timeout)
    except pyodbc.Error as exc:
        raise ConnectionError(handle_odbc_error(exc)) from exc

    try:
        conn.timeout = config.query_timeout
    except pyodbc.Error:
        pass  # Some drivers don't support this

    # Switch to target database
    try:
        conn.execute(f"USE {config.database}")
    except pyodbc.Error as exc:
        conn.close()
        raise ConnectionError(handle_odbc_error(exc)) from exc

    return conn


def test_connection(config: AppConfig) -> tuple[bool, str]:
    """Safe connection probe — never raises, returns (success, message)."""
    try:
        conn = connect(config)
        conn.execute("SELECT 1")
        conn.close()
        return True, f"Connected to {config.dsn or 'database'} ({config.database})"
    except Exception as e:
        return False, str(e)
