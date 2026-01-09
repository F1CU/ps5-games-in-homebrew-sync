# PS5 Dump Game Sync Tool

![Version](https://img.shields.io/badge/version-v1.2.0-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

**PS5 Dump Game Sync Tool** is an all-in-one GUI utility designed to streamline the process of syncing dumped PS4/PS5 games from USB storage to the PS5 internal storage. It serves as a central hub for managing essential payloads like Dump Runner, Kstuff, and ShadowMount.

## 📸 Screenshots

<img width="849" height="682" alt="obraz" src="https://github.com/user-attachments/assets/2e85e690-5c0c-4759-ae3a-8ceba647eb45" />

## ✨ Key Features

### 🖥️ Modern GUI
A completely new graphical interface makes managing your PS5 homebrew easier than ever.

### 🎮 Game Synchronization
* **Auto-Sync:** Scans connected USB drives (and `/mnt/ext`) for dumped games and syncs them to `/data/homebrew`.
* **Smart Shortcuts:** Automatically generates the `homebrew.js` file for **Itemzflow** or **Lightning Launcher**.
* **Metadata:** Detects game titles and creates proper icons/backgrounds.

### 📦 Payload Managers
The tool includes built-in managers to fetch specific versions of tools directly from GitHub:

* **Dump Runner Manager:** Browse, download, and update the local `dump_runner.elf` to any version you choose.
* **Kstuff Manager:** Finally integrated! Browse Kstuff releases and install your preferred version directly to `/data/etaHEN` via FTP.
* **ShadowMount Center:** A dedicated panel to download `shadowmount.elf`. You can **Inject** it immediately for temporary use or **Install** it permanently via FTP.

## 🚀 How to Run

### Option A: Download the Executable (Recommended for Windows)
1.  Go to the [Releases](https://github.com/F1CU/ps5-games-in-homebrew-sync/releases) page.
2.  Download the latest `PS5.Dump.Game.Sync.Tool.v1.2.0.exe`.
3.  Run the application. No installation required.

### Option B: Run from Source (Python)
If you are on Linux/macOS or prefer the source code:

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/F1CU/ps5-games-in-homebrew-sync.git](https://github.com/F1CU/ps5-games-in-homebrew-sync.git)
    cd ps5-games-in-homebrew-sync
    ```

2.  **Install dependencies:**
    ```bash
    pip install customtkinter
    ```

3.  **Run the application:**
    ```bash
    python ps5_game_sync.py
    ```

## ⚙ Configuration

On the first launch, go to the **Settings** tab:
* **PS5 IP:** Enter your console's IP address.
* **FTP Port:** Default is `1337`.
* **Payload Port:** Default is `9021`.

## 🤝 Credits

* **[EchoStretch](https://github.com/EchoStretch)** for [Dump Runner](https://github.com/EchoStretch/dump_runner) and [Kstuff](https://github.com/EchoStretch/kstuff).
* **[voidwhisper-ps](https://github.com/voidwhisper-ps)** for [ShadowMount](https://github.com/voidwhisper-ps/ShadowMount).
* **[ps5-payload-dev](https://github.com/ps5-payload-dev)** - For the [websrv](https://github.com/ps5-payload-dev/websrv) (Homebrew Launcher).

## ⚠️ Disclaimer

This tool is intended for educational and development purposes only. The author is not responsible for any damage to your console or data loss. Use at your own risk.
