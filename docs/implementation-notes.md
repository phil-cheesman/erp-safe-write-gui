# Implementation Notes

## What Was Built

All Phase 1 (backend core) modules and tests:

### Source Modules (10 files)

| File | Purpose |
|------|---------|
| `models.py` | `StepResult` and `PipelineResult` dataclasses |
| `errors.py` | Credential sanitization (`_CREDENTIAL_RE`), SQLSTATE mapping, `handle_odbc_error()` |
| `config.py` | `AppConfig` dataclass, INI loading, env var overlay (`ESTSHIP_DB_*`) |
| `formatting.py` | `truncate_value()`, `format_step_result()`, `format_upload_summary()` |
| `csv_parser.py` | CSV reading with `M/D/YYYY`, `YYYY-MM-DD`, Excel serial date, and `NULL` support, blank row skipping, duplicate detection, validation |
| `connection.py` | `pyodbc.pooling = False`, `connect()`, `test_connection()` |
| `validators.py` | Steps 1-8: staging table, import, verify, SO/Line check, item cross-check, before/after date comparison, date anomalies, summary |
| `updater.py` | Steps 9-13: UPDATE in transaction, in-transaction validation, commit/rollback, post-commit verify, cleanup |
| `pipeline.py` | `run_validation()` and `run_upload()` orchestration |
| `main.py` + `__main__.py` | CLI entry point with `--file`, `--config`, `--validate-only`, `--test-connection` |

### Test Files (5 files, 36 tests)

| File | Tests | Coverage |
|------|-------|----------|
| `conftest.py` | — | MockRow, mock_config, mock_cursor, mock_connection, 10 CSV fixtures |
| `test_csv_parser.py` | 10 | Valid CSV, blank rows, bad dates, wrong headers, ISO dates, missing fields, header-only, Excel serial dates, NULL date, duplicate same/diff dates |
| `test_validators.py` | 12 | Pass + fail for all 8 steps; date anomalies returns WARNING not FAIL |
| `test_updater.py` | 9 | execute_update success/error, validate pass/mismatch/count, commit/rollback, cleanup success/error |
| `test_pipeline.py` | 6 | All-pass (8 steps), halt-on-error, warning pass-through, upload success, rollback on mismatch, cleanup on exception |

## Deviations from Plan

1. **`models.py` added** — The plan had `StepResult`/`PipelineResult` defined in `pipeline.py`, but `validators.py` and `updater.py` both import `StepResult` while `pipeline.py` imports `validators`/`updater`. Extracted shared dataclasses to `models.py` to break the circular import. This is the only structural deviation.

2. **`errors.py` UID sanitization** — Added `UID=` to the credential regex alongside `PWD=`/`PASSWORD=`, matching the spec's section 9 requirement ("Any value after `UID=` or `PWD=`").

## Verification Results

- `pytest` — **36/36 passed** (all pyodbc mocked, no DB needed)
- `python -m estship_uploader --file sample_data/example_upload.csv --validate-only` — CSV parsed (3 rows, 0 skipped), failed at DB connect (expected: no DSN configured)
- `python -m estship_uploader --test-connection` — "Data source not found" (expected)
- `sanitize_error_message("DSN=X;PWD=secret123;UID=admin;")` → `"DSN=X;PWD=***;UID=***;"` (correct)

---

## Session 2: GUI, Main Wiring, and Build Script

### What Was Built

| File | Purpose |
|------|---------|
| `gui.py` | Tkinter GUI — `EstShipApp(tk.Tk)` with full widget layout, state machine, threaded operations |
| `scripts/build_exe.py` | PyInstaller build script (`--onefile --console`) |

### Files Modified

| File | Change |
|------|--------|
| `pipeline.py` | Added `on_step` callback parameter to `run_validation()` and `run_upload()` for live GUI updates |
| `main.py` | Launches GUI when no `--file` arg is given; CLI flags still work |

### GUI Architecture

