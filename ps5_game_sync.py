"""
PS5 Homebrew Game Sync Tool
---------------------------------------------------
Automates the process of adding PS5 game dumps to the Homebrew Launcher (websrv).

Features:
- Universal Discovery: Detects games regardless of folder (/games, /etaHEN, /homebrew).
- Auto-Download: Fetches latest dump_runner with 'Auto Game Mount' & FW 10.01 support.
- Incremental Sync: Only copies missing files.
- Detailed Logging: Operations saved to ps5_sync_log.txt.
- Fixes cover art: Handles icon0.png case-sensitivity automatically.

CREDITS:
- dump_runner & Kstuff (Auto Game Mount): EchoStretch
  https://github.com/EchoStretch/dump_runner
- Homebrew Launcher (websrv): ps5-payload-dev
  https://github.com/ps5-payload-dev/websrv
---------------------------------------------------
"""

import ftplib
import os
import io
import json
import sys
import time
import urllib.request
import zipfile
import logging
from datetime import datetime

# --- HARDCODED SETTINGS ---
GITHUB_REPO_OWNER = "EchoStretch"
GITHUB_REPO_NAME = "dump_runner"
GITHUB_BRANCH = "main"
WORKFLOW_FILENAME = "build.yml"
ARTIFACT_NAME = "dump_runner"
LOG_FILENAME = "ps5_sync_log.txt"

# --- CONFIGURATION ---
CONFIG_FILE = "settings.json"
DEFAULT_CONFIG = {
    "ps5_ip": "192.168.1.30",
    "ps5_ftp_port": 1337,
    "target_base_path": "/data/homebrew"
}

