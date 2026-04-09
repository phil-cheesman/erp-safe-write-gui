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

- **Pipeline pattern**: each tab has its own `*_pipeline.py` → `*_validators.py` → `*_updater.py`
- **State machine**: IDLE → CSV_LOADED → VALIDATED → COMPLETE
- **Transaction safety**: UPDATE runs in explicit transaction, rolls back on any mismatch
- **Staging tables**: Temp staging tables created/dropped each run (e.g. `dbo.EstShipUpload_Staging`, `dbo.MfgLTUpload_Staging`, `dbo.ReordPtUpload_Staging`, `dbo.ReordQtyUpload_Staging`)

## DB Targets

- **Est Ship Date**: `sostrs` — `csono` (CHAR10), `clineitem` (CHAR10), `citemno` (CHAR20), `idestship` (DATE)
- **Item Class**: `iclmas` — `citemno` (CHAR20), `cbuyer` (CHAR10)
- **Mfg Lead Time**: `iciwhs` — `citemno` (CHAR20), `cwarehouse` (CHAR10), `nmfgltime` (INT). Updates fan out to ALL warehouses per part number. Full-table backup before each upload.
- **Reorder Point**: `iciwhs` — `citemno` (CHAR20), `cwarehouse` (CHAR10), `nreordpt` (NUMERIC16). Same fan-out + backup pattern as Mfg Lead Time.
- **Reorder Qty**: `iciwhs` — `citemno` (CHAR20), `cwarehouse` (CHAR10), `nreordqty` (NUMERIC16). Same fan-out + backup pattern as Mfg Lead Time.
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