**Layout (top to bottom):**
- Header: app title, connection info (DSN/database), status dot + label, Test Connection button
- CSV File: readonly entry + Browse button, info label (row count / skip count)
- Action buttons: Load & Validate, Upload to ERP, View Log
- Results: `ScrolledText` (readonly) with color tags — PASS (green), FAIL (red), WARNING (amber)
- Status bar: current state label

**State machine:** `IDLE → CSV_LOADED → VALIDATED → COMPLETE`

| State | Browse | Test Conn | Validate | Upload |
|-------|--------|-----------|----------|--------|
| IDLE | on | on | off | off |
| CSV_LOADED | on | on | on | off |
| VALIDATED | on | on | on | on* |
| COMPLETE | on | on | off | off |

*Upload only enabled if validation had no FAIL steps.

**Threading:** All DB operations (test connection, validate, upload) run in daemon threads. Widget updates happen on the main thread via `self.after(0, callback)`. A `_busy` flag disables all action buttons during operations to prevent double-clicks.

**Connection management:** `self.conn` established on first validate/test, reused for upload (same connection holds the staging table), closed on window close.

### Pipeline `on_step` Callback

Added a shared `_emit(result, step, on_step)` helper that appends the step to the result and calls the callback if provided. Both `run_validation()` and `run_upload()` accept an optional `on_step=None` parameter. Fully backwards-compatible — CLI and all existing tests unaffected.

### Build Script

`scripts/build_exe.py` runs PyInstaller via subprocess:
- `--onefile --console --name=EstShipUploader`
- Bundles `config/config.example.ini` via `--add-data`
- Uses `--icon=assets/icon.ico` if present
- Console mode kept for initial rollout debugging

### Deviations from Plan

1. **`--console` instead of `--windowed`** — The spec (section 13) says `--windowed`, but the session 2 plan specified `--console` for debugging during initial rollout. Used `--console` as planned; can switch to `--windowed` once stable.

2. **build_exe.py uses `subprocess.run`** — The spec shows `PyInstaller.__main__.run()` but we use `subprocess.run([sys.executable, "-m", "PyInstaller", ...])` which is more robust for path resolution when running from different working directories.

### Verification Results

- `pytest` — **40/40 passed** (no regressions from `on_step` change)
- GUI launches with `python -m estship_uploader` (no `--file` flag)
- CLI still works: `python -m estship_uploader --file x.csv`

---

## Session 3: GUI Credentials Input

### What Was Built

Added credentials entry fields to the GUI so end users can type username/password directly instead of editing `config.ini`.

### Files Modified

| File | Change |
|------|--------|
| `config.py` | Added `config_path` field to `AppConfig`; `load_config()` tracks which INI was loaded; new `save_credentials(config)` function |
| `gui.py` | Replaced flat header connection area with "Connection" `LabelFrame` containing DSN info, username/password entries, "Save credentials" checkbox, Test Connection button + status dot |

### GUI Changes

**New Connection frame layout:**
```
┌─ Connection ────────────────────────────────────────┐
│  DSN: MY_DSN  |  Database: my_database               │
│                                                      │
│  Username: [____________]  Password: [____________]  │
│                                                      │
│  ☐ Save credentials     [Test Connection]  ● Status  │
└──────────────────────────────────────────────────────┘
```

- Username/password `ttk.Entry` fields pre-populated from config
- Password field uses `show="*"`
- `_sync_credentials()` pushes GUI values into `self.config` before any connection attempt; closes existing `self.conn` if credentials changed so next operation reconnects
- `_ensure_connection()` calls `_sync_credentials()` automatically (covers Validate and Upload)
- On successful Test Connection with "Save credentials" checked, calls `save_credentials()` and shows confirmation in status label

### Verification Results

- `pytest` — **36/36 passed** (no test changes needed)
- GUI launches with credentials fields visible and pre-populated
- Test Connection works with entered credentials
- Save credentials persists username/password to `config.ini`