# --- LOGGER SETUP ---
def setup_logger():
    # Konfiguracja loggera: Zapis do pliku ORAZ wypisywanie na konsolę
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(LOG_FILENAME, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        logging.info(f"Created default configuration file: {CONFIG_FILE}")
        return DEFAULT_CONFIG
    else:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config

# --- PATHS ---
SEARCH_PATHS = []
SEARCH_PATHS.append("/data/homebrew")
for i in range(8): SEARCH_PATHS.append(f"/mnt/usb{i}/homebrew")
for i in range(8): SEARCH_PATHS.append(f"/mnt/ext{i}/homebrew")
SEARCH_PATHS.append("/data/etaHEN/games")
for i in range(7): SEARCH_PATHS.append(f"/mnt/usb{i}/etaHEN/games")
for i in range(2): SEARCH_PATHS.append(f"/mnt/ext{i}/etaHEN/games")
SEARCH_PATHS.append("/mnt/usb0/games")
SEARCH_PATHS.append("/mnt/usb1/games")
SEARCH_PATHS.append("/data/games")

# --- JS TEMPLATE ---
JS_TEMPLATE = """
/* Generated with PS5 Game Sync tool based on EchoStretch's dump_runner homebrew.js repository */
async function main() {{
    const LOCAL_PATH = window.workingDir;
    const PAYLOAD = LOCAL_PATH + '/dump_runner.elf';
    const USB_GAME_PATH = '{usb_path}';
    
    const PARAM_URL = baseURL + '/fs/' + USB_GAME_PATH + '/sce_sys/param.json';
    
    // Check local files
    const ICON_PATH = 'file://' + LOCAL_PATH + '/sce_sys/icon0.png';
    const BG_PATH = 'file://' + LOCAL_PATH + '/sce_sys/pic1.png'; 

    const resp = await fetch(PARAM_URL);
    const param = await resp.json();

    var name = '';
    for (const key in param.localizedParameters) {{
        if (key.startsWith('en-')) {{
            name = param.localizedParameters[key]['titleName'];
            break;
        }}
    }}
    if (name === '') {{
        const keys = Object.keys(param.localizedParameters);
        if (keys.length > 0) name = param.localizedParameters[keys[0]]['titleName'];
        else name = param['titleId'];
    }}

    return {{
        mainText: name,
        secondaryText: param['titleId'],
        image: ICON_PATH,
        imageBackground: BG_PATH,
        onclick: async () => {{
            return {{
                path: PAYLOAD,
                cwd: USB_GAME_PATH,
                args: [PAYLOAD, param['titleId']],
                daemon: true,
            }};
        }}
    }};
}}
"""

# --- DOWNLOAD FUNCTION (Standard Lib) ---
def ensure_dump_runner():
    if os.path.exists("dump_runner.elf"):
        logging.info("Local dump_runner.elf found.")
        return True
        
    url = f"https://nightly.link/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/workflows/{WORKFLOW_FILENAME}/{GITHUB_BRANCH}/{ARTIFACT_NAME}.zip"
    logging.info(f"[INIT] dump_runner.elf missing. Downloading from: {url}")
    
    try:
        with urllib.request.urlopen(url) as response:
            if response.status == 200:
                zip_data = io.BytesIO(response.read())
                with zipfile.ZipFile(zip_data) as z:
                    z.extract("dump_runner.elf", path=".")
                logging.info("[INIT] Downloaded and extracted successfully.")
                return True
            else:
                logging.error(f"[INIT] Download failed with status: {response.status}")
    except Exception as e:
        logging.error(f"[ERROR] Could not download file: {e}")
        return False

    return False

def connect_ftp(cfg):
    logging.info(f"[FTP] Connecting to {cfg['ps5_ip']}:{cfg['ps5_ftp_port']}...")
    try:
        ftp = ftplib.FTP()
        ftp.connect(cfg['ps5_ip'], cfg['ps5_ftp_port'], timeout=10)
        ftp.login()
        logging.info("[FTP] Connection established!")
        return ftp
    except Exception as e:
        logging.critical(f"[FTP] Connection Error: {e}")
        return None

def is_valid_game_dump(ftp, folder_path):
    param_file = f"{folder_path}/sce_sys/param.json"
    try:
        ftp.size(param_file)
        return True
    except ftplib.error_perm:
        return False

def scan_games(ftp, target_base_path):
    found_games = []
    processed_paths = set()
    logging.info(f"[SCAN] Starting scan across {len(SEARCH_PATHS)} paths...")
    
    for path in SEARCH_PATHS:
        try:
            ftp.cwd(path)
            items = ftp.nlst()
            for item in items:
                if "." in item: continue
                
                # Skip target folder self-scan
                if path == target_base_path:
                    try:
                        files = ftp.nlst(f"{path}/{item}")
                        if "dump_runner.elf" in [os.path.basename(f) for f in files]:
                            continue 
                    except: pass
                
                full_path = f"{path}/{item}"
                if full_path not in processed_paths:
                    if is_valid_game_dump(ftp, full_path):
                        logging.info(f"  [GAME FOUND] {item} at {path}")
                        found_games.append((item, full_path))
                        processed_paths.add(full_path)
                    else:
                        # Optional debug for invalid folders
                        # logging.debug(f"  [SKIP] {item} (Invalid dump/No param.json)")
                        pass
        except ftplib.error_perm:
            # logging.debug(f"[SCAN] Path not accessible: {path}")
            continue
            
    return found_games

def remote_file_exists(ftp, filepath):
    try:
        size = ftp.size(filepath)
        return size > 0
    except ftplib.error_perm:
        return False

def brute_force_transfer_image(ftp, source_base, target_base_game_dir, image_type):
    source_sce = f"{source_base}/sce_sys"
    target_sce = f"{target_base_game_dir}/sce_sys"
    target_full_path = f"{target_sce}/{image_type}"
    
    # SPEED CHECK
    if remote_file_exists(ftp, target_full_path):
        logging.info(f"    [SKIP] {image_type} already exists on target.")
        return

    # Transfer if missing
    try: ftp.mkd(target_sce)
    except: pass

    try:
        ftp.cwd(source_sce)
        files = ftp.nlst()
    except Exception as e:
        logging.warning(f"    [WARN] Could not access source sce_sys: {source_sce} ({e})")
        return

    found_name = None
    for f in files:
        fname = os.path.basename(f)
        if fname.lower() == image_type.lower():
            found_name = fname
            break
    
    if found_name:
        bio = io.BytesIO()
        try:
            ftp.retrbinary(f"RETR {found_name}", bio.write)
            bio.seek(0)
            ftp.storbinary(f"STOR {target_full_path}", bio)
            logging.info(f"    [COPY] Transferred {found_name} -> {image_type}")
        except Exception as e:
            logging.error(f"    [ERROR] Transfer failed for {found_name}: {e}")
    else:
        logging.info(f"    [MISSING] {image_type} not found in source game folder.")

def deploy_homebrew(ftp, game_name, source_path, target_base_path):
    target_dir = f"{target_base_path}/{game_name}"
    local_elf = "dump_runner.elf"
    
    try: ftp.mkd(target_dir)
    except: pass
        
    # Upload local ELF
    if os.path.exists(local_elf):
        with open(local_elf, "rb") as f:
            ftp.storbinary(f"STOR {target_dir}/dump_runner.elf", f)

    js_content = JS_TEMPLATE.format(usb_path=source_path)
    bio = io.BytesIO(js_content.encode('utf-8'))
    ftp.storbinary(f"STOR {target_dir}/homebrew.js", bio)
    
    brute_force_transfer_image(ftp, source_path, target_dir, "icon0.png")
    brute_force_transfer_image(ftp, source_path, target_dir, "pic1.png")
    brute_force_transfer_image(ftp, source_path, target_dir, "pic0.png")

def main():
    setup_logger()
    logging.info("--- PS5 GAME SYNC TOOL STARTED ---")
    
    # Load Config
    cfg = load_config()

    # Auto-Download if missing
    if not ensure_dump_runner():
        logging.critical("Failed to obtain dump_runner.elf. Check logs.")
        input("Press ENTER to exit...")
        return

    ftp = connect_ftp(cfg)
    if not ftp: 
        input("Press ENTER to exit...")
        return

    games = scan_games(ftp, cfg['target_base_path'])
    if not games:
        logging.warning("No games found in any scanned directory.")
        ftp.quit()
        input("Press ENTER to exit...")
        return

    logging.info(f"[DEPLOY] Starting deployment for {len(games)} games...")
    
    try: ftp.mkd(cfg['target_base_path'])
    except: pass

    count = 0
    for game_name, full_source_path in games:
        logging.info(f"Processing: {game_name}")
        deploy_homebrew(ftp, game_name, full_source_path, cfg['target_base_path'])
        count += 1
        
    ftp.quit()
    logging.info(f"--- SUCCESS ---")
    logging.info(f"Processed {count} games.")
    logging.info("IMPORTANT: Reload Homebrew Launcher (websrv) to see changes.")
    logging.info(f"Detailed log saved to: {LOG_FILENAME}")
    input("\nPress ENTER to exit...")

if __name__ == "__main__":
    main()