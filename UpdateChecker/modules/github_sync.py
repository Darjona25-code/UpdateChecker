import os
import tempfile
from datetime import datetime
from . import database

try:
    from github import Github, GithubException
    HAS_PYGITHUB = True
except ImportError:
    HAS_PYGITHUB = False


DB_PATH = database.DB_PATH
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_github_client(config):
    token = config.get("github", {}).get("personal_access_token", "")
    if not token:
        return None, "GitHub token not configured."
    if not HAS_PYGITHUB:
        return None, "PyGithub library not installed."
    try:
        g = Github(token)
        user = g.get_user()
        return g, None
    except GithubException as e:
        return None, f"GitHub authentication failed: {e.data.get('message', str(e))}"
    except Exception as e:
        return None, str(e)


def _get_or_create_repo(g, config):
    repo_name = config.get("github", {}).get("repo_name", "UpdateChecker-Backup")
    branch = config.get("github", {}).get("branch", "main")

    try:
        user = g.get_user()
        try:
            repo = user.get_repo(repo_name)
            return repo, None
        except GithubException:
            repo = user.create_repo(repo_name, private=True, auto_init=True)
            return repo, None
    except GithubException as e:
        return None, f"Repository error: {e.data.get('message', str(e))}"
    except Exception as e:
        return None, str(e)


def _get_file_content(repo, path, branch="main"):
    try:
        contents = repo.get_contents(path, ref=branch)
        return contents.decoded_content, contents.sha
    except GithubException:
        return None, None


def _create_or_update_file(repo, path, content, message, branch="main"):
    try:
        existing_content, sha = _get_file_content(repo, path, branch)
        if existing_content is not None:
            repo.update_file(path, message, content, sha, branch=branch)
        else:
            repo.create_file(path, message, content, branch=branch)
        return True, None
    except GithubException as e:
        return False, str(e)


def _get_source_files():
    files = []
    main_py = os.path.join(BASE_DIR, "main.py")
    config_json = os.path.join(BASE_DIR, "config.json")
    requirements = os.path.join(BASE_DIR, "requirements.txt")

    if os.path.exists(main_py):
        files.append(("main.py", main_py))
    if os.path.exists(config_json):
        files.append(("config.json", config_json))
    if os.path.exists(requirements):
        files.append(("requirements.txt", requirements))

    modules_dir = os.path.join(BASE_DIR, "modules")
    if os.path.isdir(modules_dir):
        for f in sorted(os.listdir(modules_dir)):
            if f.endswith(".py"):
                files.append((f"modules/{f}", os.path.join(modules_dir, f)))

    return files


def test_connection(config):
    g, error = _get_github_client(config)
    if error:
        return {"success": False, "error": error}
    try:
        user = g.get_user()
        return {"success": True, "error": None, "login": user.login}
    except Exception as e:
        return {"success": False, "error": str(e)}


def sync_source_code(config):
    g, error = _get_github_client(config)
    if error:
        return {"success": False, "error": error}

    repo, error = _get_or_create_repo(g, config)
    if error:
        return {"success": False, "error": error}

    branch = config.get("github", {}).get("branch", "main")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_message = f"UpdateChecker sync - {timestamp}"

    source_files = _get_source_files()
    uploaded = []
    failed = []

    for remote_path, local_path in source_files:
        with open(local_path, "rb") as f:
            content = f.read()
        success, err = _create_or_update_file(repo, remote_path, content, commit_message, branch)
        if success:
            uploaded.append(remote_path)
        else:
            failed.append((remote_path, err))

    return {
        "success": len(failed) == 0,
        "uploaded": uploaded,
        "failed": failed,
        "error": f"Failed: {len(failed)} files" if failed else None
    }


def sync_database(config):
    g, error = _get_github_client(config)
    if error:
        return {"success": False, "error": error}

    repo, error = _get_or_create_repo(g, config)
    if error:
        return {"success": False, "error": error}

    branch = config.get("github", {}).get("branch", "main")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_message = f"UpdateChecker database sync - {timestamp}"

    remote_content, _ = _get_file_content(repo, "update_history.db", branch)
    merged_count = 0

    if remote_content:
        tmp_dir = tempfile.gettempdir()
        tmp_path = os.path.join(tmp_dir, "update_history_github.db")
        with open(tmp_path, "wb") as f:
            f.write(remote_content)
        merged_count = database.merge_from_github(tmp_path)
        os.remove(tmp_path)

    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            db_content = f.read()
        success, err = _create_or_update_file(repo, "update_history.db", db_content, commit_message, branch)
        if success:
            result = {"success": True, "merged": merged_count, "error": None}
        else:
            result = {"success": False, "error": err}
    else:
        result = {"success": False, "error": "Local database not found."}

    return result


def full_sync(config):
    source_result = sync_source_code(config)
    db_result = sync_database(config)

    return {
        "source": source_result,
        "database": db_result,
        "success": source_result.get("success", False) and db_result.get("success", False),
        "error": None if source_result.get("success") and db_result.get("success")
                 else f"Source: {source_result.get('error')} | DB: {db_result.get('error')}"
    }