---

## Session 4: Validation Safeguards, NULL Dates, Excel Serial Dates

### What Was Built

Three validation safeguards, NULL date support for clearing existing dates, and Excel serial date conversion.

### Files Modified

| File | Change |
|------|--------|
| `csv_parser.py` | Returns 4 values `(rows, skipped, errors, warnings)`; duplicate SO/Line detection (same date → warning, different dates → error); `NULL` keyword clears dates; Excel serial date (5-digit number) auto-conversion; Lotus 1-2-3 leap year bug adjustment |
| `validators.py` | New `check_date_changes(conn)` step — compares current vs new dates, shows `[>>]` prefix for rows that will change and `(no change)` for unchanged; datetime-to-date stripping for clean display |
| `pipeline.py` | Wired `check_date_changes()` as Step 6 between item cross-check and date anomalies (informational, never halts); step numbers shifted to 1-8 validation, 9-13 upload |
| `updater.py` | `post_commit_verify()` strips time portion from datetime values for date-only display |
| `gui.py` | `_on_browse` unpacks 4 values, shows duplicate warnings (yellow), row count warning dialog for >500 rows; preview displays `NULL` for cleared dates; button renamed to "Upload to ERP" |
| `main.py` | Updated `parse_csv` caller to unpack 4 values and print warnings |
| `conftest.py` | Added 3 fixtures: `sample_csv_excel_serial`, `sample_csv_null_date`, `sample_csv_duplicate_same_date`, `sample_csv_duplicate_diff_dates` |
| `test_csv_parser.py` | Updated all existing tests to unpack 4 values; added 3 tests: Excel serial dates, NULL date, duplicate same date, duplicate different dates |
| `test_pipeline.py` | Updated step counts (7→8) and added `check_date_changes` mock to validation tests |

### Date Input Formats Supported

| Format | Example | Notes |
|--------|---------|-------|
| `M/D/YYYY` | `3/6/2026` | US date format |
| `YYYY-MM-DD` | `2026-03-06` | ISO format |
| Excel serial | `46112` | 5-6 digit number, auto-detected |
| `NULL` | `NULL` | Clears existing date (case-insensitive) |

### Duplicate SO/Line Detection

- **Same SO/Line, same date** → warning (informational, probably harmless copy-paste)
- **Same SO/Line, different dates** → error (ambiguous, CSV rejected)

### Verification Results

- `pytest` — **40/40 passed**
- Normal CSV → before/after comparison shows current → new dates with `[>>]` markers
- NULL date → warning shown on load, date anomaly flagged during validation, upload clears the date
- Excel serial date → auto-converted to `YYYY-MM-DD`
- Duplicate SO/Line with same date → warning, proceeds
- Duplicate SO/Line with different dates → error, rejected

---

## What's Left to Do

### Before First Real Use

- [ ] **Manual testing against test database** — Test Connection, Validate, Upload with real data
- [ ] **Test on target machine** — Verify ODBC DSN is configured, run the app
- [x] **Credentials entry in GUI** — Users can enter username/password directly and optionally save to `config.ini`

### Before Distribution (Phase 3 — Polish & Package)

- [ ] **Build the .exe** — `python scripts/build_exe.py` → `dist/EstShipUploader.exe`
- [ ] **Test .exe on clean Windows machine** — No Python installed, verify it runs
- [ ] **Switch to `--windowed`** — Remove console window once confident in stability
- [ ] **Write user-facing README** — Setup instructions, first-run guide, screenshots
- [ ] **App icon** — Create `assets/icon.ico` if desired

### Nice-to-Have (Not Blocking)

- [ ] GUI tests (would need `tkinter` mocking — low priority)
- [ ] Progress indicator for long-running operations (useful for 500+ row CSVs)
- [ ] Error message polish for non-technical users

---

## Session 5: Mfg Lead Time — Multi-Warehouse Update

### What Was Built

