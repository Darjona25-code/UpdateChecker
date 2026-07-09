import os
import tempfile
from . import database

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


DB_PATH = database.DB_PATH


def test_connection(config):
    if not HAS_REQUESTS:
        return {"success": False, "error": "requests library not installed."}

    syn = config.get("synology", {})
    qid = syn.get("quickconnect_id", "")
    username = syn.get("username", "")
    password = syn.get("password", "")

    if not qid or not username or not password:
        return {"success": False, "error": "Synology credentials not configured."}

    base_url = f"https://{qid}.quickconnect.to"
    remote_path = syn.get("remote_path", "/UpdateChecker/update_history.db")
    webdav_url = f"{base_url}:5006{remote_path}"

    try:
        response = requests.request(
            "PROPFIND", webdav_url,
            auth=(username, password),
            timeout=15,
            headers={"Depth": "0"}
        )
        if response.status_code in (200, 207, 404):
            return {"success": True, "error": None}
        else:
            return {"success": False, "error": f"WebDAV returned status {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to Synology. Check QuickConnect ID and network."}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Connection to Synology timed out."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def upload_to_synology(config):
    if not HAS_REQUESTS:
        return {"success": False, "error": "requests library not installed."}

    syn = config.get("synology", {})
    qid = syn.get("quickconnect_id", "")
    username = syn.get("username", "")
    password = syn.get("password", "")
    remote_path = syn.get("remote_path", "/UpdateChecker/update_history.db")

    if not qid or not username or not password:
        return {"success": False, "error": "Synology credentials not configured."}

    if not os.path.exists(DB_PATH):
        return {"success": False, "error": "Local database not found."}

    base_url = f"https://{qid}.quickconnect.to"
    webdav_url = f"{base_url}:5006{remote_path}"

    try:
        with open(DB_PATH, "rb") as f:
            response = requests.put(
                webdav_url,
                auth=(username, password),
                data=f,
                timeout=60,
                headers={"Content-Type": "application/octet-stream"}
            )

        if response.status_code in (200, 201, 204):
            return {"success": True, "error": None}
        elif response.status_code == 401:
            return {"success": False, "error": "Authentication failed. Check username and password."}
        elif response.status_code == 404:
            return {"success": False, "error": "Remote path not found. Check remote_path setting."}
        else:
            return {"success": False, "error": f"Upload failed with status {response.status_code}"}

    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to Synology."}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Upload timed out."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def download_from_synology(config):
    if not HAS_REQUESTS:
        return {"success": False, "error": "requests library not installed."}

    syn = config.get("synology", {})
    qid = syn.get("quickconnect_id", "")
    username = syn.get("username", "")
    password = syn.get("password", "")
    remote_path = syn.get("remote_path", "/UpdateChecker/update_history.db")

    if not qid or not username or not password:
        return {"success": False, "error": "Synology credentials not configured."}

    base_url = f"https://{qid}.quickconnect.to"
    webdav_url = f"{base_url}:5006{remote_path}"

    try:
        response = requests.get(
            webdav_url,
            auth=(username, password),
            timeout=30
        )

        if response.status_code == 200:
            tmp_dir = tempfile.gettempdir()
            tmp_path = os.path.join(tmp_dir, "update_history_synology.db")
            with open(tmp_path, "wb") as f:
                f.write(response.content)

            merged = database.merge_from_github(tmp_path)
            os.remove(tmp_path)

            return {"success": True, "merged": merged, "error": None}
        elif response.status_code == 404:
            return {"success": False, "error": "No remote database found on Synology.", "not_found": True}
        elif response.status_code == 401:
            return {"success": False, "error": "Authentication failed."}
        else:
            return {"success": False, "error": f"Download failed with status {response.status_code}"}

    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to Synology."}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Download timed out."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def sync_to_synology(config):
    upload_result = upload_to_synology(config)
    return upload_result
