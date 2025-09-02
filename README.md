📂 Automated Backup & Sync System

This project is an automated backup, versioning, and synchronization tool for local files. It monitors a specified directory for changes, creates file versions, syncs them to Google Drive, maintains a local mirror, and sends email notifications on backup events.

✨ Features

🔄 Real-time Monitoring – Watches a directory and backs up files on modification.

🕒 Version Control – Maintains timestamped versions of updated files.

☁️ Google Drive Sync – Uploads new/modified files to Google Drive and keeps a local mirror.

📥 Drive → Local Sync – Downloads Google Drive contents into a local mirror before backup starts.

📧 Email Notifications – Sends an email after each successful backup.

📝 Logging – Keeps detailed logs of all operations in logs/backup_log.txt.

⚡ Concurrent Execution – Uses multithreading for efficient backup operations.

📦 Requirements

Python 3.8+

Required Python libraries:

pip install watchdog pydrive google-auth smtplib


Google Drive API enabled with OAuth credentials.

Gmail account with App Passwords enabled (for email notifications).

⚙️ Configuration

The project expects a configuration file at:

config/config.json


Example structure:

{
  "watch_path": "C:/path/to/watch",
  "email": {
    "sender": "youremail@gmail.com",
    "receiver": "receiveremail@gmail.com"
  }
}

🔑 Google Drive Authentication

First run will open a browser for authentication.

Credentials will be stored in mycreds.txt for future use.

🚀 Usage

Run the script:

python backup.py


The system will:

Sync Google Drive contents to the local mirror.

Perform a full backup of all existing files.

Start watching for changes and back them up automatically.

Stop with CTRL + C.

📁 Project Structure
project/
│── backup.py              # Main script
│── config/
│   └── config.json        # Configuration file
│── mycreds.txt            # Google Drive credentials (auto-generated)
│── logs/
│   └── backup_log.txt     # Backup logs
│── versions/              # Stored file versions
│── drive_mirror/          # Local mirror of Google Drive

📧 Email Notifications

Uses Gmail SMTP (smtp.gmail.com:587).

Requires a Gmail App Password instead of your real password.

Edit the password in Notifier class if you change accounts.
