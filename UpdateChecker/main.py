import os
import sys
import json
import threading
import platform
import ctypes
from tkinter import *
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from modules.database import init_db, get_history, clear_history, search_history, export_to_csv, get_filtered_history, get_distinct_computers
from modules.winget_checker import check_program_updates, is_winget_installed
from modules.driver_checker import check_driver_updates
from modules.updater import UpdateManager
from modules.system_restore import is_restore_point_enabled, create_restore_point
from modules.notifications import show_notification, notify_updates_available
from modules.synology_sync import test_connection as test_synology, sync_to_synology, download_from_synology
from modules.github_sync import test_connection as test_github, full_sync as github_full_sync


CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def request_admin():
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "app_name": "UpdateChecker",
        "version": "1.0.0",
        "synology": {"quickconnect_id": "", "username": "", "password": "", "remote_path": "/UpdateChecker/update_history.db", "auto_sync": False},
        "github": {"repo_name": "UpdateChecker-Backup", "personal_access_token": "", "branch": "main", "auto_sync": False},
        "preferences": {"check_programs": True, "check_drivers": True, "create_restore_points": True, "notifications_enabled": True, "auto_check_on_start": False, "track_computer_name": True},
        "window": {"width": 1000, "height": 700, "theme": "dark"}
    }


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


