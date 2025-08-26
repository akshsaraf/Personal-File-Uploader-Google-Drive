from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from concurrent.futures import ThreadPoolExecutor
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from email.mime.text import MIMEText
import smtplib
import time
import os
import shutil
from datetime import datetime
import json
import logging

# Ensure necessary directories exist
os.makedirs("logs", exist_ok=True)
os.makedirs("versions", exist_ok=True)

# Setup logging
logging.basicConfig(filename="logs/backup_log.txt", level=logging.INFO, format="%(asctime)s - %(message)s")

class VersionManager:
    def __init__(self):
        self.version_dir = "versions/"

    def save_version(self, file_path):
        try:
            file_name = os.path.basename(file_path)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            versioned_file = f"{file_name}_{timestamp}"
            shutil.copy(file_path, os.path.join(self.version_dir, versioned_file))
            logging.info(f"📄 Version saved: {versioned_file}")
        except Exception as e:
            logging.error(f"⚠️ Error saving version: {str(e)}")

class Uploader:
    def __init__(self):
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
            logging.error(f"❌ Google Drive authentication failed: {str(e)}")

    def upload_file(self, file_path):
        try:
            file = self.drive.CreateFile({'title': os.path.basename(file_path)})
            file.SetContentFile(file_path)
            file.Upload()
            logging.info(f"✅ Uploaded to Google Drive: {file['title']}")
        except Exception as e:
            logging.error(f"❌ Failed to upload {file_path} to Drive: {str(e)}")

class Notifier:
    def __init__(self, sender, receiver):
        self.sender = sender
        self.receiver = receiver
        self.password = "iqxk gxwu mhlb qiug"

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

class BackupHandler(FileSystemEventHandler):
    def __init__(self, uploader, notifier, version_manager):
        self.uploader = uploader
        self.notifier = notifier
        self.version_manager = version_manager

    def on_modified(self, event):
        if not event.is_directory:
            try:
                logging.info(f"📝 File modified: {event.src_path}")

                self.version_manager.save_version(event.src_path)
                self.uploader.upload_file(event.src_path)
                self.notifier.send(f"Backup done: {os.path.basename(event.src_path)}")

            except Exception as e:
                logging.error(f"⚠️ Error processing {event.src_path}: {str(e)}")

class BackupManager:
    def __init__(self):
        try:
            with open('config/config.json') as f:
                config = json.load(f)

            self.watch_path = config['watch_path']
            self.uploader = Uploader()
            self.notifier = Notifier(config['email']['sender'], config['email']['receiver'])
            self.version_manager = VersionManager()

            logging.info("✅ BackupManager initialized successfully.")

        except Exception as e:
            logging.error(f"❌ Error initializing BackupManager: {str(e)}")

    def start_backup(self):
        event_handler = BackupHandler(self.uploader, self.notifier, self.version_manager)
        observer = PollingObserver(timeout=10)

        try:
            observer.schedule(event_handler, self.watch_path, recursive=True)
            observer.start()
            logging.info("🚀 Backup service started, monitoring for changes...")

            with ThreadPoolExecutor(max_workers=2) as executor:
                while True:
                    time.sleep(5)

        except KeyboardInterrupt:
            logging.info("🛑 Backup service stopped manually.")
            observer.stop()
        except Exception as e:
            logging.error(f"❌ Critical error in BackupManager: {str(e)}")

        observer.join()

if __name__ == "__main__":
    manager = BackupManager()
    manager.start_backup()

