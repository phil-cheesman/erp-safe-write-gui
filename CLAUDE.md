# EstShip Uploader

Standalone Tkinter GUI app that automates daily estimated ship date uploads to SQL Server ERP systems via ODBC. Replaces manual DBeaver workflow with validated, one-click upload.

## Tech Stack

- **Python 3.12+**, **Tkinter** (GUI), **pyodbc** (DB), **PyInstaller** (packaging)
- All other deps are stdlib: csv, configparser, logging

## Project Structure

- `src/estship_uploader/` — application source
- `tests/` — pytest unit tests (mock pyodbc, no DB needed)
- `config/` — INI config files (`config.ini` is gitignored, `config.example.ini` is committed)
- `scripts/` — build scripts (PyInstaller)
- `sample_data/` — example CSV files for testing
- `docs/` — spec and documentation

## Key Architecture

- **Pipeline pattern**: `pipeline.py` orchestrates steps from `validators.py` and `updater.py`
- **State machine**: IDLE → CSV_LOADED → VALIDATED → COMPLETE
- **Transaction safety**: UPDATE runs in explicit transaction, rolls back on any mismatch
- **Staging table**: Temp `dbo.EstShipUpload_Staging` created/dropped each run

## DB Target

- Target table: configurable (default: `sostrs`)
- Fields: `csono` (CHAR10), `clineitem` (CHAR10), `citemno` (CHAR20), `idestship` (DATE)
- Connection via ODBC DSN (configured in `config/config.ini`)

## Commands

```bash
# Run tests
pytest

# Run app in dev
python -m estship_uploader

# Build exe
python scripts/build_exe.py
```

## Conventions

- Parameterized queries only (no string formatting for SQL)
- Sanitize credentials from all error messages and logs
- Staging table always cleaned up in finally blocks
- Warnings (e.g. past dates) don't block upload; errors do

## Commits

- Never use "Co-Authored-By" in any commit message