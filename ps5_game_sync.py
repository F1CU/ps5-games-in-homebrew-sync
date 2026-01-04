"""
PS5 Homebrew Game Sync Tool (v1.1.0)
---------------------------------------------------
Automates the process of adding PS5 game dumps to the Homebrew Launcher (websrv).

Features:
- SMART MENU: Dynamically hides "Latest" option if it matches "Recommended".
- PINNED RELEASE: Defaults to a verified payload version.
- MD5 INTEGRITY: Compares local file hash vs remote metadata (payload_version.json).
- SMART SYNC: Compares content of homebrew.js to avoid redundant writes.
- AUTO-LANGUAGE: Detects console language and selects appropriate game title.

CREDITS:
- dump_runner & Kstuff: EchoStretch
- Homebrew Launcher (websrv): ps5-payload-dev
---------------------------------------------------
"""

import ftplib
import os
import io
import json
import sys
import urllib.request
import zipfile
import logging
import hashlib
from datetime import datetime

# --- CONFIGURATION (DEVELOPER) ---
TOOL_VERSION = "v1.1.0"
TESTED_VERSION_TAG = "v1.00"  # The payload version we recommend/tested

# --- CONFIGURATION (USER) ---
LOG_FILENAME = "ps5_sync_log.txt"
CONFIG_FILE = "settings.json"
DEFAULT_CONFIG = {
    "ps5_ip": "192.168.1.30",
    "ps5_ftp_port": 1337,
    "target_base_path": "/data/homebrew"
}

# --- GLOBAL VARS ---
LOCAL_PAYLOAD_META = {
    "version": "Unknown",
    "date": "Unknown",
    "md5": None
}

# --- JS TEMPLATE ---
JS_TEMPLATE = """
/* Generated with PS5 Game Sync tool {tool_version} */
async function main() {{
    const LOCAL_PATH = window.workingDir;
    const PAYLOAD = LOCAL_PATH + '/dump_runner.elf';
    const USB_GAME_PATH = '{usb_path}';
    
    // Remote path to param.json on USB
    const PARAM_JSON_URL = baseURL + '/fs/' + USB_GAME_PATH + '/sce_sys/param.json';
    
    // Icons
    const ICON_PATH = 'file://' + LOCAL_PATH + '/sce_sys/icon0.png';
    const BG_PATH = 'file://' + LOCAL_PATH + '/sce_sys/pic1.png'; 

    // Defaults
    let mainText = 'Game Shortcut';
    let secondaryText = USB_GAME_PATH.split('/').pop();
    let args = [PAYLOAD];
    
    const sysLang = navigator.language || 'en-US';

    try {{
        const resp = await fetch(PARAM_JSON_URL);
        
        if (resp.ok) {{
            const param = await resp.json();
            
            // --- AUTO LANGUAGE DETECTION ---
            let name = '';
            const langPrefix = sysLang.split('-')[0].toLowerCase() + '-';

            if (param.localizedParameters) {{
                // 1. Try System Language
                for (const key in param.localizedParameters) {{
                    if (key.toLowerCase().startsWith(langPrefix)) {{
                        name = param.localizedParameters[key].titleName;
                        break;
                    }}
                }}
                // 2. Try English (Fallback)
                if (!name) {{
                    for (const key in param.localizedParameters) {{
                        if (key.startsWith('en-')) {{
                            name = param.localizedParameters[key].titleName;
                            break;
                        }}
                    }}
                }}
                // 3. First Available (Last Resort)
                if (!name) {{
                     const keys = Object.keys(param.localizedParameters);
                     if (keys.length > 0) name = param.localizedParameters[keys[0]].titleName;
                }}
            }}

            if (name) mainText = name;
            
            if (param.titleId) {{
                secondaryText = param.titleId; 
                args = [PAYLOAD, param.titleId];
            }}
        }}
    }} catch (e) {{
        console.log("Sync Tool Error: " + e);
    }}

    return {{
        mainText,
        secondaryText,
        image: ICON_PATH,
        imageBackground: BG_PATH,
        onclick: async () => {{
            return {{
                path: PAYLOAD,
                cwd: USB_GAME_PATH,
                args: args,
                daemon: true,
            }};
        }}
    }};
}}
"""

# --- LOGGER ---
def setup_logger():
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
        return DEFAULT_CONFIG
    else:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config

# --- HELPER FUNCTIONS ---
def calculate_file_md5(filepath):
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except:
        return None

