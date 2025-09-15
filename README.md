# 📂 Automated Backup & Sync System  

An automated **backup, versioning, and synchronization tool** for local files.  
It monitors a directory in real time, creates file versions, syncs them to **Google Drive**, maintains a **local mirror**, and sends **email notifications** on backup events.  

---

## ✨ Features  

- 🔄 **Real-time Monitoring** – Automatically backs up files on modification.  
- 🕒 **Version Control** – Saves timestamped versions of updated files.  
- ☁️ **Google Drive Sync** – Uploads changes to Drive and keeps a local mirror.  
- 📥 **Drive → Local Sync** – Mirrors Drive contents locally before starting backups.  
- 📧 **Email Notifications** – Sends an email after each successful backup.  
- 📝 **Detailed Logging** – Stores logs at `logs/backup_log.txt`.  
- ⚡ **Concurrent Execution** – Multithreaded for faster backups.  

---

## 📦 Requirements  

- **Python 3.8+**  
- Install dependencies:  
  ```bash
  pip install watchdog pydrive google-auth smtplib

Google Drive API enabled with OAuth credentials
Gmail account with App Passwords enabled (for email alerts)

Configuration is stored in:
```bash
  config/config.json
```
Example:
```
{
  "watch_path": "C:/path/to/watch",
  "email": {
    "sender": "youremail@gmail.com",
    "receiver": "receiveremail@gmail.com"
  }
}
```

🔑 Google Drive Authentication

On first run, a browser window will open for authentication.
OAuth credentials are required (downloaded from your Google Cloud Console).
After successful authentication, a mycreds.txt file is generated.
This file stores your credentials securely so that repeated logins are not required.

🚀 Usage

Run:
```bash
python main.py
```
The system will:

Sync Google Drive → Local mirror.
Perform a full backup of existing files.
Watch for changes and back them up automatically.
Stop with CTRL + C.

📁 Project Structure:
```
project/
│── backup.py              # Main script
│── config/
│   └── config.json        # Configuration file
│── mycreds.txt            # Google Drive credentials (auto-generated)
│── logs/
│   └── backup_log.txt     # Backup logs
│── versions/              # Stored file versions
│── drive_mirror/          # Local mirror of Google Drive
```

📧 Email Notifications
Uses Gmail SMTP (smtp.gmail.com:587)
Requires a Gmail App Password (not your main password)
Update credentials in the Notifier class if switching accounts
