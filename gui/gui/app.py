"""
Main GUI application for Account Creation Tool.

Provides a tkinter-based interface that mirrors the CLI menu with:
- Admin email login
- Service buttons for each account creation step
- Real-time log output panel
- Session status indicators
- Pause/continue dialog for Selenium interactions
"""

import os
import sys
import re
import json
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime

# --- Persist last login email ---
_SETTINGS_FILE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AccountTool_settings.json")

def _load_settings():
    try:
        with open(_SETTINGS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_settings(settings):
    try:
        with open(_SETTINGS_FILE, "w") as f:
            json.dump(settings, f)
    except Exception:
        pass

# Add parent directory to path so scripts package is importable
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)


class LogRedirector:
    """Redirects print() output to the GUI log panel."""

    def __init__(self, text_widget, original_stream):
        self.text_widget = text_widget
        self.original = original_stream

    def write(self, message):
        if message.strip():
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted = f"[{timestamp}] {message.rstrip()}\n"
        else:
            formatted = message

        # Schedule GUI update on main thread
        self.text_widget.after(0, self._append, formatted)

        # Also write to original stream (terminal)
        if self.original:
            self.original.write(message)

    def _append(self, text):
        self.text_widget.configure(state="normal")
        self.text_widget.insert(tk.END, text)
        self.text_widget.see(tk.END)
        self.text_widget.configure(state="disabled")

    def flush(self):
        if self.original:
            self.original.flush()


class PauseDialog:
    """Thread-safe dialog that blocks a worker thread until the user clicks Continue."""

    def __init__(self, root):
        self.root = root
        self._event = threading.Event()

    def show(self, message):
        """Called from worker thread. Blocks until user clicks Continue."""
        self._event.clear()
        self.root.after(0, self._create_dialog, message)
        self._event.wait()

    def _create_dialog(self, message):
        dialog = tk.Toplevel(self.root)
        dialog.title("Action Required")
        dialog.geometry("450x180")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 225
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 90
        dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=message, wraplength=400, justify=tk.LEFT).pack(pady=(0, 20))

        btn = ttk.Button(frame, text="Continue", command=lambda: self._on_continue(dialog))
        btn.pack()
        btn.focus_set()
        dialog.bind("<Return>", lambda e: self._on_continue(dialog))

    def _on_continue(self, dialog):
        dialog.destroy()
        self._event.set()


