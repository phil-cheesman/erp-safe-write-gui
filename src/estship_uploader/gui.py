"""Tkinter GUI for EstShip Date Uploader."""

from __future__ import annotations

import logging
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from estship_uploader.config import AppConfig, save_credentials
from estship_uploader.csv_parser import parse_csv
from estship_uploader.formatting import format_step_result

logger = logging.getLogger(__name__)

# States
IDLE = "IDLE"
CSV_LOADED = "CSV_LOADED"
VALIDATED = "VALIDATED"
COMPLETE = "COMPLETE"


class EstShipApp(tk.Tk):
    """Main application window."""

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.state = IDLE
        self.conn = None
        self.rows: list[tuple] = []
        self.csv_path = ""
        self._busy = False
        self._validation_has_fail = False

        self.title("EstShip Date Uploader")
        self.geometry("750x700")
        self.minsize(600, 500)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_widgets()
        self._apply_state()

    # ------------------------------------------------------------------
    # Widget layout
    # ------------------------------------------------------------------

    def _build_widgets(self):
        # Header
        header = ttk.Frame(self, padding=(10, 10, 10, 5))
        header.pack(fill=tk.X)

        ttk.Label(header, text="EstShip Date Uploader",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)

        # Connection frame
        conn_frame = ttk.LabelFrame(self, text="Connection", padding=8)
        conn_frame.pack(fill=tk.X, padx=10, pady=(5, 5))

        # DSN / Database row
        dsn_row = ttk.Frame(conn_frame)
        dsn_row.pack(fill=tk.X, pady=(0, 0))

        ttk.Label(dsn_row, text="DSN:").pack(side=tk.LEFT)
        self._dsn_var = tk.StringVar(value=self.config.dsn)
        ttk.Entry(dsn_row, textvariable=self._dsn_var, width=18).pack(
            side=tk.LEFT, padx=(4, 12))

        ttk.Label(dsn_row, text="Database:").pack(side=tk.LEFT)
        self._database_var = tk.StringVar(value=self.config.database)
        ttk.Entry(dsn_row, textvariable=self._database_var, width=18).pack(
            side=tk.LEFT, padx=(4, 0))

        # Credentials row
        creds_row = ttk.Frame(conn_frame)
        creds_row.pack(fill=tk.X, pady=(4, 0))

        ttk.Label(creds_row, text="Username:").pack(side=tk.LEFT)
        self._user_var = tk.StringVar(value=self.config.username)
        ttk.Entry(creds_row, textvariable=self._user_var, width=18).pack(
            side=tk.LEFT, padx=(4, 12))

        ttk.Label(creds_row, text="Password:").pack(side=tk.LEFT)
        self._pass_var = tk.StringVar(value=self.config.password)
        ttk.Entry(creds_row, textvariable=self._pass_var, width=18,
                  show="*").pack(side=tk.LEFT, padx=(4, 0))

        # Bottom row: save checkbox, test button, status dot
        bottom_row = ttk.Frame(conn_frame)
        bottom_row.pack(fill=tk.X, pady=(6, 0))

        self._save_creds_var = tk.BooleanVar(
            value=bool(self.config.config_path and self.config.username))
        ttk.Checkbutton(bottom_row, text="Save settings",
                        variable=self._save_creds_var).pack(side=tk.LEFT)

        self.btn_test_conn = ttk.Button(bottom_row, text="Test Connection",
                                        command=self._on_test_connection)
        self.btn_test_conn.pack(side=tk.LEFT, padx=(12, 8))

        self._conn_dot = tk.Canvas(bottom_row, width=12, height=12,
                                   highlightthickness=0)
        self._conn_dot.pack(side=tk.LEFT, padx=(0, 5))
        self._draw_dot("gray")

        self._conn_status_var = tk.StringVar(value="Not tested")
        ttk.Label(bottom_row, textvariable=self._conn_status_var).pack(side=tk.LEFT)

        # File frame
        file_frame = ttk.LabelFrame(self, text="CSV File", padding=8)
        file_frame.pack(fill=tk.X, padx=10, pady=5)

        file_row = ttk.Frame(file_frame)
        file_row.pack(fill=tk.X)

        self._file_var = tk.StringVar()
        file_entry = ttk.Entry(file_row, textvariable=self._file_var,
                               state="readonly")
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.btn_browse = ttk.Button(file_row, text="Browse...",
                                     command=self._on_browse)
        self.btn_browse.pack(side=tk.RIGHT)

        self._file_info_var = tk.StringVar()
        ttk.Label(file_frame, textvariable=self._file_info_var).pack(
            anchor=tk.W, pady=(4, 0))

        # Action buttons
        action_frame = ttk.Frame(self, padding=(10, 5))
        action_frame.pack(fill=tk.X)

        self.btn_validate = ttk.Button(action_frame, text="Load && Validate",
                                       command=self._on_validate)
        self.btn_validate.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_upload = ttk.Button(action_frame, text="Upload to ERP",
                                     command=self._on_upload)
        self.btn_upload.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_view_log = ttk.Button(action_frame, text="View Log",
                                       command=self._on_view_log)
        self.btn_view_log.pack(side=tk.LEFT)

        self.btn_how = ttk.Button(action_frame, text="How It Works",
                                  command=self._on_how_it_works)
        self.btn_how.pack(side=tk.RIGHT)

        # Results
        results_frame = ttk.LabelFrame(self, text="Results", padding=8)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.results_text = scrolledtext.ScrolledText(
            results_frame, wrap=tk.WORD, state=tk.DISABLED,
            font=("Consolas", 10), height=15)
        self.results_text.pack(fill=tk.BOTH, expand=True)

        self.results_text.tag_configure("PASS", foreground="#228B22")
        self.results_text.tag_configure("FAIL", foreground="#CC0000")
        self.results_text.tag_configure("WARNING", foreground="#CC8800")
        self.results_text.tag_configure("INFO", foreground="#333333")

        # Status bar
        status_frame = ttk.Frame(self, padding=(10, 2, 10, 5))
        status_frame.pack(fill=tk.X)

        self._status_var = tk.StringVar(value="State: IDLE")
        ttk.Label(status_frame, textvariable=self._status_var,
                  relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X)

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def _set_state(self, new_state: str):
        self.state = new_state
        self._status_var.set(f"State: {new_state}")
        self._apply_state()

    def _apply_state(self):
        if self._busy:
            self.btn_browse.config(state=tk.DISABLED)
            self.btn_test_conn.config(state=tk.DISABLED)
            self.btn_validate.config(state=tk.DISABLED)
            self.btn_upload.config(state=tk.DISABLED)
            return

        self.btn_browse.config(state=tk.NORMAL)
        self.btn_test_conn.config(state=tk.NORMAL)

        if self.state == IDLE:
            self.btn_validate.config(state=tk.DISABLED)
            self.btn_upload.config(state=tk.DISABLED)
        elif self.state == CSV_LOADED:
            self.btn_validate.config(state=tk.NORMAL)
            self.btn_upload.config(state=tk.DISABLED)
        elif self.state == VALIDATED:
            self.btn_validate.config(state=tk.NORMAL)
            upload_ok = not self._validation_has_fail
            self.btn_upload.config(state=tk.NORMAL if upload_ok else tk.DISABLED)
        elif self.state == COMPLETE:
            self.btn_validate.config(state=tk.DISABLED)
            self.btn_upload.config(state=tk.DISABLED)

    def _set_busy(self, busy: bool):
        self._busy = busy
        self._apply_state()

    # ------------------------------------------------------------------
    # Connection dot helper
    # ------------------------------------------------------------------

    def _draw_dot(self, color: str):
        self._conn_dot.delete("all")
        self._conn_dot.create_oval(2, 2, 10, 10, fill=color, outline=color)

    # ------------------------------------------------------------------
    # Results text helpers
    # ------------------------------------------------------------------

    def _clear_results(self):
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete("1.0", tk.END)
        self.results_text.config(state=tk.DISABLED)

    def _append_result(self, text: str, tag: str = "INFO"):
        self.results_text.config(state=tk.NORMAL)
        self.results_text.insert(tk.END, text + "\n", tag)
        self.results_text.see(tk.END)
        self.results_text.config(state=tk.DISABLED)

    def _append_step(self, step):
        """Append a formatted StepResult with appropriate color tag."""
        text = format_step_result(step)
        self._append_result(text, step.status)

    def _show_row_preview(self, rows: list[tuple]):
        """Display all parsed CSV rows in the results window."""
        self._append_result("--- CSV Preview ---", "INFO")
        self._append_result(
            f"{'SO_Number':<12} {'Line_Item':<12} {'Item_Number':<22} {'Est_Ship_Date'}", "INFO")
        self._append_result("-" * 60, "INFO")
        for so, line, item, date in rows:
            date_display = date if date is not None else "NULL"
            self._append_result(
                f"{so:<12} {line:<12} {item:<22} {date_display}", "INFO")
        self._append_result(f"\n{len(rows)} rows total\n", "INFO")

    # ------------------------------------------------------------------
    # Threading helper
    # ------------------------------------------------------------------

    def _run_in_thread(self, target, on_complete):
        self._set_busy(True)

        def wrapper():
            try:
                result = target()
                self.after(0, lambda: on_complete(result))
            except Exception as e:
                self.after(0, lambda: self._show_error(str(e)))
            finally:
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=wrapper, daemon=True).start()

    def _show_error(self, msg: str):
        self._append_result(f"ERROR: {msg}", "FAIL")
        logger.error("GUI error: %s", msg)

    # ------------------------------------------------------------------
    # Credential sync
    # ------------------------------------------------------------------

    def _sync_credentials(self):
        """Push GUI credential/connection fields into config; close conn if they changed."""
        new_user = self._user_var.get()
        new_pass = self._pass_var.get()
        new_dsn = self._dsn_var.get().strip()
        new_db = self._database_var.get().strip()
        changed = (new_user != self.config.username
                   or new_pass != self.config.password
                   or new_dsn != self.config.dsn
                   or new_db != self.config.database)
        self.config.username = new_user
        self.config.password = new_pass
        self.config.dsn = new_dsn
        self.config.database = new_db
        if changed and self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _ensure_connection(self):
        """Establish connection if not already connected. Returns connection or raises."""
        self._sync_credentials()
        if self.conn is not None:
            return self.conn
        from estship_uploader.connection import connect
        self.conn = connect(self.config)
        return self.conn

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_browse(self):
        path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return

        try:
            rows, skipped, errors, warnings = parse_csv(path)
        except Exception as e:
            self._clear_results()
            self._show_error(f"Failed to read CSV: {e}")
            return

        if errors:
            self._clear_results()
            for err in errors:
                self._append_result(f"ERROR: {err}", "FAIL")
            self._file_var.set(path)
            self._file_info_var.set("CSV has errors — see Results")
            return

        # Large upload warning
        if len(rows) > 500:
            if not messagebox.askokcancel(
                    "Large Upload",
                    f"This CSV contains {len(rows)} rows.\n\n"
                    f"Are you sure you want to load this many rows?"):
                return

        self.csv_path = path
        self.rows = rows
        self._file_var.set(path)
        self._file_info_var.set(
            f"{len(rows)} rows loaded, {skipped} blank rows skipped")
        self._clear_results()
        self._show_row_preview(rows)

        if warnings:
            for w in warnings:
                self._append_result(f"WARNING: {w}", "WARNING")

        self._validation_has_fail = False
        self._set_state(CSV_LOADED)

    def _on_test_connection(self):
        self._sync_credentials()
        self._draw_dot("gray")
        self._conn_status_var.set("Testing...")

        def worker():
            from estship_uploader.connection import test_connection
            return test_connection(self.config)

        def on_complete(result):
            success, msg = result
            if success:
                self._draw_dot("#228B22")
                self._conn_status_var.set("Connected")
                if self._save_creds_var.get():
                    try:
                        save_credentials(self.config)
                        self._conn_status_var.set("Connected — settings saved")
                    except Exception as e:
                        logger.error("Failed to save credentials: %s", e)
                        self._conn_status_var.set("Connected (save failed)")
            else:
                self._draw_dot("#CC0000")
                self._conn_status_var.set(f"Error: {msg}")

        self._run_in_thread(worker, on_complete)

    def _on_validate(self):
        self._append_result("\n--- Validation ---", "INFO")
        self._validation_has_fail = False

        def step_callback(step):
            self.after(0, lambda s=step: self._append_step(s))

        def worker():
            conn = self._ensure_connection()
            from estship_uploader.pipeline import run_validation
            return run_validation(conn, self.rows, self.config.database,
                                  on_step=step_callback)

        def on_complete(result):
            self._validation_has_fail = any(
                s.status == "FAIL" for s in result.steps)
            self._upload_count = result.upload_count
            if result.success:
                self._append_result("\nValidation passed.", "PASS")
                self._set_state(VALIDATED)
            else:
                self._append_result("\nValidation FAILED.", "FAIL")
                self._set_state(CSV_LOADED)

        self._run_in_thread(worker, on_complete)

    def _on_upload(self):
        upload_count = getattr(self, '_upload_count', len(self.rows))
        if not messagebox.askokcancel(
                "Confirm Upload",
                f"This will permanently overwrite the Estimated Ship Date "
                f"(idestship) for {upload_count} sales order line items "
                f"in the sostrs table.\n\n"
                f"Any existing estimated ship dates on these line items "
                f"will be replaced with the values from your CSV.\n\n"
                f"This cannot be undone. Continue?"):
            return

        self._append_result("\n--- Upload ---", "INFO")

        def step_callback(step):
            self.after(0, lambda s=step: self._append_step(s))

        def worker():
            from estship_uploader.pipeline import run_upload
            return run_upload(self.conn, upload_count,
                              database=self.config.database,
                              on_step=step_callback)

        def on_complete(result):
            if result.success:
                self._append_result("\nUpload complete.", "PASS")
                self._set_state(COMPLETE)
            else:
                self._append_result("\nUpload FAILED — transaction was rolled back.",
                                    "FAIL")
                self._set_state(CSV_LOADED)

        self._run_in_thread(worker, on_complete)

    def _on_view_log(self):
        log_path = self.config.log_file
        if not os.path.exists(log_path):
            messagebox.showinfo("View Log", f"Log file not found:\n{log_path}")
            return
        try:
            os.startfile(log_path)
        except Exception as e:
            messagebox.showerror("View Log", f"Could not open log file:\n{e}")

    def _on_how_it_works(self):
        win = tk.Toplevel(self)
        win.title("How It Works — EstShip Date Uploader")
        win.geometry("720x620")
        win.minsize(500, 400)

        text = scrolledtext.ScrolledText(win, wrap=tk.WORD,
                                         font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        text.tag_configure("heading", font=("Segoe UI", 12, "bold"))
        text.tag_configure("subheading", font=("Segoe UI", 10, "bold"))
        text.tag_configure("sql", font=("Consolas", 9), foreground="#336699",
                           lmargin1=20, lmargin2=20)
        text.tag_configure("body", font=("Segoe UI", 10))

        def h(t):
            text.insert(tk.END, t + "\n", "heading")

        def sh(t):
            text.insert(tk.END, "\n" + t + "\n", "subheading")

        def b(t):
            text.insert(tk.END, t + "\n", "body")

        def sql(t):
            text.insert(tk.END, t + "\n", "sql")

        h("EstShip Date Uploader")
        b("")
        b("This app bulk-updates the Estimated Ship Date (idestship) on sales")
        b("order line items in the ERP database (sostrs table) using data from")
        b("a CSV file. It replaces a manual multi-step SQL workflow with a")
        b("validated, one-click upload.")
        b("")
        b("Every change runs inside a database transaction. If anything goes")
        b("wrong at any step, the entire batch is rolled back — no partial")
        b("updates, no corrupt data.")

        h("\nPipeline Steps")

        sh("Phase A: Setup & Import")

        b("Step 1 — Create a temporary staging table:")
        sql("    CREATE TABLE dbo.EstShipUpload_Staging (")
        sql("        SO_Number     CHAR(10),")
        sql("        Line_Item     CHAR(10),")
        sql("        Item_Number   CHAR(20),")
        sql("        Est_Ship_Date DATE")
        sql("    )")

        b("\nStep 2 — Import CSV rows via parameterized INSERT (no string")
        b("formatting — prevents SQL injection):")
        sql("    INSERT INTO dbo.EstShipUpload_Staging")
        sql("        (SO_Number, Line_Item, Item_Number, Est_Ship_Date)")
        sql("    VALUES (?, ?, ?, ?)    -- one row per CSV line")

        b("\nStep 3 — Verify row count matches the CSV.")

        sh("Phase B: Validation")

        b("Step 4 — Check every SO/Line pair exists in the ERP:")
        sql("    SELECT s.SO_Number, s.Line_Item,")
        sql("        CASE WHEN EXISTS (")
        sql("            SELECT 1 FROM sostrs t")
        sql("            WHERE t.csono = s.SO_Number")
        sql("              AND t.clineitem = s.Line_Item")
        sql("        ) THEN 1 ELSE 0 END AS found")
        sql("    FROM dbo.EstShipUpload_Staging s")
        b("Missing rows are removed from staging and reported as a warning.")

        b("\nStep 5 — Cross-check item numbers (CSV vs database):")
        sql("    SELECT s.Item_Number AS csv_item, t.citemno AS db_item")
        sql("    FROM dbo.EstShipUpload_Staging s")
        sql("    JOIN sostrs t ON t.csono = s.SO_Number")
        sql("        AND t.clineitem = s.Line_Item")
        b("Mismatches block the upload (likely wrong line item mapping).")

        b("\nStep 6 — Show before/after date comparison.")
        b("Step 7 — Flag date anomalies (past dates, >1 year out, NULLs).")
        b("  Warnings only — these don't block upload.")
        b("Step 8 — Final count: N rows ready for upload.")

        sh("Phase C: Upload (Transaction)")

        b("Step 9 — Execute the UPDATE inside a transaction:")
        sql("    BEGIN TRANSACTION")
        sql("")
        sql("    UPDATE t")
        sql("    SET t.idestship = s.Est_Ship_Date")
        sql("    FROM sostrs t")
        sql("    JOIN dbo.EstShipUpload_Staging s")
        sql("        ON t.csono = s.SO_Number")
        sql("        AND t.clineitem = s.Line_Item")

        b("\nStep 10 — Validate while still in the transaction:")
        b("  - Count mismatches (must be 0)")
        b("  - Verify update count matches staging count")
        b("  - Confirm @@TRANCOUNT = 1 (transaction still open)")

        b("\nStep 11 — COMMIT or ROLLBACK:")
        b("  If all checks pass: COMMIT (changes become permanent)")
        b("  If anything fails: ROLLBACK (zero changes written)")

        b("\nStep 12 — Post-commit verification (row count + date range).")

        sh("Phase D: Cleanup")

        b("Step 13 — Drop the staging table (always runs, even on failure).")

        h("\nSafety Guarantees")
        b("")
        b("- All data inserted via parameterized queries (not string formatting)")
        b("- UPDATE runs inside an explicit transaction")
        b("- Automatic ROLLBACK on any mismatch or error during upload")
        b("- Staging table is always cleaned up, even if the app crashes")
        b("- Credentials are stripped from all error messages and logs")
        b("- Item number cross-check catches wrong SO/Line mappings before")
        b("  any data is written")

        text.config(state=tk.DISABLED)

    def _on_close(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
        self.destroy()
