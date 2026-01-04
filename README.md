# PS5 Homebrew Game Sync Tool

A lightweight automation tool for PS5 Homebrew users. This script scans your console's storage, fixes missing icons in **Homebrew Launcher (websrv)**, and automatically updates the game runner to the latest bleeding-edge version.

## ⚡ What's New?

* **Auto Game Mount Support:** Automatically downloads the latest `dump_runner` (based on EchoStretch's latest commits) which now handles **Auto Game Mount** via Kstuff. This improves stability and launch reliability.
* **Extended Firmware Support:** Compatible with payloads supporting FW **9.xx up to 10.01**.
* **Detailed Logging:** Generates `ps5_sync_log.txt` for easy troubleshooting.
* **Folder Agnostic:** It doesn't matter if your dumps are in `/games`, `/etaHEN/games`, or `/homebrew`. The script detects them automatically.

## 🚀 Key Features

* **Smart Sync:** Checks if artwork already exists on the console and skips it.
* **Fixes Missing Art:** Automatically handles case-sensitive filenames (e.g., `ICON0.PNG` vs `icon0.png`), ensuring covers appear in the launcher.
* **Universal Scan:** Detects games on USB (0-7), Extended Storage, and Internal paths.

## 🛠 Prerequisites

* Python 3.x
* PS5 with FTP server running (etaHEN)

## 📦 Usage

1. Download `ps5_game_sync.py`.
2. Run the script:
    ```bash
    python ps5_game_sync.py
    ```
3. On the first run, it will create a `settings.json` file.
4. Edit `settings.json` with your PS5 IP address.
5. Run the script again. It will:
    * **Auto-fetch** the latest `dump_runner.elf`.
    * Scan your drives and setup the games.
    * Save a log to `ps5_sync_log.txt`.
6. **Important:** Refresh/Reload your Homebrew Launcher to see the new icons.

## ⚙️ Configuration (settings.json)

```json
{
    "ps5_ip": "192.168.1.30",
    "ps5_ftp_port": 1337,
    "target_base_path": "/data/homebrew"
}
```
📜 Credits
```Markdown
    EchoStretch: For dump_runner, kstuff (Auto Game Mount logic), and original JS concepts.

    ps5-payload-dev: For the websrv (Homebrew Launcher).
```
⚠️ Disclaimer

This tool is for educational and development purposes. Use at your own risk.