Extended the Mfg Lead Time uploader to update `nmfgltime` across **all warehouses** in `iciwhs` that hold each part number, instead of only the MAIN warehouse. Added a pre-flight scope computation step, tightened the in-transaction row-count verification, and updated the value-change display to surface warehouse-to-warehouse drift.

### Live Data Context (verified via ODBC MCP against `sqlvam`)

- `iciwhs` has 8 distinct warehouses: 2377, CA, HOLD, HUDSON, INTRANSIT, MAIN, NC, TX
- Most items live in 2 warehouses (MAIN + HUDSON); some span up to 8
- 124 items exist in non-MAIN warehouses but have no MAIN row — previously rejected, now accepted
- Some items have drifted lead times across warehouses (e.g., MAIN=10, HUDSON/CA/NC/TX=0)

### Files Modified

| File | Change |
|------|--------|
| `models.py` | Added `expected_rows: int = 0` field to `PipelineResult` |
| `mfglt_validators.py` | `check_items_exist` no longer filters by warehouse (any warehouse passes). `check_value_changes` groups by `(item, current_value)` with warehouse count — drift surfaces as separate groups. New `compute_update_scope()` returns `(StepResult, expected_rows, warehouses)` |
| `mfglt_updater.py` | `execute_update` returns `(StepResult, rows_affected)` — no warehouse filter on the UPDATE. `validate_in_transaction` takes both `expected_rows` and `actual_rows`, verifies exact match, plus a re-counted scope_count for defense in depth. `post_commit_verify` covers all warehouses |
| `mfglt_pipeline.py` | `run_validation` calls `compute_update_scope` after item-exist check, stashes `expected_rows` on result. `run_upload` threads `expected_rows` + `actual_rows` into the validator |
| `tabbed_gui.py` | `MfgLTTab` caches `_expected_rows` from validation, passes it to `run_upload`. Updated confirmation prompt and "How It Works" modal to describe all-warehouse behavior |

### New Test File

| File | Tests | Coverage |
|------|-------|----------|
| `test_mfglt_updater.py` | 10 | `execute_update` tuple return + no warehouse filter, `validate_in_transaction` pass/actual-vs-expected mismatch/mismatch count/scope drift/lost transaction/no warehouse filter, `post_commit_verify` no warehouse filter |

### Modified Tests

| File | Changes |
|------|---------|
| `test_mfglt_validators.py` | Updated `check_items_exist` assertions (no MAIN filter). Added `test_item_in_non_main_warehouse_passes`, `TestComputeUpdateScope` (4 cases), `test_warehouse_drift_shown_as_separate_groups` |
| `test_mfglt_pipeline.py` | Updated mock shapes for 4-element `check_value_changes` rows and warehouse list for `compute_update_scope`. Added `test_rollback_when_actual_rows_differs_from_expected` |

### Verification Results

- `pytest` — **122/122 passed** (44 mfglt + backup, 78 unrelated)
- Read-only ODBC sanity check against `sqlvam`: new SQL compiles, sample CTE with multi-warehouse parts returned correct fan-out (3 items × varying warehouse counts = 8 expected rows), item with no MAIN row accepted

---

## Session 5b: Config Path Fix for .exe Distribution

### What Was Fixed

`config.py` used relative paths (`config/config.ini`) which resolve against the CWD. The batch file masks this by doing `cd /d "%~dp0"`, but double-clicking the exe directly uses the exe's directory as CWD, which doesn't contain `config/`. Settings saved to the wrong location and were lost on restart.

### Files Modified

| File | Change |
|------|--------|
| `config.py` | Added `_app_dir()` helper: returns `Path(sys.executable).parent` when frozen (PyInstaller), `Path.cwd()` otherwise. Both `load_config` and `save_credentials` resolve config paths relative to `_app_dir()` |

### Distribution Impact

The exe now requires `config/config.ini` next to it (`dist/config/config.ini`). "Save settings" writes to that location regardless of how the exe is launched.
