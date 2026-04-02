"""Tabbed GUI shell — hosts EstShip, Item Class, and Mfg Lead Time tabs."""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from estship_uploader.config import AppConfig, save_credentials
from estship_uploader.formatting import format_step_result

logger = logging.getLogger(__name__)

# States (shared across tabs)
IDLE = "IDLE"
CSV_LOADED = "CSV_LOADED"
VALIDATED = "VALIDATED"
COMPLETE = "COMPLETE"


class TabbedApp(tk.Tk):
    """Main application window with tabbed interface."""

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.conn = None
        self._busy = False

        self.title("ERP Uploader")
        self.geometry("800x750")
        self.minsize(650, 550)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_widgets()

    # ------------------------------------------------------------------
    # Widget layout
    # ------------------------------------------------------------------

    def _build_widgets(self):
        # Header
        header = ttk.Frame(self, padding=(10, 10, 10, 5))
        header.pack(fill=tk.X)

        ttk.Label(header, text="ERP Uploader",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)

        # Connection frame (shared across all tabs)
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

        # Notebook (tabs)
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create tabs
        self._estship_tab = EstShipTab(self._notebook, self)
        self._itemclass_tab = ItemClassTab(self._notebook, self)
        self._mfglt_tab = MfgLTTab(self._notebook, self)

        self._notebook.add(self._estship_tab, text="EstShip Dates")
        self._notebook.add(self._itemclass_tab, text="Item Class")
        self._notebook.add(self._mfglt_tab, text="Mfg Lead Time")

    # ------------------------------------------------------------------
    # Connection dot helper
    # ------------------------------------------------------------------

    def _draw_dot(self, color: str):
        self._conn_dot.delete("all")
        self._conn_dot.create_oval(2, 2, 10, 10, fill=color, outline=color)

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
        """Establish connection if not already connected."""
        self._sync_credentials()
        if self.conn is not None:
            return self.conn
        from estship_uploader.connection import connect
        self.conn = connect(self.config)
        return self.conn

    # ------------------------------------------------------------------
    # Busy state (connection frame)
    # ------------------------------------------------------------------

    def _set_conn_busy(self, busy: bool):
        """Disable/enable connection frame controls when any tab is busy."""
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.btn_test_conn.config(state=state)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

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

    def _run_in_thread(self, target, on_complete):
        self._set_conn_busy(True)

        def wrapper():
            try:
                result = target()
                self.after(0, lambda: on_complete(result))
            except Exception as e:
                self.after(0, lambda: self._show_error(str(e)))
            finally:
                self.after(0, lambda: self._set_conn_busy(False))

        threading.Thread(target=wrapper, daemon=True).start()

    def _show_error(self, msg: str):
        logger.error("App error: %s", msg)

    def _on_close(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
        self.destroy()


# ======================================================================
# Base tab class — shared logic for all upload tabs
# ======================================================================


class BaseUploadTab(ttk.Frame):
    """Shared tab structure: CSV file picker, action buttons, results pane, state machine."""

    def __init__(self, parent, app: TabbedApp):
        super().__init__(parent, padding=5)
        self.app = app
        self.state = IDLE
        self.rows: list[tuple] = []
        self.csv_path = ""
        self._busy = False
        self._validation_has_fail = False
        self._upload_count = 0

        self._build_tab_widgets()
        self._apply_state()

    def _build_tab_widgets(self):
        # File frame
        file_frame = ttk.LabelFrame(self, text="CSV File", padding=8)
        file_frame.pack(fill=tk.X, pady=(0, 5))

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
        action_frame = ttk.Frame(self, padding=(0, 5))
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

        self.btn_example = ttk.Button(action_frame, text="Example CSV",
                                      command=self._on_example_csv)
        self.btn_example.pack(side=tk.RIGHT, padx=(0, 5))

        # Results
        results_frame = ttk.LabelFrame(self, text="Results", padding=8)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.results_text = scrolledtext.ScrolledText(
            results_frame, wrap=tk.WORD, state=tk.DISABLED,
            font=("Consolas", 10), height=15)
        self.results_text.pack(fill=tk.BOTH, expand=True)

        self.results_text.tag_configure("PASS", foreground="#228B22")
        self.results_text.tag_configure("FAIL", foreground="#CC0000")
        self.results_text.tag_configure("WARNING", foreground="#CC8800")
        self.results_text.tag_configure("INFO", foreground="#333333")

        # Status bar
        status_frame = ttk.Frame(self, padding=(0, 2, 0, 0))
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
            self.btn_validate.config(state=tk.DISABLED)
            self.btn_upload.config(state=tk.DISABLED)
            return

        self.btn_browse.config(state=tk.NORMAL)

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
        self.app._set_conn_busy(busy)

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
        text = format_step_result(step)
        self._append_result(text, step.status)

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
        logger.error("Tab error: %s", msg)

    # ------------------------------------------------------------------
    # Event handlers — view log (shared)
    # ------------------------------------------------------------------

    def _on_view_log(self):
        log_path = self.app.config.log_file
        if not os.path.exists(log_path):
            messagebox.showinfo("View Log", f"Log file not found:\n{log_path}")
            return
        try:
            os.startfile(log_path)
        except Exception as e:
            messagebox.showerror("View Log", f"Could not open log file:\n{e}")

    # ------------------------------------------------------------------
    # Subclass hooks — must be implemented by each tab
    # ------------------------------------------------------------------

    def _parse_csv(self, path: str):
        """Parse CSV file. Return (rows, skipped, errors, warnings)."""
        raise NotImplementedError

    def _show_row_preview(self, rows: list[tuple]):
        """Display parsed CSV rows in the results area."""
        raise NotImplementedError

    def _run_validation(self, conn):
        """Run the validation pipeline. Return PipelineResult."""
        raise NotImplementedError

    def _run_upload(self, conn, upload_count: int):
        """Run the upload pipeline. Return PipelineResult."""
        raise NotImplementedError

    def _get_upload_confirm_msg(self, count: int) -> str:
        """Return the upload confirmation message."""
        raise NotImplementedError

    def _on_how_it_works(self):
        """Show the "How It Works" dialog."""
        raise NotImplementedError

    def _get_example_csv_content(self) -> tuple[str, str]:
        """Return (filename, csv_content) for the example CSV."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Event handlers — example CSV
    # ------------------------------------------------------------------

    def _on_example_csv(self):
        """Write an example CSV to a temp file and open it in the default app."""
        filename, content = self._get_example_csv_content()
        try:
            stem, ext = os.path.splitext(filename)
            fd = tempfile.NamedTemporaryFile(
                mode="w", prefix=stem + "_", suffix=ext,
                newline="", encoding="utf-8", delete=False,
            )
            with fd:
                fd.write(content)
            os.startfile(fd.name)
        except Exception as e:
            messagebox.showerror("Example CSV", f"Could not open example CSV:\n{e}")

    # ------------------------------------------------------------------
    # Event handlers — shared browse/validate/upload logic
    # ------------------------------------------------------------------

    def _on_browse(self):
        path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return

        try:
            rows, skipped, errors, warnings = self._parse_csv(path)
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

    def _on_validate(self):
        self._append_result("\n--- Validation ---", "INFO")
        self._validation_has_fail = False

        def step_callback(step):
            self.after(0, lambda s=step: self._append_step(s))

        def worker():
            conn = self.app._ensure_connection()
            return self._run_validation(conn)

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
        upload_count = self._upload_count or len(self.rows)
        if not messagebox.askokcancel(
                "Confirm Upload",
                self._get_upload_confirm_msg(upload_count)):
            return

        self._append_result("\n--- Upload ---", "INFO")

        def step_callback(step):
            self.after(0, lambda s=step: self._append_step(s))

        def worker():
            return self._run_upload(self.app.conn, upload_count)

        def on_complete(result):
            if result.success:
                self._append_result("\nUpload complete.", "PASS")
                self._set_state(COMPLETE)
            else:
                self._append_result("\nUpload FAILED — transaction was rolled back.",
                                    "FAIL")
                self._set_state(CSV_LOADED)

        self._run_in_thread(worker, on_complete)


# ======================================================================
# EstShip Dates tab
# ======================================================================


class EstShipTab(BaseUploadTab):
    """Tab for uploading estimated ship dates to sostrs."""

    def _get_example_csv_content(self):
        return ("example_estship.csv",
                "SO_Number,Line_Item,Item_Number,Est_Ship_Date\n"
                "   2873157,a7EF0MVPRF,01-0014,4/20/2026\n"
                "   2844846,a7B90XEBT8,FNR316118-M50,5/15/2026\n"
                "   2869191,F2D0572DCA,01-04579/2,3/11/2026\n")

    def _parse_csv(self, path):
        from estship_uploader.csv_parser import parse_csv
        return parse_csv(path)

    def _show_row_preview(self, rows):
        self._append_result("--- CSV Preview ---", "INFO")
        self._append_result(
            f"{'SO_Number':<12} {'Line_Item':<12} {'Item_Number':<22} {'Est_Ship_Date'}", "INFO")
        self._append_result("-" * 60, "INFO")
        for so, line, item, date in rows:
            date_display = date if date is not None else "NULL"
            self._append_result(
                f"{so:<12} {line:<12} {item:<22} {date_display}", "INFO")
        self._append_result(f"\n{len(rows)} rows total\n", "INFO")

    def _run_validation(self, conn):
        def step_callback(step):
            self.after(0, lambda s=step: self._append_step(s))
        from estship_uploader.pipeline import run_validation
        return run_validation(conn, self.rows, self.app.config.database,
                              on_step=step_callback)

    def _run_upload(self, conn, upload_count):
        def step_callback(step):
            self.after(0, lambda s=step: self._append_step(s))
        from estship_uploader.pipeline import run_upload
        return run_upload(conn, upload_count,
                          database=self.app.config.database,
                          on_step=step_callback)

    def _get_upload_confirm_msg(self, count):
        return (
            f"This will permanently overwrite the Estimated Ship Date "
            f"(idestship) for {count} sales order line items "
            f"in the sostrs table.\n\n"
            f"Any existing estimated ship dates on these line items "
            f"will be replaced with the values from your CSV.\n\n"
            f"This cannot be undone. Continue?"
        )

    def _on_how_it_works(self):
        win = tk.Toplevel(self.app)
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

        def h(t): text.insert(tk.END, t + "\n", "heading")
        def sh(t): text.insert(tk.END, "\n" + t + "\n", "subheading")
        def b(t): text.insert(tk.END, t + "\n", "body")
        def sql(t): text.insert(tk.END, t + "\n", "sql")

        h("EstShip Date Uploader")
        b("")
        b("This tab bulk-updates the Estimated Ship Date (idestship) on sales")
        b("order line items in the ERP database (sostrs table) using data from")
        b("a CSV file.")
        b("")
        b("Every change runs inside a database transaction. If anything goes")
        b("wrong at any step, the entire batch is rolled back.")

        h("\nPipeline Steps")
        sh("Phase A: Setup & Import")
        b("Step 1 — Create a temporary staging table")
        b("Step 2 — Import CSV rows via parameterized INSERT")
        b("Step 3 — Verify row count matches the CSV")
        sh("Phase B: Validation")
        b("Step 4 — Check every SO/Line pair exists in the ERP")
        b("Step 5 — Cross-check item numbers (CSV vs database)")
        b("Step 6 — Show before/after date comparison")
        b("Step 7 — Flag date anomalies (past dates, >1 year out, NULLs)")
        b("Step 8 — Final count: N rows ready for upload")
        sh("Phase C: Upload (Transaction)")
        b("Step 9 — Execute the UPDATE inside a transaction")
        b("Step 10 — Validate while still in the transaction")
        b("Step 11 — COMMIT or ROLLBACK")
        b("Step 12 — Post-commit verification")
        sh("Phase D: Cleanup")
        b("Step 13 — Drop the staging table (always runs)")

        h("\nSafety Guarantees")
        b("")
        b("- All data inserted via parameterized queries")
        b("- UPDATE runs inside an explicit transaction")
        b("- Automatic ROLLBACK on any mismatch or error")
        b("- Staging table is always cleaned up")
        b("- Credentials are stripped from all error messages")

        text.config(state=tk.DISABLED)


# ======================================================================
# Item Class tab
# ======================================================================


class ItemClassTab(BaseUploadTab):
    """Tab for uploading item class (cbuyer) to icitem."""

    def _get_example_csv_content(self):
        return ("example_itemclass.csv",
                "citemno,cbuyer\n"
                "WIDGET-A100,A\n"
                "GADGET-B200,MTO\n"
                "PART-C300,\n")

    def _parse_csv(self, path):
        from estship_uploader.itemclass_csv_parser import parse_itemclass_csv
        return parse_itemclass_csv(path)

    def _show_row_preview(self, rows):
        self._append_result("--- CSV Preview ---", "INFO")
        self._append_result(f"{'citemno':<22} {'cbuyer'}", "INFO")
        self._append_result("-" * 35, "INFO")
        for item, buyer in rows:
            buyer_display = buyer if buyer else "(blank — will clear)"
            self._append_result(f"{item:<22} {buyer_display}", "INFO")
        self._append_result(f"\n{len(rows)} rows total\n", "INFO")

    def _run_validation(self, conn):
        def step_callback(step):
            self.after(0, lambda s=step: self._append_step(s))
        from estship_uploader.itemclass_pipeline import run_validation
        return run_validation(conn, self.rows, self.app.config.database,
                              on_step=step_callback)

    def _run_upload(self, conn, upload_count):
        def step_callback(step):
            self.after(0, lambda s=step: self._append_step(s))
        from estship_uploader.itemclass_pipeline import run_upload
        return run_upload(conn, upload_count,
                          database=self.app.config.database,
                          on_step=step_callback)

    def _get_upload_confirm_msg(self, count):
        return (
            f"This will permanently overwrite the Buyer Class (cbuyer) "
            f"for {count} items in the icitem table.\n\n"
            f"A backup of icitem will be created before the update.\n\n"
            f"Any existing buyer class values on these items "
            f"will be replaced with the values from your CSV.\n\n"
            f"This cannot be undone. Continue?"
        )

    def _on_how_it_works(self):
        win = tk.Toplevel(self.app)
        win.title("How It Works — Item Class Uploader")
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

        def h(t): text.insert(tk.END, t + "\n", "heading")
        def sh(t): text.insert(tk.END, "\n" + t + "\n", "subheading")
        def b(t): text.insert(tk.END, t + "\n", "body")
        def sql(t): text.insert(tk.END, t + "\n", "sql")

        h("Item Class (cbuyer) Uploader")
        b("")
        b("This tab bulk-updates the Buyer Class (cbuyer) on items in the")
        b("item master table (icitem) using data from a CSV file.")
        b("")
        b("CSV format: citemno, cbuyer")
        b("Blank cbuyer = clear the field (set to empty string)")
        b("")
        b("A backup of icitem is created before each upload (max 3 kept).")

        h("\nPipeline Steps")
        sh("Phase A: Setup & Import")
        b("Step 1 — Create staging table (ItemClassUpload_Staging)")
        b("Step 2 — Import CSV rows via parameterized INSERT")
        b("Step 3 — Verify row count")
        sh("Phase B: Validation")
        b("Step 4 — Check every item exists in icitem")
        b("Step 5 — Validate cbuyer values against approved list")
        b("  Non-approved values get a WARNING (not blocked)")
        b("Step 6 — Show before/after value comparison")
        b("Step 7 — Anomaly check (blanks being set, value distribution)")
        b("Step 8 — Final count")
        sh("Phase C: Upload (Transaction)")
        b("Step 9a — Backup icitem table")
        b("Step 9b — Execute UPDATE inside a transaction:")
        sql("    UPDATE t SET t.cbuyer = s.Buyer_Class")
        sql("    FROM icitem t")
        sql("    JOIN dbo.ItemClassUpload_Staging s")
        sql("        ON t.citemno = s.Item_Number")
        b("Step 10 — In-transaction validation")
        b("Step 11 — COMMIT or ROLLBACK")
        b("Step 12 — Post-commit verification")
        sh("Phase D: Cleanup")
        b("Step 13 — Drop staging table")

        h("\nApproved cbuyer Values")
        b("A, B, C, D, MTO, RESTRICTED, C1, C2, RES")
        b("Other values are allowed with a warning.")

        text.config(state=tk.DISABLED)


# ======================================================================
# Mfg Lead Time tab
# ======================================================================


class MfgLTTab(BaseUploadTab):
    """Tab for uploading manufacturing lead time (nmfgltime) to iciwhs."""

    def _get_example_csv_content(self):
        return ("example_mfglt.csv",
                "citemno,nmfgltime\n"
                "WIDGET-A100,14\n"
                "GADGET-B200,30\n"
                "PART-C300,0\n")

    def _parse_csv(self, path):
        from estship_uploader.mfglt_csv_parser import parse_mfglt_csv
        return parse_mfglt_csv(path)

    def _show_row_preview(self, rows):
        self._append_result("--- CSV Preview ---", "INFO")
        self._append_result(f"{'citemno':<22} {'nmfgltime'}", "INFO")
        self._append_result("-" * 35, "INFO")
        for item, lt in rows:
            lt_display = str(lt) if lt is not None else "NULL"
            self._append_result(f"{item:<22} {lt_display}", "INFO")
        self._append_result(f"\n{len(rows)} rows total\n", "INFO")

    def _run_validation(self, conn):
        def step_callback(step):
            self.after(0, lambda s=step: self._append_step(s))
        from estship_uploader.mfglt_pipeline import run_validation
        return run_validation(conn, self.rows, self.app.config.database,
                              on_step=step_callback)

    def _run_upload(self, conn, upload_count):
        def step_callback(step):
            self.after(0, lambda s=step: self._append_step(s))
        from estship_uploader.mfglt_pipeline import run_upload
        return run_upload(conn, upload_count,
                          database=self.app.config.database,
                          on_step=step_callback)

    def _get_upload_confirm_msg(self, count):
        return (
            f"This will permanently overwrite the Manufacturing Lead Time "
            f"(nmfgltime) for {count} items in the iciwhs table "
            f"(MAIN warehouse only).\n\n"
            f"A backup of iciwhs will be created before the update.\n\n"
            f"Any existing lead time values on these items "
            f"will be replaced with the values from your CSV.\n\n"
            f"This cannot be undone. Continue?"
        )

    def _on_how_it_works(self):
        win = tk.Toplevel(self.app)
        win.title("How It Works — Mfg Lead Time Uploader")
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

        def h(t): text.insert(tk.END, t + "\n", "heading")
        def sh(t): text.insert(tk.END, "\n" + t + "\n", "subheading")
        def b(t): text.insert(tk.END, t + "\n", "body")
        def sql(t): text.insert(tk.END, t + "\n", "sql")

        h("Manufacturing Lead Time Uploader")
        b("")
        b("This tab bulk-updates the Manufacturing Lead Time (nmfgltime)")
        b("on items in the warehouse table (iciwhs) for the MAIN warehouse")
        b("using data from a CSV file.")
        b("")
        b("CSV format: citemno, nmfgltime (integer days)")
        b("")
        b("A backup of iciwhs is created before each upload (max 3 kept).")

        h("\nPipeline Steps")
        sh("Phase A: Setup & Import")
        b("Step 1 — Create staging table (MfgLTUpload_Staging)")
        b("Step 2 — Import CSV rows")
        b("Step 3 — Verify row count")
        sh("Phase B: Validation")
        b("Step 4 — Check every item exists in iciwhs WHERE cwarehouse='MAIN'")
        b("Step 5 — Show before/after lead time comparison")
        b("Step 6 — Anomaly check (zero values, >365 days, NULLs)")
        b("Step 7 — Final count")
        sh("Phase C: Upload (Transaction)")
        b("Backup — Create backup of iciwhs table")
        b("Execute UPDATE inside a transaction:")
        sql("    UPDATE t SET t.nmfgltime = s.Mfg_Lead_Time")
        sql("    FROM iciwhs t")
        sql("    JOIN dbo.MfgLTUpload_Staging s")
        sql("        ON t.citemno = s.Item_Number")
        sql("    WHERE t.cwarehouse = 'MAIN'")
        b("In-transaction validation, COMMIT/ROLLBACK, post-commit verify")
        sh("Phase D: Cleanup")
        b("Drop staging table")

        text.config(state=tk.DISABLED)
