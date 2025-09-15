from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from concurrent.futures import ThreadPoolExecutor
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from email.mime.text import MIMEText
import smtplib
import hashlib
import time
import os
import shutil
from datetime import datetime
import json
import logging

# ===== Utils =====
def compute_hash(file_path):
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

# ===== Version Manager =====
class VersionManager:
    def __init__(self, base_path):
        self.version_dir = os.path.join(base_path, "versions")
        os.makedirs(self.version_dir, exist_ok=True)

    def save_version(self, file_path):
        file_name = os.path.basename(file_path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        versioned_file = f"{file_name}_{timestamp}"
        shutil.copy(file_path, os.path.join(self.version_dir, versioned_file))
        logging.info(f"📄 Version saved: {versioned_file}")

# ===== Uploader/Syncer =====
class Uploader:
    def __init__(self, mirror_dir):
        self.drive = None
        self.folder_cache = {}
        self.mirror_dir = mirror_dir
        os.makedirs(self.mirror_dir, exist_ok=True)
        self.authenticate_drive()

    def authenticate_drive(self):
        try:
            self.gauth = GoogleAuth()
            self.gauth.LoadCredentialsFile("mycreds.txt")

            if self.gauth.credentials is None:
                self.gauth.LocalWebserverAuth()
            elif self.gauth.access_token_expired:
                self.gauth.Refresh()
            else:
                self.gauth.Authorize()

            self.gauth.SaveCredentialsFile("mycreds.txt")
            self.drive = GoogleDrive(self.gauth)
            logging.info("✅ Google Drive authentication successful.")
        except Exception as e:
            self.drive = None
            logging.error(f"❌ Google Drive authentication failed: {str(e)}")

    def get_or_create_folder(self, folder_name, parent_id=None):
        key = (folder_name, parent_id)
        if key in self.folder_cache:
            return self.folder_cache[key]

        query = f"title='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        folders = self.drive.ListFile({'q': query}).GetList()
        if folders:
            folder_id = folders[0]['id']
        else:
            folder = self.drive.CreateFile({
                'title': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [{'id': parent_id}] if parent_id else []
            })
            folder.Upload()
            folder_id = folder['id']
            logging.info(f"📁 Created folder: {folder_name}")

        self.folder_cache[key] = folder_id
        return folder_id

    def get_drive_path_id(self, relative_path):
        parts = relative_path.split(os.sep)[:-1]
        parent_id = None
        for part in parts:
            parent_id = self.get_or_create_folder(part, parent_id)
        return parent_id

    def upload_file(self, file_path, relative_path):
        if not self.drive:
            logging.error("⚠️ Cannot upload, Google Drive not authenticated.")
            return

        file_name = os.path.basename(file_path)
        parent_id = self.get_drive_path_id(relative_path)

        # Check if file already exists in Drive
        query = f"title='{file_name}' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        existing = self.drive.ListFile({'q': query}).GetList()
        if existing:
            file = existing[0]
            file.SetContentFile(file_path)
            file.Upload()
            logging.info(f"♻️ Updated in Drive: {relative_path}")
        else:
            file = self.drive.CreateFile({
                'title': file_name,
                'parents': [{'id': parent_id}] if parent_id else []
            })
            file.SetContentFile(file_path)
            file.Upload()
            logging.info(f"✅ Uploaded new to Drive: {relative_path}")

        # === Local Drive Mirror ===
        mirror_path = os.path.join(self.mirror_dir, relative_path)
        os.makedirs(os.path.dirname(mirror_path), exist_ok=True)
        shutil.copy(file_path, mirror_path)
        logging.info(f"🗂️ Local mirror updated: {mirror_path}")

    def download_drive_to_local(self, folder_id=None, local_path=None):
        """Download files from Drive into local mirror"""
        if not self.drive:
            return
        if folder_id is None:
            files = self.drive.ListFile({'q': "'root' in parents and trashed=false"}).GetList()
        else:
            files = self.drive.ListFile({'q': f"'{folder_id}' in parents and trashed=false"}).GetList()

        for file in files:
            if file['mimeType'] == 'application/vnd.google-apps.folder':
                new_local_path = os.path.join(local_path, file['title']) if local_path else os.path.join(self.mirror_dir, file['title'])
                os.makedirs(new_local_path, exist_ok=True)
                self.download_drive_to_local(file['id'], new_local_path)
            else:
                local_file_path = os.path.join(local_path or self.mirror_dir, file['title'])
                file.GetContentFile(local_file_path)
                logging.info(f"⬇️ Downloaded from Drive: {local_file_path}")

# ===== Notifier =====
class Notifier:
    def __init__(self, sender, receiver):
        self.sender = sender
        self.receiver = receiver
        self.password = "Your G-Mail App Password"

    def send(self, message):
        try:
            msg = MIMEText(message)
            msg['Subject'] = "Backup Notification"
            msg['From'] = self.sender
            msg['To'] = self.receiver

            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)
            logging.info(f"📩 Email sent: {message}")
        except Exception as e:
            logging.error(f"❌ Email notification failed: {str(e)}")