class SettingsDialog:
    def __init__(self, parent, config):
        self.dialog = Toplevel(parent)
        self.dialog.title("Settings - UpdateChecker")
        self.dialog.geometry("550x500")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.config = config
        self.result = None

        main_frame = ttk.Frame(self.dialog, padding=15)
        main_frame.pack(fill=BOTH, expand=True)

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=BOTH, expand=True)

        syn_frame = ttk.Frame(notebook, padding=10)
        notebook.add(syn_frame, text="Synology")

        ttk.Label(syn_frame, text="QuickConnect ID:").grid(row=0, column=0, sticky=W, pady=5)
        self.syn_qid = ttk.Entry(syn_frame, width=40)
        self.syn_qid.insert(0, config.get("synology", {}).get("quickconnect_id", ""))
        self.syn_qid.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(syn_frame, text="Username:").grid(row=1, column=0, sticky=W, pady=5)
        self.syn_user = ttk.Entry(syn_frame, width=40)
        self.syn_user.insert(0, config.get("synology", {}).get("username", ""))
        self.syn_user.grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(syn_frame, text="Password:").grid(row=2, column=0, sticky=W, pady=5)
        self.syn_pass = ttk.Entry(syn_frame, width=40, show="*")
        self.syn_pass.insert(0, config.get("synology", {}).get("password", ""))
        self.syn_pass.grid(row=2, column=1, pady=5, padx=5)

        ttk.Label(syn_frame, text="Remote Path:").grid(row=3, column=0, sticky=W, pady=5)
        self.syn_path = ttk.Entry(syn_frame, width=40)
        self.syn_path.insert(0, config.get("synology", {}).get("remote_path", "/UpdateChecker/update_history.db"))
        self.syn_path.grid(row=3, column=1, pady=5, padx=5)

        self.syn_auto = BooleanVar(value=config.get("synology", {}).get("auto_sync", False))
        ttk.Checkbutton(syn_frame, text="Auto-sync after updates", variable=self.syn_auto).grid(row=4, column=0, columnspan=2, pady=10)

        gh_frame = ttk.Frame(notebook, padding=10)
        notebook.add(gh_frame, text="GitHub")

        ttk.Label(gh_frame, text="Personal Access Token:").grid(row=0, column=0, sticky=W, pady=5)
        self.gh_token = ttk.Entry(gh_frame, width=40, show="*")
        self.gh_token.insert(0, config.get("github", {}).get("personal_access_token", ""))
        self.gh_token.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(gh_frame, text="Repository Name:").grid(row=1, column=0, sticky=W, pady=5)
        self.gh_repo = ttk.Entry(gh_frame, width=40)
        self.gh_repo.insert(0, config.get("github", {}).get("repo_name", "UpdateChecker-Backup"))
        self.gh_repo.grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(gh_frame, text="Branch:").grid(row=2, column=0, sticky=W, pady=5)
        self.gh_branch = ttk.Entry(gh_frame, width=40)
        self.gh_branch.insert(0, config.get("github", {}).get("branch", "main"))
        self.gh_branch.grid(row=2, column=1, pady=5, padx=5)

        self.gh_auto = BooleanVar(value=config.get("github", {}).get("auto_sync", False))
        ttk.Checkbutton(gh_frame, text="Auto-sync after updates", variable=self.gh_auto).grid(row=3, column=0, columnspan=2, pady=10)

        pref_frame = ttk.Frame(notebook, padding=10)
        notebook.add(pref_frame, text="Preferences")

        self.pref_programs = BooleanVar(value=config.get("preferences", {}).get("check_programs", True))
        ttk.Checkbutton(pref_frame, text="Check for program updates", variable=self.pref_programs).grid(row=0, column=0, sticky=W, pady=5)

        self.pref_drivers = BooleanVar(value=config.get("preferences", {}).get("check_drivers", True))
        ttk.Checkbutton(pref_frame, text="Check for driver updates", variable=self.pref_drivers).grid(row=1, column=0, sticky=W, pady=5)

        self.pref_restore = BooleanVar(value=config.get("preferences", {}).get("create_restore_points", True))
        ttk.Checkbutton(pref_frame, text="Create system restore points before updates", variable=self.pref_restore).grid(row=2, column=0, sticky=W, pady=5)

        self.pref_notify = BooleanVar(value=config.get("preferences", {}).get("notifications_enabled", True))
        ttk.Checkbutton(pref_frame, text="Enable toast notifications", variable=self.pref_notify).grid(row=3, column=0, sticky=W, pady=5)

        self.pref_autocheck = BooleanVar(value=config.get("preferences", {}).get("auto_check_on_start", False))
        ttk.Checkbutton(pref_frame, text="Auto-check for updates on start", variable=self.pref_autocheck).grid(row=4, column=0, sticky=W, pady=5)

        self.pref_track = BooleanVar(value=config.get("preferences", {}).get("track_computer_name", True))
        ttk.Checkbutton(pref_frame, text="Track computer name in history", variable=self.pref_track).grid(row=5, column=0, sticky=W, pady=5)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=X, pady=10)

        ttk.Button(btn_frame, text="Save", command=self.on_save, width=15).pack(side=RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy, width=15).pack(side=RIGHT, padx=5)

    def on_save(self):
        self.config["synology"]["quickconnect_id"] = self.syn_qid.get()
        self.config["synology"]["username"] = self.syn_user.get()
        self.config["synology"]["password"] = self.syn_pass.get()
        self.config["synology"]["remote_path"] = self.syn_path.get()
        self.config["synology"]["auto_sync"] = self.syn_auto.get()

        self.config["github"]["personal_access_token"] = self.gh_token.get()
        self.config["github"]["repo_name"] = self.gh_repo.get()
        self.config["github"]["branch"] = self.gh_branch.get()
        self.config["github"]["auto_sync"] = self.gh_auto.get()

        self.config["preferences"]["check_programs"] = self.pref_programs.get()
        self.config["preferences"]["check_drivers"] = self.pref_drivers.get()
        self.config["preferences"]["create_restore_points"] = self.pref_restore.get()
        self.config["preferences"]["notifications_enabled"] = self.pref_notify.get()
        self.config["preferences"]["auto_check_on_start"] = self.pref_autocheck.get()
        self.config["preferences"]["track_computer_name"] = self.pref_track.get()

        self.result = self.config
        save_config(self.config)
        self.dialog.destroy()