class AccountCreationApp:
    """Main application window."""

    # Color scheme
    BG_COLOR = "#1e1e2e"
    PANEL_COLOR = "#2a2a3d"
    ACCENT_COLOR = "#7c3aed"
    ACCENT_HOVER = "#6d28d9"
    TEXT_COLOR = "#e2e8f0"
    MUTED_COLOR = "#94a3b8"
    SUCCESS_COLOR = "#22c55e"
    WARNING_COLOR = "#eab308"
    ERROR_COLOR = "#ef4444"
    LOG_BG = "#0f0f1a"

    def __init__(self, root):
        self.root = root
        self.root.title("Account Creation Tool")
        self.root.geometry("920x750")
        self.root.minsize(800, 650)
        self.root.configure(bg=self.BG_COLOR)

        # State
        self.array = []
        self.is_running = False
        self._pause_dialog = PauseDialog(root)

        # Configure ttk styles
        self._setup_styles()

        # Build UI
        self._build_header()
        self._build_records_panel()
        self._build_service_buttons()
        self._build_log_panel()
        self._build_status_bar()

        # Redirect stdout/stderr to log panel
        sys.stdout = LogRedirector(self.log_text, sys.__stdout__)
        sys.stderr = LogRedirector(self.log_text, sys.__stderr__)

        # Wire up pause callbacks for services that need user interaction
        self._setup_pause_callbacks()

        # Disable service buttons until user logs in
        self._set_buttons_state("disabled")
        self.login_btn.configure(state="normal")

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("App.TFrame", background=self.BG_COLOR)
        style.configure("Panel.TFrame", background=self.PANEL_COLOR)

        style.configure("Header.TLabel",
                        background=self.BG_COLOR,
                        foreground=self.TEXT_COLOR,
                        font=("Segoe UI", 16, "bold"))

        style.configure("SubHeader.TLabel",
                        background=self.BG_COLOR,
                        foreground=self.MUTED_COLOR,
                        font=("Segoe UI", 9))

        style.configure("Panel.TLabel",
                        background=self.PANEL_COLOR,
                        foreground=self.TEXT_COLOR,
                        font=("Segoe UI", 10))

        style.configure("Status.TLabel",
                        background=self.PANEL_COLOR,
                        foreground=self.SUCCESS_COLOR,
                        font=("Segoe UI", 9))

        style.configure("Accent.TButton",
                        background=self.ACCENT_COLOR,
                        foreground="white",
                        font=("Segoe UI", 10, "bold"),
                        padding=(12, 8))
        style.map("Accent.TButton",
                  background=[("active", self.ACCENT_HOVER), ("disabled", "#4a4a5a")])

        style.configure("Service.TButton",
                        background=self.PANEL_COLOR,
                        foreground=self.TEXT_COLOR,
                        font=("Segoe UI", 9),
                        padding=(10, 8))
        style.map("Service.TButton",
                  background=[("active", "#3a3a4d"), ("disabled", "#2a2a3d")],
                  foreground=[("disabled", "#4a4a5a")])

        style.configure("RunAll.TButton",
                        background="#059669",
                        foreground="white",
                        font=("Segoe UI", 10, "bold"),
                        padding=(12, 10))
        style.map("RunAll.TButton",
                  background=[("active", "#047857"), ("disabled", "#4a4a5a")])

        style.configure("StatusBar.TFrame", background=self.PANEL_COLOR)
        style.configure("StatusBar.TLabel",
                        background=self.PANEL_COLOR,
                        foreground=self.MUTED_COLOR,
                        font=("Segoe UI", 8))

    def _build_header(self):
        header = ttk.Frame(self.root, style="App.TFrame")
        header.pack(fill=tk.X, padx=20, pady=(15, 5))

        ttk.Label(header, text="Account Creation Tool",
                  style="Header.TLabel").pack(side=tk.LEFT)

        # Login area (right side of header)
        login_frame = ttk.Frame(header, style="App.TFrame")
        login_frame.pack(side=tk.RIGHT)

        ttk.Label(login_frame, text="Admin Email:",
                  style="SubHeader.TLabel").pack(side=tk.LEFT, padx=(0, 5))

        saved_email = _load_settings().get("email", os.environ.get("EMAIL", ""))
        self.email_var = tk.StringVar(value=saved_email)
        self.email_entry = ttk.Entry(login_frame, textvariable=self.email_var, width=35,
                                     font=("Segoe UI", 9))
        self.email_entry.pack(side=tk.LEFT, padx=(0, 8))

        self.login_btn = ttk.Button(login_frame, text="Login",
                                    style="Accent.TButton", command=self._on_login)
        self.login_btn.pack(side=tk.LEFT)

    def _build_records_panel(self):
        panel = ttk.Frame(self.root, style="Panel.TFrame")
        panel.pack(fill=tk.X, padx=20, pady=(10, 5))

        inner = ttk.Frame(panel, style="Panel.TFrame")
        inner.pack(fill=tk.X, padx=15, pady=10)

        self.records_label = ttk.Label(inner, text="No records loaded",
                                       style="Panel.TLabel")
        self.records_label.pack(side=tk.LEFT)

        self.session_label = ttk.Label(inner, text="",
                                       style="Status.TLabel")
        self.session_label.pack(side=tk.RIGHT)

        # Reload button
        reload_btn = ttk.Button(inner, text="Reload Data",
                                style="Service.TButton", command=self._on_reload)
        reload_btn.pack(side=tk.RIGHT, padx=(0, 15))

    def _build_service_buttons(self):
        container = ttk.Frame(self.root, style="App.TFrame")
        container.pack(fill=tk.X, padx=20, pady=5)

        # Run All button (full width)
        self.run_all_btn = ttk.Button(container, text="Run All Flows  (Sheets > Gmail > 8x8 > TPP > Update > AD)",
                                      style="RunAll.TButton", command=lambda: self._run_task("run_all"))
        self.run_all_btn.pack(fill=tk.X, pady=(0, 8))

        # Service buttons in a 2-column grid
        grid = ttk.Frame(container, style="App.TFrame")
        grid.pack(fill=tk.X)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        services = [
            ("Generate Login Sheets", "login_sheets"),
            ("Create Gmail Accounts", "gmail"),
            ("Setup 8x8 PBX Extensions", "8x8"),
            ("Create Transport Pro Accounts", "tpp"),
            ("Update Gmail Profiles & Sigs", "gmail_update"),
            ("Create AD Server Accounts", "ad"),
            ("Send Notification to HR/QC", "notify"),
            ("Register Numbers (FCR)", "fcr"),
            ("Update Onboarding Sheet", "update_sheet"),
            ("Clear All Sessions", "clear_sessions"),
        ]

        self.service_buttons = {}
        for i, (label, key) in enumerate(services):
            btn = ttk.Button(grid, text=label, style="Service.TButton",
                             command=lambda k=key: self._run_task(k))
            btn.grid(row=i // 2, column=i % 2, padx=3, pady=3, sticky="ew")
            self.service_buttons[key] = btn

    def _build_log_panel(self):
        log_frame = ttk.Frame(self.root, style="App.TFrame")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(5, 5))

        top = ttk.Frame(log_frame, style="App.TFrame")
        top.pack(fill=tk.X)
        ttk.Label(top, text="Log Output", style="SubHeader.TLabel").pack(side=tk.LEFT)

        clear_btn = ttk.Button(top, text="Clear", style="Service.TButton",
                               command=self._clear_log)
        clear_btn.pack(side=tk.RIGHT)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, state="disabled",
            bg=self.LOG_BG, fg=self.TEXT_COLOR,
            font=("Consolas", 9), insertbackground=self.TEXT_COLOR,
            selectbackground=self.ACCENT_COLOR, relief=tk.FLAT,
            padx=10, pady=8
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def _build_status_bar(self):
        bar = ttk.Frame(self.root, style="StatusBar.TFrame")
        bar.pack(fill=tk.X, padx=0, pady=0)

        inner = ttk.Frame(bar, style="StatusBar.TFrame")
        inner.pack(fill=tk.X, padx=15, pady=4)

        self.status_text = ttk.Label(inner, text="Ready", style="StatusBar.TLabel")
        self.status_text.pack(side=tk.LEFT)

        self.session_info = ttk.Label(inner, text="", style="StatusBar.TLabel")
        self.session_info.pack(side=tk.RIGHT)

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state="disabled")

    def _set_status(self, text, color=None):
        self.status_text.configure(text=text)
        if color:
            self.status_text.configure(foreground=color)

    def _set_buttons_state(self, state):
        """Enable or disable all service buttons."""
        for btn in self.service_buttons.values():
            btn.configure(state=state)
        self.run_all_btn.configure(state=state)
        self.login_btn.configure(state=state)

    def _update_records_display(self):
        if self.array:
            names = [f"{u.get('Preferred First Name', '')} {u.get('Preferred Last Name', '')}" for u in self.array]
            self.records_label.configure(
                text=f"{len(self.array)} records loaded: {', '.join(names)}"
            )
        else:
            self.records_label.configure(text="No records loaded")

    def _update_session_display(self):
        from scripts.session_manager import session_status
        parts = []
        for svc, label in [("8x8", "8x8"), ("tp", "TP"), ("fcr", "FCR")]:
            status = session_status(svc)
            if status["active"]:
                parts.append(f"{label}: active ({status['saved_at']})")
        if parts:
            self.session_info.configure(text="Sessions: " + " | ".join(parts))
        else:
            self.session_info.configure(text="No cached sessions")

    # --- Actions ---

    def _on_login(self):
        email = self.email_var.get().strip()
        if not email or "@" not in email:
            messagebox.showwarning("Invalid Email", "Please enter a valid @company.com email address.")
            return

        from scripts.authenticator import set_admin_email
        set_admin_email(email)
        os.environ["EMAIL"] = email

        _save_settings({**_load_settings(), "email": email})
        print(f"Logged in as: {email}")
        self._set_status(f"Logged in: {email}", self.SUCCESS_COLOR)

        # Load data
        self._on_reload()

    def _on_reload(self):
        self._run_task("reload")

    def _setup_pause_callbacks(self):
        """Wire up the pause dialog to services that need user interaction."""
        try:
            from scripts.utils import set_pause_callback as set_utils_pause
            set_utils_pause(self._pause_dialog.show)
        except ImportError:
            pass
        try:
            from scripts.pbx_8x8_service import set_pause_callback as set_8x8_pause
            set_8x8_pause(self._pause_dialog.show)
        except ImportError:
            pass
        try:
            from scripts.tpp_service import set_pause_callback as set_tpp_pause
            set_tpp_pause(self._pause_dialog.show)
        except ImportError:
            pass

    def _run_task(self, task_key):
        """Run a task in a background thread to keep GUI responsive."""
        if self.is_running and task_key != "clear_sessions":
            messagebox.showinfo("Busy", "A task is already running. Please wait.")
            return

        self.is_running = True
        self._set_buttons_state("disabled")
        self._set_status(f"Running: {task_key}...", self.WARNING_COLOR)

        thread = threading.Thread(target=self._execute_task, args=(task_key,), daemon=True)
        thread.start()

    def _execute_task(self, task_key):
        """Execute a task (runs in worker thread)."""
        try:
            if task_key == "reload":
                print("Loading data from onboarding sheet...")
                from scripts.data_processing import get_processed_data
                self.array = get_processed_data()
                print(f"Loaded {len(self.array)} records.")
                self.root.after(0, self._update_records_display)

            elif task_key == "run_all":
                if not self.array:
                    print("No users to process!")
                    return
                from scripts.pdf_service import makeLoginSheets
                from scripts.gmail_service import makeGmail, updateUserInfo
                from scripts.pbx_8x8_service import make8x8
                from scripts.tpp_service import makeTPP
                from scripts.ad_service import makeAD

                steps = [
                    ("Login Sheets", makeLoginSheets),
                    ("Gmail", makeGmail),
                    ("8x8", make8x8),
                    ("TPP", makeTPP),
                    ("Gmail Update", updateUserInfo),
                    ("AD", makeAD),
                ]
                for name, func in steps:
                    print(f"\n{'='*40}")
                    print(f"Starting: {name}")
                    print(f"{'='*40}")
                    try:
                        func(self.array)
                        print(f"{name} Done")
                    except Exception as e:
                        print(f"{name} Failed: {e}")

            elif task_key == "login_sheets":
                from scripts.pdf_service import makeLoginSheets
                makeLoginSheets(self.array)
                print("Login Sheets Done")

            elif task_key == "gmail":
                from scripts.gmail_service import makeGmail
                makeGmail(self.array)
                print("Gmail Done")

            elif task_key == "8x8":
                from scripts.pbx_8x8_service import make8x8
                make8x8(self.array)
                print("8x8 Done")

            elif task_key == "tpp":
                from scripts.tpp_service import makeTPP
                makeTPP(self.array)
                print("TPP Done")

            elif task_key == "gmail_update":
                from scripts.gmail_service import updateUserInfo
                updateUserInfo(self.array)
                print("Gmail Update Done")

            elif task_key == "ad":
                from scripts.ad_service import makeAD
                makeAD(self.array)
                print("AD Done")

            elif task_key == "notify":
                self._run_notify()

            elif task_key == "fcr":
                self._run_fcr()

            elif task_key == "update_sheet":
                from scripts.data_processing import update_onboarding_sheet
                update_onboarding_sheet(self.array)
                print("Sheet Update Done")

            elif task_key == "clear_sessions":
                from scripts.session_manager import clear_all_sessions
                clear_all_sessions()
                print("All cached sessions cleared.")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

        finally:
            self.is_running = False
            self.root.after(0, self._set_buttons_state, "normal")
            self.root.after(0, self._set_status, "Ready", self.MUTED_COLOR)
            self.root.after(0, self._update_session_display)

    def _run_notify(self):
        if not self.array:
            print("No users to notify HR about.")
            return
        from scripts.utils import sendEmail
        email_body = """
        <div style="font-family: Arial, sans-serif; color: #333;">
            <p>Hello, please review the upcoming hires listed below and complete account creation according to their position/title. If you have any questions or concerns please reach out to the HR Team.</p>
            <hr>
        </div>
        """
        for hire in self.array:
            email_body += f"""
            <div style="margin-bottom: 20px;">
                <strong>Employee Name:</strong> {hire.get('Preferred First Name', '')} {hire.get('Preferred Last Name', '')}<br>
                <strong>Employee Email:</strong> {hire.get('Employee Email', '')}<br>
                <strong>Direct Line:</strong> {hire.get('Direct Line', '')}<br>
                <strong>Ext:</strong> {hire.get('Ext', '')}<br>
                <strong>Employee Title:</strong> {hire.get('Title', '')}<br>
                <strong>Employee Supervisor Email:</strong> {hire.get('Direct Report', '')}
            </div>
            """
        sendTo = "notifications@company.com,hr@company.com,admin@company.com,crm.admin@company.com"
        sendEmail(sendTo, "New Hire Accounts", email_body)
        print("Notification email sent successfully.")

    def _run_fcr(self):
        """Prompt for phone numbers via a dialog, then register."""
        self._fcr_numbers = None
        self._fcr_event = threading.Event()
        self.root.after(0, self._show_fcr_dialog)
        self._fcr_event.wait()

        if self._fcr_numbers:
            print(f"Registering {len(self._fcr_numbers)} number(s)...")
            from scripts.fcr_service import numberRegister
            numberRegister(self._fcr_numbers)
            print("FCR Done")
        else:
            print("No numbers entered.")

    def _show_fcr_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Register Numbers - Free Caller Registry")
        dialog.geometry("450x300")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Enter phone numbers (comma-separated or one per line):",
                  font=("Segoe UI", 10)).pack(anchor=tk.W)

        text = tk.Text(frame, height=10, font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        text.focus_set()

        # Pre-fill with loaded Direct Line numbers if available
        loaded_numbers = [
            re.sub(r'\D', '', user.get("Direct Line", ""))
            for user in self.array if user.get("Direct Line")
        ]

        def use_loaded():
            if loaded_numbers:
                text.delete("1.0", tk.END)
                text.insert("1.0", "\n".join(loaded_numbers))
            else:
                messagebox.showinfo("No Numbers", "No Direct Line numbers found in loaded records.")

        def submit():
            raw = text.get("1.0", tk.END)
            numbers = []
            for line in raw.split("\n"):
                for n in line.split(","):
                    cleaned = re.sub(r'\D', '', n.strip())
                    if cleaned:
                        numbers.append(cleaned)
            self._fcr_numbers = numbers if numbers else None
            dialog.destroy()
            self._fcr_event.set()

        def cancel():
            self._fcr_numbers = None
            dialog.destroy()
            self._fcr_event.set()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Register", style="Accent.TButton", command=submit).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Cancel", style="Service.TButton", command=cancel).pack(side=tk.RIGHT)
        load_btn = ttk.Button(btn_frame, text=f"Use Loaded Numbers ({len(loaded_numbers)})",
                              style="Service.TButton", command=use_loaded)
        load_btn.pack(side=tk.LEFT)

        dialog.protocol("WM_DELETE_WINDOW", cancel)


def launch():
    """Entry point to launch the GUI application."""
    root = tk.Tk()
    app = AccountCreationApp(root)

    root.mainloop()