# ===== File Watcher =====
class BackupHandler(FileSystemEventHandler):
    def __init__(self, uploader, notifier, version_manager, hash_store, base_path):
        self.uploader = uploader
        self.notifier = notifier
        self.version_manager = version_manager
        self.hash_store = hash_store
        self.base_path = base_path
        self.ignore_dirs = ["logs", "versions", "__pycache__", "drive_mirror"]

    def process_file(self, full_path):
        rel_path = os.path.relpath(full_path, self.base_path)
        if any(ignored in rel_path for ignored in self.ignore_dirs):
            return
        if not os.path.isfile(full_path):
            return

        current_hash = compute_hash(full_path)
        if self.hash_store.get(full_path) == current_hash:
            return
        self.hash_store[full_path] = current_hash

        self.version_manager.save_version(full_path)
        self.uploader.upload_file(full_path, rel_path)
        self.notifier.send(f"Backup done: {rel_path}")

    def on_modified(self, event):
        if not event.is_directory:
            self.process_file(event.src_path)

# ===== Backup Manager =====
class BackupManager:
    def __init__(self):
        with open('config/config.json') as f:
            config = json.load(f)
        self.watch_path = config['watch_path']

        # Setup logs inside watch_path
        self.log_dir = os.path.join(self.watch_path, "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        logging.basicConfig(
            filename=os.path.join(self.log_dir, "backup_log.txt"),
            level=logging.INFO,
            format="%(asctime)s - %(message)s"
        )

        self.mirror_dir = os.path.join(self.watch_path, "drive_mirror")
        self.uploader = Uploader(self.mirror_dir)
        self.notifier = Notifier(config['email']['sender'], config['email']['receiver'])
        self.version_manager = VersionManager(self.watch_path)
        self.hash_store = {}

    def backup_existing_files(self):
        handler = BackupHandler(self.uploader, self.notifier, self.version_manager, self.hash_store, self.watch_path)
        for root, _, files in os.walk(self.watch_path):
            for file in files:
                full_path = os.path.join(root, file)
                handler.process_file(full_path)

    def sync_drive_to_local(self):
        logging.info("⬇️ Syncing Google Drive → Local mirror...")
        self.uploader.download_drive_to_local(local_path=self.mirror_dir)

    def start_backup(self):
        # 1. Sync Drive to Local Mirror
        self.sync_drive_to_local()

        # 2. Full backup of local files to Drive
        logging.info("🚀 Starting full backup of existing local files...")
        self.backup_existing_files()

        # 3. Watch for changes
        logging.info("🔍 Now watching for changes...")
        event_handler = BackupHandler(self.uploader, self.notifier, self.version_manager, self.hash_store, self.watch_path)
        observer = PollingObserver(timeout=10)
        observer.schedule(event_handler, self.watch_path, recursive=True)
        observer.start()

        with ThreadPoolExecutor(max_workers=2):
            try:
                while True:
                    time.sleep(5)
            except KeyboardInterrupt:
                observer.stop()
        observer.join()

if __name__ == "__main__":
    manager = BackupManager()
    manager.start_backup()
