import os
import shutil
import zipfile
import requests
import subprocess
import sys
import json
import config

class Updater:
    """Handles the application update process from GitHub."""
    
    def __init__(self, repo=config.GITHUB_REPO):
        self.repo = repo
        self.api_url = f"https://api.github.com/repos/{repo}"
        self.download_url = f"https://github.com/{repo}/archive/refs/heads/main.zip"
        self.backup_dir = os.path.join(os.path.dirname(__file__), "backups", "last_update")
        self.temp_dir = os.path.join(os.path.dirname(__file__), "temp_update")
        self.metadata_file = os.path.join(self.backup_dir, "metadata.json")

    def check_for_update(self):
        """Checks if a new commit is available on the main branch."""
        try:
            response = requests.get(f"{self.api_url}/commits/main", timeout=10)
            if response.status_code == 200:
                latest_sha = response.json().get("sha")
                current_sha, build_date = self._get_version_info()
                
                # Bootstrap: If local SHA is uninitialized ("main"), sync it without flagging an update.
                # This fixes the "Update Available" false positive for new installations.
                if current_sha == "main":
                    self._save_version_info(latest_sha, build_date)
                    return False, latest_sha
                
                return latest_sha != current_sha, latest_sha
            return False, None
        except Exception as e:
            print(f"Update check failed: {e}")
            return False, None

    def download_update(self):
        """Downloads the latest code as a ZIP file."""
        try:
            if not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir)
            
            response = requests.get(self.download_url, stream=True, timeout=30)
            zip_path = os.path.join(self.temp_dir, "update.zip")
            with open(zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as e:
            print(f"Download failed: {e}")
            return False

    def create_backup(self):
        """Backs up the current .py files."""
        try:
            if os.path.exists(self.backup_dir):
                shutil.rmtree(self.backup_dir)
            os.makedirs(self.backup_dir)
            
            root_dir = os.path.dirname(__file__)
            files_to_backup = [f for f in os.listdir(root_dir) if f.endswith(".py")]
            
            for file in files_to_backup:
                shutil.copy2(os.path.join(root_dir, file), os.path.join(self.backup_dir, file))
            
            # Save metadata
            sha, build_date = self._get_version_info()
            with open(self.metadata_file, "w") as f:
                json.dump({"current_sha": sha, "build_date": build_date}, f)
            return True
        except Exception as e:
            print(f"Backup failed: {e}")
            return False

    def apply_update(self, new_sha):
        """Extracts the ZIP and overwrites existing files."""
        try:
            zip_path = os.path.join(self.temp_dir, "update.zip")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)
            
            # GitHub ZIPs wrap content in a folder like 'repo-main'
            extracted_folder = os.path.join(self.temp_dir, f"{self.repo.split('/')[-1]}-main")
            root_dir = os.path.dirname(__file__)
            
            for item in os.listdir(extracted_folder):
                s = os.path.join(extracted_folder, item)
                d = os.path.join(root_dir, item)
                if os.path.isdir(s):
                    if os.path.exists(d): shutil.rmtree(d)
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
            
            # Update the stored version info
            from datetime import datetime
            build_date = datetime.now().strftime("%Y-%m-%d")
            self._save_version_info(new_sha, build_date)
            
            # Cleanup
            shutil.rmtree(self.temp_dir)
            return True
        except Exception as e:
            print(f"Apply failed: {e}")
            return False

    def revert_update(self):
        """Restores files from the backup directory."""
        try:
            if not os.path.exists(self.backup_dir):
                return False
            
            root_dir = os.path.dirname(__file__)
            files_in_backup = [f for f in os.listdir(self.backup_dir) if f.endswith(".py")]
            
            for file in files_in_backup:
                shutil.copy2(os.path.join(self.backup_dir, file), os.path.join(root_dir, file))
            
            # Restore local SHA from metadata if possible
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, "r") as f:
                    meta = json.load(f)
                    self._save_version_info(
                        meta.get("current_sha", config.CURRENT_SHA),
                        meta.get("build_date", config.BUILD_DATE)
                    )
            
            return True
        except Exception as e:
            print(f"Revert failed: {e}")
            return False

    def _get_version_info(self):
        """Retrieves the currently stored SHA and Build Date."""
        settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
        sha = config.CURRENT_SHA
        build_date = config.BUILD_DATE
        try:
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                    sha = settings.get("current_sha", sha)
                    build_date = settings.get("build_date", build_date)
        except:
            pass
        return sha, build_date

    def _save_version_info(self, sha, build_date):
        """Persists the new SHA and Build Date to settings.json."""
        settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
        try:
            settings = {}
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    settings = json.load(f)
            settings["current_sha"] = sha
            settings["build_date"] = build_date
            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Failed to save version info: {e}")

    def restart_app(self):
        """Restarts the current Python script."""
        python = sys.executable
        os.execl(python, python, *sys.argv)
