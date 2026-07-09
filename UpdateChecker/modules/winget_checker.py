import subprocess
import json
import re


def is_winget_installed():
    try:
        subprocess.run(["winget", "--version"], capture_output=True, check=True, timeout=10)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def get_winget_version():
    try:
        result = subprocess.run(["winget", "--version"], capture_output=True, text=True, check=True, timeout=10)
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def check_program_updates():
    if not is_winget_installed():
        return {"success": False, "error": "Winget is not installed on this system.", "updates": []}

    try:
        result = subprocess.run(
            ["winget", "list", "--upgrade-available", "--accept-source-agreements"],
            capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            return {"success": False, "error": f"Winget exited with code {result.returncode}: {result.stderr.strip()}", "updates": []}

        updates = parse_winget_output(result.stdout)
        return {"success": True, "error": None, "updates": updates}

    except FileNotFoundError:
        return {"success": False, "error": "Winget executable not found.", "updates": []}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Winget check timed out.", "updates": []}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}", "updates": []}


def parse_winget_output(output):
    updates = []
    lines = output.strip().split("\n")

    headers_found = False
    header_indices = {}
    column_names = ["Name", "Id", "Version", "Available", "Source"]

    for i, line in enumerate(lines):
        if "Name" in line and "Id" in line and "Version" in line and "Available" in line:
            headers_found = True
            parts = re.split(r"\s{2,}", line)
            for col_name in column_names:
                for j, part in enumerate(parts):
                    if part.strip() == col_name:
                        header_indices[col_name] = j
                        break
            continue

        if headers_found:
            line = line.strip()
            if not line or line.startswith("-"):
                continue

            parts = re.split(r"\s{2,}", line)
            if len(parts) >= 4:
                name = parts[header_indices.get("Name", 0)].strip() if header_indices.get("Name", 0) < len(parts) else ""
                pkg_id = parts[header_indices.get("Id", 1)].strip() if header_indices.get("Id", 1) < len(parts) else ""
                current_ver = parts[header_indices.get("Version", 2)].strip() if header_indices.get("Version", 2) < len(parts) else ""
                available_ver = parts[header_indices.get("Available", 3)].strip() if header_indices.get("Available", 3) < len(parts) else ""
                source = parts[header_indices.get("Source", 4)].strip() if header_indices.get("Source", 4) < len(parts) else ""

                if name and available_ver:
                    updates.append({
                        "name": name,
                        "package_id": pkg_id,
                        "current_version": current_ver,
                        "available_version": available_ver,
                        "source": source,
                        "type": "program"
                    })

    return updates


def install_program_update(package_id):
    try:
        result = subprocess.run(
            ["winget", "upgrade", "--id", package_id, "--silent", "--accept-package-agreements", "--accept-source-agreements"],
            capture_output=True, text=True, timeout=300
        )

        if result.returncode == 0:
            return {"success": True, "message": f"Successfully installed {package_id}"}
        else:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            if "0x8" in error_msg or "0x1" in error_msg:
                return {"success": False, "message": f"Installation may have failed or was cancelled: {error_msg}"}
            return {"success": False, "message": f"Installation error: {error_msg}"}

    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Installation timed out (300 seconds)."}
    except FileNotFoundError:
        return {"success": False, "message": "Winget executable not found."}
    except Exception as e:
        return {"success": False, "message": f"Unexpected error: {str(e)}"}
