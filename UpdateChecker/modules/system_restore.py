import subprocess
import platform
from datetime import datetime


def is_restore_point_enabled():
    ps_script = """
    $status = Get-ComputerRestorePoint -ErrorAction SilentlyContinue
    if ($status) { Write-Output "ENABLED" } else {
        $vss = Get-CimInstance -ClassName Win32_ShadowStorage -ErrorAction SilentlyContinue
        if ($vss) { Write-Output "ENABLED" } else { Write-Output "DISABLED" }
    }
    """
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, timeout=30
        )
        return "ENABLED" in result.stdout
    except:
        return False


def create_restore_point(description=None):
    if not description:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        computer = platform.node()
        description = f"UpdateChecker - {timestamp} - {computer}"

    ps_script = f"""
    try {{
        Checkpoint-Computer -Description "{description}" -RestorePointType MODIFY_SETTINGS -ErrorAction Stop
        Write-Output "SUCCESS"
    }} catch {{
        try {{
            Checkpoint-Computer -Description "{description}" -RestorePointType APPLICATION_INSTALL -ErrorAction Stop
            Write-Output "SUCCESS"
        }} catch {{
            Write-Output "FAILED: $($_.Exception.Message)"
        }}
    }}
    """

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, timeout=120
        )

        output = result.stdout.strip()

        if "SUCCESS" in output:
            return {"success": True, "message": "Restore point created successfully.", "description": description}
        else:
            return {"success": False, "message": output, "description": description}

    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Restore point creation timed out.", "description": description}
    except FileNotFoundError:
        return {"success": False, "message": "PowerShell not available.", "description": description}
    except Exception as e:
        return {"success": False, "message": str(e), "description": description}


def enable_system_restore(drive="C:"):
    ps_script = f"""
    try {{
        Enable-ComputerRestore -Drive "{drive}" -ErrorAction Stop
        Write-Output "SUCCESS"
    }} catch {{
        Write-Output "FAILED: $($_.Exception.Message)"
    }}
    """
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, timeout=30
        )
        return "SUCCESS" in result.stdout
    except:
        return False
