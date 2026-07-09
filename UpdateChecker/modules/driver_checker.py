import subprocess
import json


def _run_powershell(script):
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=120
        )
        return {"success": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
    except FileNotFoundError:
        return {"success": False, "error": "PowerShell not found."}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "PowerShell command timed out."}
    except Exception as e:
        return {"success": False, "error": str(e)}


CLASS_CATEGORY_MAP = {
    "Display": "Display",
    "Network": "Network",
    "Net": "Network",
    "Audio": "Audio",
    "Media": "Audio",
    "System": "Chipset",
    "CPU": "Chipset",
    "Power": "Chipset",
    "Battery": "Chipset",
    "DiskDrive": "Storage",
    "Storage": "Storage",
    "HDC": "Storage",
    "SCSIAdapter": "Storage",
    "USB": "USB",
    "USBDevice": "USB",
    "Ports": "USB",
    "Printer": "Printers",
    "Bluetooth": "Bluetooth",
    "Keyboard": "Input",
    "Mouse": "Input",
    "HIDClass": "Input",
    "Point": "Input",
    "Camera": "Camera",
    "Image": "Camera",
    "FDC": "Other",
    "CDROM": "Other",
    "Volume": "Other",
    "Computer": "Other",
    "SoftwareDevice": "Other",
    "Extension": "Other",
    "Sensor": "Other",
    "Biometric": "Other",
    "SmartCard": "Other",
    "Security": "Other",
    "Tpm": "Other",
}


def map_class_to_category(device_class):
    if not device_class:
        return "Other"
    for key, cat in CLASS_CATEGORY_MAP.items():
        if key.lower() in device_class.lower() or device_class.lower() in key.lower():
            return cat
    return "Other"


def check_driver_updates():
    all_drivers = []

    devices = _get_pnp_devices()
    all_drivers.extend(devices)

    wu_drivers = _check_windows_update_drivers()
    existing_names = {d["name"] for d in all_drivers}

    for wu_d in wu_drivers:
        if wu_d["name"] not in existing_names:
            all_drivers.append(wu_d)

    return all_drivers


def _get_pnp_devices():
    ps_script = """
    $devices = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
        Where-Object { $_.Class -ne 'SoftwareDevice' -and $_.Status -eq 'OK' -and $_.FriendlyName -ne $null }
    $result = @()
    foreach ($d in $devices) {
        $driverVer = Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName '{a8b865dd-2e3d-4094-ad97-e593a70c75d6},7' -ErrorAction SilentlyContinue
        $driverProvider = Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName '{a8b865dd-2e3d-4094-ad97-e593a70c75d6},6' -ErrorAction SilentlyContinue
        $result += [PSCustomObject]@{
            DeviceName = $d.FriendlyName
            Class = if ($d.Class) { $d.Class } else { 'Other' }
            DriverVersion = if ($driverVer.Data) { $driverVer.Data } else { 'N/A' }
            DriverProvider = if ($driverProvider.Data) { $driverProvider.Data } else { 'Unknown' }
        }
    }
    $result | ConvertTo-Json -Compress
    """

    result = _run_powershell(ps_script)
    devices = []

    if result["success"] and result["stdout"].strip():
        try:
            data = json.loads(result["stdout"])
            if not isinstance(data, list):
                data = [data]
            for d in data:
                if isinstance(d, dict) and d.get("DeviceName"):
                    device_class = d.get("Class", "Other")
                    devices.append({
                        "name": d["DeviceName"],
                        "provider": d.get("DriverProvider", "Unknown"),
                        "version": d.get("DriverVersion", "N/A"),
                        "class": device_class,
                        "category": map_class_to_category(device_class),
                        "type": "driver"
                    })
        except json.JSONDecodeError:
            pass

    return devices


def _check_windows_update_drivers():
    ps_script = """
    try {
        $updateSession = New-Object -ComObject Microsoft.Update.Session
        $updateSearcher = $updateSession.CreateUpdateSearcher()
        $searchResult = $updateSearcher.Search("IsInstalled=0 and Type='Driver'")
        $result = @()
        foreach ($update in $searchResult.Updates) {
            $categories = @()
            foreach ($cat in $update.Categories) {
                $categories += $cat.Name
            }
            $result += [PSCustomObject]@{
                Title = $update.Title
                Categories = ($categories -join '; ')
            }
        }
        if ($result.Count -gt 0) { $result | ConvertTo-Json -Compress } else { '[]' }
    } catch {
        '[]'
    }
    """

    result = _run_powershell(ps_script)
    drivers = []

    if result["success"] and result["stdout"].strip():
        try:
            data = json.loads(result["stdout"])
            if not isinstance(data, list):
                data = [data]
            for u in data:
                if isinstance(u, dict) and u.get("Title"):
                    cat_name = u.get("Categories", "Other") or "Other"
                    drivers.append({
                        "name": u["Title"],
                        "provider": "Windows Update",
                        "version": "Available",
                        "class": cat_name,
                        "category": map_class_to_category(cat_name),
                        "type": "driver"
                    })
        except json.JSONDecodeError:
            pass

    return drivers


CATEGORY_ORDER = ["Display", "Network", "Audio", "Chipset", "Storage", "USB", "Bluetooth", "Printers", "Camera", "Input", "Other"]


def get_category_order():
    return CATEGORY_ORDER


def group_drivers_by_category(drivers):
    grouped = {}
    for cat in CATEGORY_ORDER:
        grouped[cat] = []
    for d in drivers:
        cat = d.get("category", "Other")
        if cat not in grouped:
            cat = "Other"
        grouped[cat].append(d)
    return grouped


def get_driver_categories():
    return list(CATEGORY_ORDER)


def install_driver_update(driver_name):
    ps_script = f"""
    try {{
        $updateSession = New-Object -ComObject Microsoft.Update.Session
        $updateSearcher = $updateSession.CreateUpdateSearcher()
        $searchResult = $updateSearcher.Search("IsInstalled=0 and Type='Driver'")
        $update = $searchResult.Updates | Where-Object {{ $_.Title -like '*{driver_name}*' }} | Select-Object -First 1
        if ($update) {{
            $downloader = $updateSession.CreateUpdateDownloader()
            $downloader.Updates = New-Object -ComObject Microsoft.Update.UpdateColl
            $downloader.Updates.Add($update) | Out-Null
            $downloadResult = $downloader.Download()
            if ($downloadResult.ResultCode -eq 2) {{
                $installer = $updateSession.CreateUpdateInstaller()
                $installer.Updates = $downloader.Updates
                $installResult = $installer.Install()
                if ($installResult.ResultCode -eq 2) {{
                    Write-Output "SUCCESS"
                }} else {{
                    Write-Output "FAILED: Install result code $($installResult.ResultCode)"
                }}
            }} else {{
                Write-Output "FAILED: Download result code $($downloadResult.ResultCode)"
            }}
        }} else {{
            Write-Output "SKIPPED: Driver not found in Windows Update"
        }}
    }} catch {{
        Write-Output "ERROR: $($_.Exception.Message)"
    }}
    """

    result = _run_powershell(ps_script)
    if result["success"]:
        output = result["stdout"].strip()
        if "SUCCESS" in output:
            return {"success": True, "message": f"Driver '{driver_name}' installed successfully."}
        elif "SKIPPED" in output:
            return {"success": False, "message": f"Driver '{driver_name}' not found in Windows Update."}
        else:
            return {"success": False, "message": output}
    else:
        return {"success": False, "message": result.get("error", "PowerShell execution failed.")}
