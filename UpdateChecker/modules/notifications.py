import threading


try:
    from win10toast import ToastNotifier
    HAS_TOAST = True
except ImportError:
    HAS_TOAST = False


_notifier = None


def _get_notifier():
    global _notifier
    if not HAS_TOAST:
        return None
    if _notifier is None:
        _notifier = ToastNotifier()
    return _notifier


def show_notification(title, message, duration=5, threaded=True):
    def _show():
        notifier = _get_notifier()
        if notifier:
            try:
                notifier.show_toast(title, message, duration=duration, threaded=False)
            except Exception:
                pass

    if threaded:
        thread = threading.Thread(target=_show, daemon=True)
        thread.start()
    else:
        _show()


def notify_updates_available(program_count=0, driver_count=0):
    total = program_count + driver_count
    if total == 0:
        return
    title = "UpdateChecker"
    if program_count > 0 and driver_count > 0:
        message = f"{total} updates available: {program_count} programs, {driver_count} drivers"
    elif program_count > 0:
        message = f"{program_count} program update(s) available"
    else:
        message = f"{driver_count} driver update(s) available"
    show_notification(title, message)


def notify_update_installed(name, success=True):
    title = "UpdateChecker"
    if success:
        message = f"Successfully installed: {name}"
    else:
        message = f"Failed to install: {name}"
    show_notification(title, message)


def notify_sync_complete(target, success=True):
    title = "UpdateChecker"
    target_name = "Synology" if target == "synology" else "GitHub"
    if success:
        message = f"Sync to {target_name} completed successfully"
    else:
        message = f"Sync to {target_name} failed"
    show_notification(title, message)