def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'PS5SyncTool'})
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return None

def format_datetime(iso_str):
    try:
        return iso_str.replace('T', ' ').replace('Z', '')[:16]
    except:
        return iso_str

# --- GITHUB INFO GETTERS ---
def get_pinned_info():
    url = f"https://api.github.com/repos/EchoStretch/dump_runner/releases/tags/{TESTED_VERSION_TAG}"
    data = fetch_json(url)
    if not data: return get_latest_stable_fallback()

    download_url = None
    for asset in data.get('assets', []):
        if asset['name'].endswith('.zip'):
            download_url = asset['browser_download_url']
            break     
    if not download_url: return None

    body = data.get('body', '').split('\n')[0].strip()
    if len(body) > 60: body = body[:57] + "..."

    return {
        "tag": data.get('tag_name', 'Unknown'),
        "date": format_datetime(data.get('published_at', '')),
        "note": body,
        "url": download_url,
        "is_verified": True
    }

def get_latest_stable_fallback():
    url = "https://api.github.com/repos/EchoStretch/dump_runner/releases/latest"
    data = fetch_json(url)
    if not data: return None
    
    download_url = None
    for asset in data.get('assets', []):
        if asset['name'].endswith('.zip'):
            download_url = asset['browser_download_url']
            break
    if not download_url: return None

    return {
        "tag": data.get('tag_name', 'Unknown'),
        "date": format_datetime(data.get('published_at', '')),
        "note": data.get('body', '').split('\n')[0].strip(),
        "url": download_url,
        "is_verified": False
    }

def get_latest_stable_info():
    return get_latest_stable_fallback()

def get_beta_info():
    url = "https://api.github.com/repos/EchoStretch/dump_runner/actions/runs?branch=main&status=success&per_page=1"
    data = fetch_json(url)
    if not data or not data.get('workflow_runs'): return None
    
    run = data['workflow_runs'][0]
    msg = run.get('head_commit', {}).get('message', '').split('\n')[0].strip()
    if len(msg) > 60: msg = msg[:57] + "..."
    
    return {
        "tag": run.get('head_sha', '')[:7],
        "date": format_datetime(run.get('updated_at', '')),
        "note": msg,
        "url": "https://nightly.link/EchoStretch/dump_runner/workflows/build.yml/main/dump_runner.zip"
    }

# --- DOWNLOAD LOGIC ---
def download_and_extract(url, version_label, version_date):
    logging.info(f"[DOWNLOAD] Starting download: {version_label}")
    try:
        with urllib.request.urlopen(url) as response:
            if response.status == 200:
                data = io.BytesIO(response.read())
                if url.endswith('.zip') or data.getbuffer().nbytes > 0: 
                    try:
                        with zipfile.ZipFile(data) as z:
                            elf_name = next((n for n in z.namelist() if n.endswith('dump_runner.elf')), None)
                            if elf_name:
                                with open("dump_runner.elf", "wb") as f_out:
                                    f_out.write(z.read(elf_name))
                                
                                LOCAL_PAYLOAD_META["version"] = version_label
                                LOCAL_PAYLOAD_META["date"] = version_date
                                LOCAL_PAYLOAD_META["md5"] = calculate_file_md5("dump_runner.elf")
                                
                                logging.info(f"[SUCCESS] Updated dump_runner.elf (MD5: {LOCAL_PAYLOAD_META['md5']})")
                                return True
                    except zipfile.BadZipFile:
                         logging.error("[ERROR] Downloaded file is not a valid ZIP.")
            else:
                logging.error(f"[ERROR] HTTP Status: {response.status}")
    except Exception as e:
        logging.error(f"[ERROR] Download exception: {e}")
    return False

