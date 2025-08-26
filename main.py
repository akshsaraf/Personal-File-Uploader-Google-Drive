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

# ===== Utils =====
def compute_hash(file_path):
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

# ===== Version Manager =====
class VersionManager:
    def __init__(self):
        self.version_dir = "versions/"
        os.makedirs(self.version_dir, exist_ok=True)

    def save_version(self, file_path):
        file_name = os.path.basename(file_path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        versioned_file = f"{file_name}_{timestamp}"
        shutil.copy(file_path, os.path.join(self.version_dir, versioned_file))
        print(f"📄 Version saved: {versioned_file}")

# ===== Uploader =====
class Uploader:
    def __init__(self):
        self.gauth = GoogleAuth()
        self.gauth.LocalWebserverAuth()
        self.drive = GoogleDrive(self.gauth)
        self.folder_cache = {}

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
            print(f"📁 Created folder: {folder_name}")

        self.folder_cache[key] = folder_id
        return folder_id

    def get_drive_path_id(self, relative_path):
        parts = relative_path.split(os.sep)[:-1]
        parent_id = None
        for part in parts:
            parent_id = self.get_or_create_folder(part, parent_id)
        return parent_id

    def upload_file(self, file_path, relative_path):
        file_name = os.path.basename(file_path)
        parent_id = self.get_drive_path_id(relative_path)
        query = f"title='{file_name}' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        existing = self.drive.ListFile({'q': query}).GetList()
        if existing:
            file = existing[0]
            file.SetContentFile(file_path)
            file.Upload()
            print(f"♻️ Updated: {relative_path}")
        else:
            file = self.drive.CreateFile({
                'title': file_name,
                'parents': [{'id': parent_id}] if parent_id else []
            })
            file.SetContentFile(file_path)
            file.Upload()
            print(f"✅ Uploaded: {relative_path}")

# ===== Notifier =====
class Notifier:
    def __init__(self, sender, receiver):
        self.sender = sender
        self.receiver = receiver
        self.password = "iqxk gxwu mhlb qiug"

    def send(self, message):
        msg = MIMEText(message)
        msg['Subject'] = "Backup Notification"
        msg['From'] = self.sender
        msg['To'] = self.receiver

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(self.sender, self.password)
            server.send_message(msg)
        print(f"📩 Email sent: {message}")

# ===== File Watcher =====
class BackupHandler(FileSystemEventHandler):
    def __init__(self, uploader, notifier, version_manager, hash_store, base_path):
        self.uploader = uploader
        self.notifier = notifier
        self.version_manager = version_manager
        self.hash_store = hash_store
        self.base_path = base_path

    def process_file(self, full_path):
        rel_path = os.path.relpath(full_path, self.base_path)
        current_hash = compute_hash(full_path)
        if self.hash_store.get(full_path) == current_hash:
            return
        self.hash_store[full_path] = current_hash
        self.version_manager.save_version(full_path)
        self.uploader.upload_file(full_path, rel_path)
        self.notifier.send(f"Backup: {rel_path}")

    def on_modified(self, event):
        if not event.is_directory:
            self.process_file(event.src_path)

# ===== Backup Manager =====
class BackupManager:
    def __init__(self):
        with open('config/config.json') as f:
            config = json.load(f)
        self.watch_path = config['watch_path']
        self.uploader = Uploader()
        self.notifier = Notifier(config['email']['sender'], config['email']['receiver'])
        self.version_manager = VersionManager()
        self.hash_store = {}

    def backup_existing_files(self):
        handler = BackupHandler(self.uploader, self.notifier, self.version_manager, self.hash_store, self.watch_path)
        for root, _, files in os.walk(self.watch_path):
            for file in files:
                full_path = os.path.join(root, file)
                handler.process_file(full_path)

    def start_backup(self):
        self.backup_existing_files()
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