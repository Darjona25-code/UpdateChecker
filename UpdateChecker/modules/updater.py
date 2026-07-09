import threading
import platform
from datetime import datetime

from . import database
from . import winget_checker
from . import driver_checker
from . import system_restore
from . import notifications


class UpdateManager:
    def __init__(self, config):
        self.config = config
        self._cancel_flag = False
        self.computer_name = platform.node()

    def cancel(self):
        self._cancel_flag = True

    def install_updates(self, updates, progress_callback=None, status_callback=None, finished_callback=None):
        self._cancel_flag = False
        thread = threading.Thread(
            target=self._install_worker,
            args=(updates, progress_callback, status_callback, finished_callback),
            daemon=True
        )
        thread.start()
        return thread

    def _install_worker(self, updates, progress_callback, status_callback, finished_callback):
        results = []
        total = len(updates)

        for i, update in enumerate(updates):
            if self._cancel_flag:
                if status_callback:
                    status_callback("Installation cancelled by user.")
                if finished_callback:
                    finished_callback(results, cancelled=True)
                return

            name = update.get("name", "Unknown")
            update_type = update.get("type", "program")
            current_version = update.get("current_version", "")
            available_version = update.get("available_version", "")
            package_id = update.get("package_id", "")

            if status_callback:
                status_callback(f"Installing: {name}...")

            if progress_callback:
                progress_callback(i, total)

            restore_point_id = None
            if self.config.get("preferences", {}).get("create_restore_points", True):
                rp_description = f"UpdateChecker - {name} - {self.computer_name} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                if status_callback:
                    status_callback(f"Creating restore point before installing {name}...")
                rp_result = system_restore.create_restore_point(rp_description)
                if rp_result["success"]:
                    restore_point_id = rp_description

            if self._cancel_flag:
                if status_callback:
                    status_callback("Installation cancelled by user.")
                if finished_callback:
                    finished_callback(results, cancelled=True)
                return

            if update_type == "program" and package_id:
                if status_callback:
                    status_callback(f"Installing program: {name} via winget...")
                result = winget_checker.install_program_update(package_id)
            elif update_type == "driver":
                if status_callback:
                    status_callback(f"Installing driver: {name}...")
                result = driver_checker.install_driver_update(name)
            else:
                result = {"success": False, "message": "Unknown update type or missing package ID."}

            status = "installed" if result["success"] else "failed"

            database.log_update(
                name=name,
                update_type=update_type,
                old_version=current_version or "N/A",
                new_version=available_version or "N/A",
                status=status,
                restore_point_id=restore_point_id,
                computer_name=self.computer_name
            )

            notifications.notify_update_installed(name, success=result["success"])

            results.append({
                "name": name,
                "type": update_type,
                "success": result["success"],
                "message": result.get("message", ""),
                "status": status
            })

            if progress_callback:
                progress_callback(i + 1, total)

        if progress_callback:
            progress_callback(total, total)

        if status_callback:
            status_callback("All selected updates processed.")

        if finished_callback:
            finished_callback(results, cancelled=False)