class HistoryWindow:
    def __init__(self, parent):
        self.window = Toplevel(parent)
        self.window.title("Update History - UpdateChecker")
        self.window.geometry("900x500")
        self.window.transient(parent)

        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=BOTH, expand=True)

        filter_frame = ttk.LabelFrame(main_frame, text="Filters", padding=10)
        filter_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(filter_frame, text="Type:").grid(row=0, column=0, padx=5)
        self.type_filter = ttk.Combobox(filter_frame, values=["All", "program", "driver"], state="readonly", width=15)
        self.type_filter.current(0)
        self.type_filter.grid(row=0, column=1, padx=5)

        ttk.Label(filter_frame, text="Status:").grid(row=0, column=2, padx=5)
        self.status_filter = ttk.Combobox(filter_frame, values=["All", "installed", "failed", "skipped"], state="readonly", width=15)
        self.status_filter.current(0)
        self.status_filter.grid(row=0, column=3, padx=5)

        ttk.Label(filter_frame, text="Computer:").grid(row=0, column=4, padx=5)
        computers = ["All"] + get_distinct_computers()
        self.computer_filter = ttk.Combobox(filter_frame, values=computers, state="readonly", width=20)
        self.computer_filter.current(0)
        self.computer_filter.grid(row=0, column=5, padx=5)

        ttk.Button(filter_frame, text="Apply Filter", command=self.apply_filter).grid(row=0, column=6, padx=10)
        ttk.Button(filter_frame, text="Export CSV", command=self.export_csv).grid(row=0, column=7, padx=5)

        columns = ("timestamp", "name", "type", "old_version", "new_version", "status", "computer")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("timestamp", text="Date/Time")
        self.tree.heading("name", text="Name")
        self.tree.heading("type", text="Type")
        self.tree.heading("old_version", text="Old Version")
        self.tree.heading("new_version", text="New Version")
        self.tree.heading("status", text="Status")
        self.tree.heading("computer", text="Computer")

        self.tree.column("timestamp", width=150)
        self.tree.column("name", width=200)
        self.tree.column("type", width=80)
        self.tree.column("old_version", width=100)
        self.tree.column("new_version", width=100)
        self.tree.column("status", width=80)
        self.tree.column("computer", width=120)

        scrollbar = ttk.Scrollbar(main_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.apply_filter()

    def apply_filter(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        type_val = self.type_filter.get() if self.type_filter.get() != "All" else None
        status_val = self.status_filter.get() if self.status_filter.get() != "All" else None
        computer_val = self.computer_filter.get() if self.computer_filter.get() != "All" else None

        records = get_filtered_history(type_filter=type_val, status_filter=status_val, computer_filter=computer_val)

        for r in records:
            self.tree.insert("", END, values=(
                r.get("timestamp", ""),
                r.get("name", ""),
                r.get("type", ""),
                r.get("old_version", ""),
                r.get("new_version", ""),
                r.get("status", ""),
                r.get("computer_name", "")
            ))

    def export_csv(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Export History to CSV"
        )
        if filepath:
            try:
                export_to_csv(filepath)
                messagebox.showinfo("Export Successful", f"History exported to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Export Failed", str(e))


class UpdateCheckerApp:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.update_manager = UpdateManager(self.config)
        self.available_updates = []
        self.selected_updates = []
        self.is_checking = False
        self.is_installing = False

        init_db()
        self.setup_gui()
        self.setup_menu()

        if self.config.get("preferences", {}).get("auto_check_on_start", False):
            self.root.after(500, self.check_for_updates)

    def setup_gui(self):
        w = self.config.get("window", {}).get("width", 1000)
        h = self.config.get("window", {}).get("height", 700)

        self.root.title("UpdateChecker - Portable Update Manager")
        self.root.geometry(f"{w}x{h}")
        self.root.minsize(800, 600)

        theme = self.config.get("window", {}).get("theme", "dark")
        if theme == "dark":
            bg_color = "#2b2b2b"
            fg_color = "#ffffff"
            select_bg = "#404040"
            self.root.configure(bg=bg_color)
            style = ttk.Style()
            style.theme_use("clam")
            style.configure("TFrame", background=bg_color)
            style.configure("TLabel", background=bg_color, foreground=fg_color)
            style.configure("TButton", background=select_bg, foreground=fg_color)
            style.configure("TNotebook", background=bg_color, foreground=fg_color)
            style.configure("TNotebook.Tab", background=select_bg, foreground=fg_color)
            style.map("TButton", background=[("active", "#505050")])
            style.configure("Treeview", background=select_bg, foreground=fg_color, fieldbackground=select_bg)
            style.configure("Treeview.Heading", background=bg_color, foreground=fg_color)
            style.configure("TCheckbutton", background=bg_color, foreground=fg_color)
            style.configure("TLabelframe", background=bg_color, foreground=fg_color)
            style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color)
            style.configure("TEntry", fieldbackground=select_bg, foreground=fg_color)
            style.configure("TCombobox", fieldbackground=select_bg, foreground=fg_color)
            style.configure("Horizontal.TProgressbar", background="#4CAF50")
            style.configure("TText", background=select_bg, foreground=fg_color)

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=BOTH, expand=True)

        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=X, pady=(0, 10))

        self.computer_label = ttk.Label(header_frame, text=f"Computer: {platform.node()}", font=("Segoe UI", 9))
        self.computer_label.pack(side=LEFT)

        self.winget_status = ttk.Label(header_frame, text="", font=("Segoe UI", 9))
        self.winget_status.pack(side=RIGHT, padx=10)

        self.admin_label = ttk.Label(header_frame, text="", font=("Segoe UI", 9))
        self.admin_label.pack(side=RIGHT, padx=10)

        check_frame = ttk.Frame(main_frame)
        check_frame.pack(fill=X, pady=(0, 10))

        self.check_btn = ttk.Button(check_frame, text="Check for Updates", command=self.check_for_updates, width=25)
        self.check_btn.pack(side=LEFT, padx=(0, 10))

        self.install_btn = ttk.Button(check_frame, text="Install Selected", command=self.install_selected, width=20, state=DISABLED)
        self.install_btn.pack(side=LEFT, padx=5)

        self.cancel_btn = ttk.Button(check_frame, text="Cancel", command=self.cancel_operation, width=15, state=DISABLED)
        self.cancel_btn.pack(side=LEFT, padx=5)

        self.select_all_btn = ttk.Button(check_frame, text="Select All", command=self.select_all, width=12)
        self.select_all_btn.pack(side=LEFT, padx=2)

        self.deselect_btn = ttk.Button(check_frame, text="Deselect All", command=self.deselect_all, width=14)
        self.deselect_btn.pack(side=LEFT, padx=2)

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=BOTH, expand=True, pady=(0, 10))

        programs_frame = ttk.Frame(notebook, padding=5)
        notebook.add(programs_frame, text="Program Updates")

        prog_columns = ("select", "name", "current", "available", "source")
        self.prog_tree = ttk.Treeview(programs_frame, columns=prog_columns, show="headings", selectmode="none", height=10)

        self.prog_tree.heading("select", text="")
        self.prog_tree.heading("name", text="Program Name")
        self.prog_tree.heading("current", text="Current Version")
        self.prog_tree.heading("available", text="Available Version")
        self.prog_tree.heading("source", text="Source")

        self.prog_tree.column("select", width=40, anchor=CENTER)
        self.prog_tree.column("name", width=250)
        self.prog_tree.column("current", width=120)
        self.prog_tree.column("available", width=120)
        self.prog_tree.column("source", width=150)

        self.prog_tree.bind("<ButtonRelease-1>", self.on_prog_click)

        prog_scroll = ttk.Scrollbar(programs_frame, orient=VERTICAL, command=self.prog_tree.yview)
        self.prog_tree.configure(yscrollcommand=prog_scroll.set)
        self.prog_tree.pack(side=LEFT, fill=BOTH, expand=True)
        prog_scroll.pack(side=RIGHT, fill=Y)

        drivers_frame = ttk.Frame(notebook, padding=5)
        notebook.add(drivers_frame, text="Driver Updates")

        drv_columns = ("select", "provider", "version")
        self.drv_tree = ttk.Treeview(drivers_frame, columns=drv_columns, show="tree headings", selectmode="none", height=10)

        self.drv_tree.heading("#0", text="Driver Name")
        self.drv_tree.heading("select", text="")
        self.drv_tree.heading("provider", text="Provider")
        self.drv_tree.heading("version", text="Version")

        self.drv_tree.column("#0", width=350, minwidth=250)
        self.drv_tree.column("select", width=40, anchor=CENTER)
        self.drv_tree.column("provider", width=180)
        self.drv_tree.column("version", width=120)

        self.drv_tree.bind("<ButtonRelease-1>", self.on_drv_click)

        drv_scroll = ttk.Scrollbar(drivers_frame, orient=VERTICAL, command=self.drv_tree.yview)
        self.drv_tree.configure(yscrollcommand=drv_scroll.set)
        self.drv_tree.pack(side=LEFT, fill=BOTH, expand=True)
        drv_scroll.pack(side=RIGHT, fill=Y)

        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=X, pady=(0, 5))

        self.progress_bar = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress_bar.pack(fill=X)

        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=X)

        self.status_label = ttk.Label(status_frame, text="Ready", font=("Segoe UI", 9))
        self.status_label.pack(side=LEFT)

        self.count_label = ttk.Label(status_frame, text="", font=("Segoe UI", 9))
        self.count_label.pack(side=RIGHT)

        self.update_status_bar()
        self.update_admin_status()

    def setup_menu(self):
        menubar = Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Exit", command=self.root.quit)

        tools_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Settings", command=self.open_settings)
        tools_menu.add_separator()
        tools_menu.add_command(label="Sync to Synology", command=self.sync_synology)
        tools_menu.add_command(label="Sync to GitHub", command=self.sync_github)
        tools_menu.add_separator()
        tools_menu.add_command(label="View History", command=self.open_history)
        tools_menu.add_separator()
        tools_menu.add_command(label="Clear History", command=self.clear_history_confirm)

        help_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

    def update_status_bar(self):
        if is_admin():
            self.admin_label.config(text="✓ Administrator", foreground="#4CAF50")
        else:
            self.admin_label.config(text="✗ Not Administrator", foreground="#F44336")

        if is_winget_installed():
            self.winget_status.config(text="✓ Winget Available", foreground="#4CAF50")
        else:
            self.winget_status.config(text="✗ Winget Not Available", foreground="#FF9800")

    def update_admin_status(self):
        if not is_admin():
            self.status_label.config(text="Some features require administrator privileges.")

    def set_status(self, message):
        self.status_label.config(text=message)
        self.root.update_idletasks()

    def set_count(self, program_count=0, driver_count=0):
        self.count_label.config(text=f"Programs: {program_count} | Drivers: {driver_count}")

    def update_btn_states(self, checking=False, installing=False):
        self.is_checking = checking
        self.is_installing = installing

        if checking or installing:
            self.check_btn.config(state=DISABLED)
            self.install_btn.config(state=DISABLED)
            self.cancel_btn.config(state=NORMAL)
        else:
            self.check_btn.config(state=NORMAL)
            has_selection = len(self.selected_updates) > 0
            self.install_btn.config(state=NORMAL if has_selection else DISABLED)
            self.cancel_btn.config(state=DISABLED)

    def select_all(self):
        self.selected_updates = []
        for u in self.available_updates:
            if u not in self.selected_updates:
                self.selected_updates.append(u)

        for item in self.prog_tree.get_children():
            self.prog_tree.set(item, "select", "☑")

        for cat_item in self.drv_tree.get_children():
            for child in self.drv_tree.get_children(cat_item):
                self.drv_tree.set(child, "select", "☑")

        self.install_btn.config(state=NORMAL)
        self.set_status(f"Selected {len(self.selected_updates)} update(s).")

    def deselect_all(self):
        self.selected_updates = []
        for item in self.prog_tree.get_children():
            self.prog_tree.set(item, "select", "")
        for cat_item in self.drv_tree.get_children():
            for child in self.drv_tree.get_children(cat_item):
                self.drv_tree.set(child, "select", "")
        self.install_btn.config(state=DISABLED)
        self.set_status("All selections cleared.")

    def refresh_selection_btn(self):
        self.install_btn.config(state=NORMAL if len(self.selected_updates) > 0 else DISABLED)

    def on_prog_click(self, event):
        item = self.prog_tree.identify_row(event.y)
        if item:
            values = self.prog_tree.item(item, "values")
            current = self.prog_tree.set(item, "select")
            name = values[1] if len(values) > 1 else ""
            if current == "☑":
                self.prog_tree.set(item, "select", "")
                self.selected_updates = [u for u in self.selected_updates if u.get("name") != name]
            else:
                self.prog_tree.set(item, "select", "☑")
                for u in self.available_updates:
                    if u.get("name") == name and u.get("type") == "program" and u not in self.selected_updates:
                        self.selected_updates.append(u)
                        break
            self.refresh_selection_btn()

    def on_drv_click(self, event):
        item = self.drv_tree.identify_row(event.y)
        if not item:
            return

        parent = self.drv_tree.parent(item)

        if not parent:
            for child in self.drv_tree.get_children(item):
                current = self.drv_tree.set(child, "select")
                name = self.drv_tree.item(child, "text")
                if current == "☑":
                    self.drv_tree.set(child, "select", "")
                    self.selected_updates = [u for u in self.selected_updates if u.get("name") != name]
                else:
                    self.drv_tree.set(child, "select", "☑")
                    for u in self.available_updates:
                        if u.get("name") == name and u.get("type") == "driver" and u not in self.selected_updates:
                            self.selected_updates.append(u)
                            break
            self.refresh_selection_btn()
            return

        current = self.drv_tree.set(item, "select")
        name = self.drv_tree.item(item, "text")
        if current == "☑":
            self.drv_tree.set(item, "select", "")
            self.selected_updates = [u for u in self.selected_updates if u.get("name") != name]
        else:
            self.drv_tree.set(item, "select", "☑")
            for u in self.available_updates:
                if u.get("name") == name and u.get("type") == "driver" and u not in self.selected_updates:
                    self.selected_updates.append(u)
                    break
        self.refresh_selection_btn()

    def check_for_updates(self):
        if self.is_checking:
            return

        self.update_btn_states(checking=True)
        self.set_status("Checking for updates...")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start(10)

        for item in self.prog_tree.get_children():
            self.prog_tree.delete(item)
        for item in self.drv_tree.get_children():
            self.drv_tree.delete(item)

        self.available_updates = []
        self.selected_updates = []

        thread = threading.Thread(target=self._check_worker, daemon=True)
        thread.start()

    def _check_worker(self):
        all_updates = []

        if self.config.get("preferences", {}).get("check_programs", True):
            self.root.after(0, lambda: self.set_status("Checking program updates via Winget..."))
            prog_result = check_program_updates()
            if prog_result["success"]:
                all_updates.extend(prog_result["updates"])
                program_count = len(prog_result["updates"])
            else:
                program_count = 0
                if prog_result["error"]:
                    self.root.after(0, lambda e=prog_result["error"]: self.set_status(f"Program check: {e}"))
        else:
            program_count = 0

        if self.config.get("preferences", {}).get("check_drivers", True):
            self.root.after(0, lambda: self.set_status("Checking driver updates..."))
            try:
                driver_updates = check_driver_updates()
                all_updates.extend(driver_updates)
                driver_count = len(driver_updates)
            except Exception as e:
                driver_count = 0
                self.root.after(0, lambda e=e: self.set_status(f"Driver check: {str(e)}"))
        else:
            driver_count = 0

        self.available_updates = all_updates

        self.root.after(0, lambda: self._populate_trees(program_count, driver_count))

        if self.config.get("preferences", {}).get("notifications_enabled", True):
            prog_updates = [u for u in all_updates if u.get("type") == "program"]
            drv_updates = [u for u in all_updates if u.get("type") == "driver"]
            notify_updates_available(len(prog_updates), len(drv_updates))

    def _populate_trees(self, program_count, driver_count):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", value=0)

        for item in self.prog_tree.get_children():
            self.prog_tree.delete(item)
        for item in self.drv_tree.get_children():
            self.drv_tree.delete(item)

        prog_updates = [u for u in self.available_updates if u.get("type") == "program"]
        drv_updates = [u for u in self.available_updates if u.get("type") == "driver"]

        for u in prog_updates:
            self.prog_tree.insert("", END, values=(
                "",
                u.get("name", ""),
                u.get("current_version", ""),
                u.get("available_version", ""),
                u.get("source", "")
            ))

        from modules.driver_checker import group_drivers_by_category, CATEGORY_ORDER
        grouped = group_drivers_by_category(drv_updates)

        for cat in CATEGORY_ORDER:
            devices = grouped.get(cat, [])
            if not devices:
                continue
            cat_id = self.drv_tree.insert("", END, text=f"  {cat}  ({len(devices)})", values=("", "", ""), open=True)
            for d in devices:
                self.drv_tree.insert(cat_id, END, text=d.get("name", ""), values=(
                    "",
                    d.get("provider", ""),
                    d.get("version", "")
                ))

        self.set_count(len(prog_updates), len(drv_updates))
        self.update_btn_states(checking=False)

        total = len(self.available_updates)
        if total == 0:
            self.set_status("No updates found. All programs and drivers are up to date.")
        else:
            self.set_status(f"Found {total} update(s) available. Select items and click 'Install Selected'.")

    def install_selected(self):
        if self.is_installing or len(self.selected_updates) == 0:
            return

        if not is_admin():
            result = messagebox.askyesno(
                "Administrator Privileges Required",
                "Installing updates requires administrator privileges.\n\n"
                "The application needs to restart with admin rights.\n"
                "Continue?"
            )
            if result:
                request_admin()
            return

        count = len(self.selected_updates)
        result = messagebox.askyesno(
            "Confirm Installation",
            f"Are you sure you want to install {count} selected update(s)?\n\n"
            f"System restore points will be created before each installation."
        )
        if not result:
            return

        self.update_btn_states(installing=True)
        self.progress_bar.configure(mode="determinate", maximum=count, value=0)
        self.set_status(f"Installing {count} update(s)...")

        self.update_manager.install_updates(
            self.selected_updates,
            progress_callback=self.on_install_progress,
            status_callback=self.on_install_status,
            finished_callback=self.on_install_finished
        )

    def on_install_progress(self, current, total):
        self.progress_bar.configure(maximum=total, value=current)
        self.root.update_idletasks()

    def on_install_status(self, message):
        self.set_status(message)

    def on_install_finished(self, results, cancelled=False):
        self.update_btn_states(installing=False)
        self.progress_bar.configure(value=0)

        if cancelled:
            self.set_status("Installation cancelled.")
            return

        success_count = sum(1 for r in results if r.get("success"))
        fail_count = sum(1 for r in results if not r.get("success"))

        if fail_count > 0:
            self.set_status(f"Installation complete: {success_count} succeeded, {fail_count} failed.")
            messagebox.showwarning(
                "Installation Results",
                f"Installation complete.\n\n"
                f"Successful: {success_count}\n"
                f"Failed: {fail_count}\n\n"
                f"Check history for details."
            )
        else:
            self.set_status(f"All {success_count} update(s) installed successfully.")
            messagebox.showinfo(
                "Installation Complete",
                f"All {success_count} update(s) installed successfully."
            )

        self.selected_updates = []
        for item in self.prog_tree.get_children():
            self.prog_tree.set(item, "select", "")
        for cat_item in self.drv_tree.get_children():
            for child in self.drv_tree.get_children(cat_item):
                self.drv_tree.set(child, "select", "")

    def cancel_operation(self):
        self.update_manager.cancel()
        self.set_status("Cancelling...")

    def open_settings(self):
        SettingsDialog(self.root, self.config)

    def open_history(self):
        HistoryWindow(self.root)

    def clear_history_confirm(self):
        result = messagebox.askyesno(
            "Clear History",
            "Are you sure you want to clear all update history?\n\nThis action cannot be undone."
        )
        if result:
            clear_history()
            self.set_status("Update history cleared.")

    def sync_synology(self):
        if not self.config.get("synology", {}).get("quickconnect_id"):
            messagebox.showinfo("Synology Sync", "Synology not configured. Configure it in Tools > Settings first.")
            return

        self.set_status("Syncing with Synology...")
        self.update_btn_states(checking=True)

        thread = threading.Thread(target=self._sync_synology_worker, daemon=True)
        thread.start()

    def _sync_synology_worker(self):
        test = test_synology(self.config)
        if not test["success"]:
            self.root.after(0, lambda: self.set_status(f"Synology connection failed: {test.get('error', 'Unknown error')}"))
            self.root.after(0, lambda: self.update_btn_states(checking=False))
            self.root.after(0, lambda: messagebox.showerror("Synology Sync", f"Connection failed:\n{test.get('error', 'Unknown error')}"))
            return

        download_from_synology(self.config)
        result = sync_to_synology(self.config)

        self.root.after(0, lambda: self._sync_synology_done(result))

    def _sync_synology_done(self, result):
        self.update_btn_states(checking=False)
        if result["success"]:
            self.set_status("Synced to Synology successfully.")
            messagebox.showinfo("Synology Sync", "Database synced to Synology Drive successfully.")
        else:
            self.set_status(f"Synology sync failed: {result.get('error', '')}")
            messagebox.showerror("Synology Sync", f"Sync failed:\n{result.get('error', 'Unknown error')}")

    def sync_github(self):
        if not self.config.get("github", {}).get("personal_access_token"):
            messagebox.showinfo("GitHub Sync", "GitHub not configured. Configure it in Tools > Settings first.")
            return

        self.set_status("Syncing with GitHub...")
        self.update_btn_states(checking=True)

        thread = threading.Thread(target=self._sync_github_worker, daemon=True)
        thread.start()

    def _sync_github_worker(self):
        test = test_github(self.config)
        if not test["success"]:
            self.root.after(0, lambda: self.set_status(f"GitHub connection failed: {test.get('error', 'Unknown error')}"))
            self.root.after(0, lambda: self.update_btn_states(checking=False))
            self.root.after(0, lambda: messagebox.showerror("GitHub Sync", f"Connection failed:\n{test.get('error', 'Unknown error')}"))
            return

        result = github_full_sync(self.config)
        self.root.after(0, lambda: self._sync_github_done(result))

    def _sync_github_done(self, result):
        self.update_btn_states(checking=False)
        if result.get("success"):
            src = result.get("source", {})
            db = result.get("database", {})
            uploaded = ", ".join(src.get("uploaded", []))
            merged = db.get("merged", 0)
            msg = f"Source files uploaded: {len(src.get('uploaded', []))}\nDatabase entries merged: {merged}"
            self.set_status("Synced to GitHub successfully.")
            messagebox.showinfo("GitHub Sync", f"Sync completed successfully.\n\n{msg}")
        else:
            self.set_status(f"GitHub sync failed: {result.get('error', '')}")
            messagebox.showerror("GitHub Sync", f"Sync failed:\n{result.get('error', 'Unknown error')}")

    def show_about(self):
        messagebox.showinfo(
            "About UpdateChecker",
            "UpdateChecker v1.0.0\n\n"
            "Portable Update Manager for Windows\n\n"
            "Checks for program and driver updates,\n"
            "creates system restore points, and\n"
            "syncs history to Synology and GitHub.\n\n"
            "Built with Python, Tkinter, and Winget."
        )


def main():
    if not is_admin():
        result = messagebox.askyesno(
            "Administrator Privileges",
            "UpdateChecker runs best with administrator privileges.\n\n"
            "Some features (driver checks, restore points) require admin rights.\n"
            "Restart with administrator privileges?"
        )
        if result:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
            return

    root = Tk()
    app = UpdateCheckerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