def manage_dump_runner():
    exists = os.path.exists("dump_runner.elf")
    
    print("\n--- PAYLOAD UPDATER ---")
    print("Checking for updates...")
    
    pinned = get_pinned_info()
    latest = get_latest_stable_info()
    beta = get_beta_info()
    
    menu_options = []
    
    # 1. Pinned Option
    if pinned:
        menu_options.append({
            "key": "pinned", 
            "label": f"RECOMMENDED: {pinned['tag']} (Verified)", 
            "info": pinned,
            "desc": f"Date: {pinned['date']} | Info: {pinned['note']}"
        })
    
    # 2. Latest Option (Only if different)
    if latest:
        if not pinned or (pinned and latest['tag'] != pinned['tag']):
            menu_options.append({
                "key": "latest",
                "label": f"NEWEST STABLE: {latest['tag']}", 
                "info": latest,
                "desc": f"Date: {latest['date']} | Info: {latest['note']}"
            })
            logging.info(f"[GITHUB] Found Latest: {latest['tag']}")
        else:
             logging.info(f"[GITHUB] Latest matches Pinned. Hiding option.")
    
    # 3. Beta Option
    if beta:
        menu_options.append({
            "key": "beta",
            "label": f"LATEST BETA: Commit {beta['tag']} (Experimental)", 
            "info": beta,
            "desc": f"Date: {beta['date']} | Info: {beta['note']}"
        })

    print("-" * 70)
    for idx, opt in enumerate(menu_options, 1):
        print(f" [{idx}] {opt['label']}")
        print(f"     {opt['desc']}")
        print("-" * 70)
        
    print(f" [{len(menu_options) + 1}] CANCEL / SKIP")
    
    prompt_msg = "\n[i] Local dump_runner.elf found.\n" if exists else "\n[!] dump_runner.elf missing.\n"
    sel_input = input(f"{prompt_msg}Select version to DOWNLOAD: ").strip()
    
    try:
        sel_idx = int(sel_input)
    except ValueError:
        print("Invalid selection.")
        return False
        
    # Cancel handling
    if sel_idx == len(menu_options) + 1:
        if exists:
            LOCAL_PAYLOAD_META["version"] = "Local File"
            LOCAL_PAYLOAD_META["date"] = "Unknown"
            LOCAL_PAYLOAD_META["md5"] = calculate_file_md5("dump_runner.elf")
            logging.info(f"[USER CHOICE] Skipped download. Using local file.")
            return True
        else:
            return False
            
    if 1 <= sel_idx <= len(menu_options):
        selected = menu_options[sel_idx - 1]
        logging.info(f"[USER CHOICE] Selected: {selected['label']}")
        info = selected['info']
        ver_label = selected['label'].split(':')[0] + " " + info['tag']
        return download_and_extract(info['url'], ver_label, info['date'])
    else:
        print("Invalid selection.")
        return False

# --- FTP & SYNC ---
def connect_ftp(cfg):
    logging.info(f"[FTP] Connecting to {cfg['ps5_ip']}:{cfg['ps5_ftp_port']}...")
    try:
        ftp = ftplib.FTP()
        ftp.connect(cfg['ps5_ip'], cfg['ps5_ftp_port'], timeout=10)
        ftp.login()
        logging.info("[FTP] Connected!")
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

def scan_games(ftp, target_base_path):
    found_games = []
    processed_paths = set()
    logging.info(f"[SCAN] Scanning paths...")
    
    for path in SEARCH_PATHS:
        try:
            ftp.cwd(path)
            items = ftp.nlst()
            for item in items:
                if "." in item: continue
                if path == target_base_path:
                    try:
                        files = ftp.nlst(f"{path}/{item}")
                        if "dump_runner.elf" in [os.path.basename(f) for f in files]: continue 
                    except: pass
                
                full_path = f"{path}/{item}"
                if full_path not in processed_paths:
                    if is_valid_game_dump(ftp, full_path):
                        logging.info(f"  [FOUND] {item} (Path: {full_path})")
                        found_games.append((item, full_path))
                        processed_paths.add(full_path)
        except ftplib.error_perm:
            continue
    return found_games

def remote_file_exists(ftp, filepath):
    try:
        size = ftp.size(filepath)
        return size > 0
    except ftplib.error_perm:
        return False

def download_remote_text(ftp, filepath):
    try:
        bio = io.BytesIO()
        ftp.retrbinary(f"RETR {filepath}", bio.write)
        return bio.getvalue().decode('utf-8', errors='ignore')
    except:
        return None

def brute_force_transfer_image(ftp, source_base, target_base_game_dir, image_type):
    source_sce = f"{source_base}/sce_sys"
    target_sce = f"{target_base_game_dir}/sce_sys"
    target_full_path = f"{target_sce}/{image_type}"
    
    if remote_file_exists(ftp, target_full_path):
        logging.info(f"    [SKIP] {image_type} (Exists)")
        return

    try: ftp.mkd(target_sce)
    except: pass
    try:
        ftp.cwd(source_sce)
        files = ftp.nlst()
    except Exception as e: return

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
            logging.info(f"    [COPY] {found_name} -> {image_type}")
        except Exception as e:
            logging.error(f"    [ERR] Failed to copy {image_type}: {e}")
    else:
        logging.info(f"    [MISS] {image_type} not found in source.")

