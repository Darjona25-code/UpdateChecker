import subprocess
import re


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


def check_driver_updates():
    all_drivers = []

    ps_script = """
    $drivers = Get-WindowsDriver -Online -ErrorAction SilentlyContinue
    $result = @()
    foreach ($d in $drivers) {
        $result += [PSCustomObject]@{
            DriverName = $d.Driver
            ProviderName = $d.ProviderName
            Version = $d.Version
            ClassName = $d.ClassName
            BootCritical = $d.BootCritical
            OriginalFileName = $d.OriginalFileName
        }
    }
    $result | ConvertTo-Json -Compress
    """

    ps_result = _run_powershell(ps_script)
    if ps_result["success"] and ps_result["stdout"].strip():
        try:
            import json
            drivers = json.loads(ps_result["stdout"])
            if not isinstance(drivers, list):
                drivers = [drivers]
            for d in drivers:
                if isinstance(d, dict):
                    all_drivers.append({
                        "name": d.get("DriverName", "Unknown"),
                        "provider": d.get("ProviderName", "Unknown"),
                        "version": d.get("Version", "Unknown"),
                        "class": d.get("ClassName", "Unknown"),
                        "type": "driver"
                    })
        except json.JSONDecodeError:
            pass

    ps_device_script = """
    $devices = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.Class -ne 'SoftwareDevice' -and $_.Status -eq 'OK' }
    $result = @()
    foreach ($d in $devices) {
        $driver = Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName '{a8b865dd-2e3d-4094-ad97-e593a70c75d6},6' -ErrorAction SilentlyContinue
        $driverVer = Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName '{a8b865dd-2e3d-4094-ad97-e593a70c75d6},7' -ErrorAction SilentlyContinue
        $result += [PSCustomObject]@{
            DeviceName = $d.FriendlyName
            Class = $d.Class
            Status = $d.Status
            DriverVersion = if ($driverVer.Data) { $driverVer.Data } else { 'N/A' }
            DriverProvider = if ($driver.Data) { $driver.Data } else { 'N/A' }
        }
    }
    $result | ConvertTo-Json -Compress
    """

    ps_device_result = _run_powershell(ps_device_script)
    if ps_device_result["success"] and ps_device_result["stdout"].strip():
        try:
            import json
            devices = json.loads(ps_device_result["stdout"])
            if not isinstance(devices, list):
                devices = [devices]
            for d in devices:
                if isinstance(d, dict) and d.get("DeviceName"):
                    existing = next((x for x in all_drivers if x["name"] == d["DeviceName"]), None)
                    if not existing:
                        all_drivers.append({
                            "name": d["DeviceName"],
                            "provider": d.get("DriverProvider", "Unknown"),
                            "version": d.get("DriverVersion", "Unknown"),
                            "class": d.get("Class", "Unknown"),
                            "type": "driver"
                        })
        except json.JSONDecodeError:
            pass

    ps_wu_script = """
    try {
        $updateSession = New-Object -ComObject Microsoft.Update.Session
        $updateSearcher = $updateSession.CreateUpdateSearcher()
        $searchResult = $updateSearcher.Search("IsInstalled=0 and Type='Driver'")
        $result = @()
        foreach ($update in $searchResult.Updates) {
            $result += [PSCustomObject]@{
                Title = $update.Title
                Description = $update.Description
                IsDownloaded = $update.IsDownloaded
                IsMandatory = $update.IsMandatory
                KBArticleIDs = ($update.KBArticleIDs -join ',')
            }
        }
        if ($result.Count -gt 0) { $result | ConvertTo-Json -Compress } else { '[]' }
    } catch {
        '[]'
    }
    """

    ps_wu_result = _run_powershell(ps_wu_script)
    if ps_wu_result["success"] and ps_wu_result["stdout"].strip():
        try:
            import json
            wu_updates = json.loads(ps_wu_result["stdout"])
            if not isinstance(wu_updates, list):
                wu_updates = [wu_updates]
            for u in wu_updates:
                if isinstance(u, dict) and u.get("Title"):
                    existing = next((x for x in all_drivers if x["name"] == u["Title"]), None)
                    if not existing:
                        all_drivers.append({
                            "name": u["Title"],
                            "provider": "Windows Update",
                            "version": "N/A",
                            "class": "Windows Update Driver",
                            "type": "driver",
                            "available": "Available"
                        })
        except json.JSONDecodeError:
            pass

    if not all_drivers:
        fallback_drivers = _get_fallback_drivers()
        all_drivers.extend(fallback_drivers)

    return all_drivers


def _get_fallback_drivers():
    fallback = []
    ps_script = """
    Get-CimInstance -ClassName Win32_PnPSignedDriver | Select-Object DeviceName, DriverVersion, DriverProviderName, ClassName | ConvertTo-Json -Compress
    """
    result = _run_powershell(ps_script)
    if result["success"] and result["stdout"].strip():
        try:
            import json
            devices = json.loads(result["stdout"])
            if not isinstance(devices, list):
                devices = [devices]
            for d in devices:
                if isinstance(d, dict) and d.get("DeviceName"):
                    fallback.append({
                        "name": d["DeviceName"],
                        "provider": d.get("DriverProviderName", "Unknown"),
                        "version": d.get("DriverVersion", "Unknown"),
                        "class": d.get("ClassName", "Unknown"),
                        "type": "driver"
                    })
        except json.JSONDecodeError:
            pass
    return fallback


def get_driver_categories():
    return [
        "Display", "Network", "Audio", "System", "Storage", "USB",
        "Printer", "Bluetooth", "Keyboard", "Mouse", "Other"
    ]


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
