# PS5 Dump Game Sync Tool

![Version](https://img.shields.io/badge/version-v1.2.0-blue)
![Python](https://img.shields.io/badge/python-3.x-yellow)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

**PS5 Dump Game Sync Tool** is a GUI utility designed to streamline the process of syncing dumped PS4/PS5 games from USB storage to the PS5 internal storage (`/data/homebrew`). It also acts as a central hub for managing essential payloads like Dump Runner, Kstuff, and ShadowMount.

## 📸 Screenshots

<img width="849" height="682" alt="obraz" src="https://github.com/user-attachments/assets/2e85e690-5c0c-4759-ae3a-8ceba647eb45" />

## ✨ Features

### 🎮 Game Synchronization
* Scans connected USB drives (and `/mnt/ext`) for dumped games.
* Syncs game folders to `/data/homebrew` on the PS5.
* **Auto-Configuration:** Automatically generates the `homebrew.js` file required for **Itemzflow** or **Lightning Launcher** to recognize the game.
* **Smart Metadata:** Detects game titles automatically (supports multi-language).
* **Version Control:** Checks MD5 of the local payload to ensure the PS5 is always up-to-date.

### 🛠 Payload Managers
The tool includes built-in managers to fetch the latest versions of popular tools directly from GitHub:
1.  **Dump Runner Manager:** Download and update the local `dump_runner.elf`.
2.  **Kstuff Manager:** Download `kstuff.elf` releases and install them to `/data/etaHEN` via FTP.
3.  **ShadowMount Center:** Download `shadowmount.elf` and either:
    * **Inject** it directly to the payload port.
    * **Install** it permanently via FTP.

## 🚀 Installation & Usage

### Prerequisites
* Python 3.x installed on your system.
* A PS5 running a Jailbreak/Exploit (etaHEN recommended).

### Running from Source

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/F1CU/ps5-games-in-homebrew-sync.git
    cd PS5-Dump-Game-Sync-Tool
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

On the first launch, the tool creates a `settings.json` file. You can modify these settings in the **Settings** tab within the app:

* **PS5 IP:** The IP address of your console.
* **FTP Port:** Default is `1337`.
* **Payload Port:** Default is `9021` (standard for etaHEN/Elf Loader).

## 🤝 Credits

* **[EchoStretch](https://github.com/EchoStretch)** for [Dump Runner](https://github.com/EchoStretch/dump_runner) and [Kstuff](https://github.com/EchoStretch/kstuff).
* **voidwhisper-ps** for [ShadowMount](https://github.com/voidwhisper-ps/ShadowMount).
* **[ps5-payload-dev](https://github.com/ps5-payload-dev)** - For the websrv (Homebrew Launcher).

## ⚠️ Disclaimer

This tool is intended for educational and development purposes only. The author is not responsible for any damage to your console or data loss. Use at your own risk.