def deploy_homebrew(ftp, game_name, source_path, target_base_path):
    target_dir = f"{target_base_path}/{game_name}"
    local_elf = "dump_runner.elf"
    remote_elf = f"{target_dir}/dump_runner.elf"
    remote_meta = f"{target_dir}/payload_version.json"
    remote_js = f"{target_dir}/homebrew.js"
    
    try: ftp.mkd(target_dir)
    except: pass
        
    # --- 1. PAYLOAD CHECK ---
    needs_payload_update = False
    remote_info = None
    
    meta_content = download_remote_text(ftp, remote_meta)
    if meta_content:
        try: remote_info = json.loads(meta_content)
        except: remote_info = None

    if remote_info and remote_info.get("md5") == LOCAL_PAYLOAD_META["md5"]:
        logging.info(f"    [SKIP] dump_runner.elf (Up to date: {remote_info.get('version')})")
    else:
        if remote_info:
            logging.info(f"    [UPDATE] dump_runner.elf (Hash Mismatch)")
            logging.info(f"        Remote: {remote_info.get('version')} -> Local: {LOCAL_PAYLOAD_META['version']}")
        else:
            logging.info(f"    [INSTALL] dump_runner.elf (Missing/No Metadata)")
        needs_payload_update = True

    if needs_payload_update and os.path.exists(local_elf):
        with open(local_elf, "rb") as f:
            ftp.storbinary(f"STOR {remote_elf}", f)
        
        meta_json = json.dumps(LOCAL_PAYLOAD_META)
        bio_meta = io.BytesIO(meta_json.encode('utf-8'))
        ftp.storbinary(f"STOR {remote_meta}", bio_meta)

    # --- 2. JS SYNC ---
    js_content = JS_TEMPLATE.format(usb_path=source_path, tool_version=TOOL_VERSION)
    remote_js_content = download_remote_text(ftp, remote_js)
    
    needs_js_update = True
    if remote_js_content:
        clean_remote = remote_js_content.replace('\r\n', '\n').strip()
        clean_local = js_content.replace('\r\n', '\n').strip()
        if clean_remote == clean_local:
            needs_js_update = False
            logging.info(f"    [SKIP] homebrew.js (Content match)")
    
    if needs_js_update:
        bio = io.BytesIO(js_content.encode('utf-8'))
        ftp.storbinary(f"STOR {remote_js}", bio)
        if remote_js_content: logging.info(f"    [UPDATE] homebrew.js refreshed.")
        else: logging.info(f"    [GEN] homebrew.js generated.")

    # --- 3. IMAGES ---
    brute_force_transfer_image(ftp, source_path, target_dir, "icon0.png")
    brute_force_transfer_image(ftp, source_path, target_dir, "pic1.png")
    brute_force_transfer_image(ftp, source_path, target_dir, "pic0.png")

def main():
    setup_logger()
    logging.info(f"--- PS5 GAME SYNC TOOL STARTED ({TOOL_VERSION}) ---")
    print(f"\n=== PS5 GAME SYNC TOOL {TOOL_VERSION} ===")
    
    if not manage_dump_runner():
        logging.critical("[CRITICAL] dump_runner.elf missing/cancelled. Exiting.")
        print("[CRITICAL] dump_runner.elf missing/cancelled.")
        input("Press ENTER to exit...")
        return

    cfg = load_config()
    ftp = connect_ftp(cfg)
    if not ftp: 
        input("Press ENTER to exit...")
        return

    games = scan_games(ftp, cfg['target_base_path'])
    if not games:
        logging.warning("[SCAN] No games found.")
        ftp.quit()
        input("Press ENTER to exit...")
        return

    logging.info(f"[DEPLOY] Processing {len(games)} games...")
    try: ftp.mkd(cfg['target_base_path'])
    except: pass

    count = 0
    for game_name, full_source_path in games:
        logging.info(f"Processing: {game_name}")
        deploy_homebrew(ftp, game_name, full_source_path, cfg['target_base_path'])
        count += 1
        
    ftp.quit()
    print(f"\n[SUCCESS] Processed {count} games.")
    logging.info(f"[SUCCESS] Tool finished. Processed {count} games.")
    print("Log saved to ps5_sync_log.txt")
    input("Press ENTER to exit...")

if __name__ == "__main__":
    main()