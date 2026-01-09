import customtkinter as ctk
import threading
import sys
import os
import json
import time
import ftplib
import urllib.request
import zipfile
import io
import hashlib
import socket
import logging
from datetime import datetime

# --- CONFIGURATION ---
TOOL_VERSION = "v1.2.0"
CONFIG_FILE = "settings.json"
DEFAULT_CONFIG = {
    "ps5_ip": "192.168.1.30",
    "ps5_ftp_port": 1337,
    "ps5_payload_port": 9021, # Default for etaHEN Elf Loader
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
/* Generated with PS5 Dump Game Sync Tool {tool_version} */
async function main() {{
    const LOCAL_PATH = window.workingDir;
    const PAYLOAD = LOCAL_PATH + '/dump_runner.elf';
    const USB_GAME_PATH = '{usb_path}';
    
    const PARAM_JSON_URL = baseURL + '/fs/' + USB_GAME_PATH + '/sce_sys/param.json';
    const ICON_PATH = 'file://' + LOCAL_PATH + '/sce_sys/icon0.png';
    const BG_PATH = 'file://' + LOCAL_PATH + '/sce_sys/pic1.png'; 

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
                // 2. Try English
                if (!name) {{
                    for (const key in param.localizedParameters) {{
                        if (key.startsWith('en-')) {{
                            name = param.localizedParameters[key].titleName;
                            break;
                        }}
                    }}
                }}
                // 3. First Available
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

# --- LOGIC HELPERS ---
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

def save_config(new_config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(new_config, f, indent=4)

def calculate_file_md5(filepath):
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except: return None

def calculate_bytes_md5(data_bytes):
    hash_md5 = hashlib.md5()
    hash_md5.update(data_bytes)
    return hash_md5.hexdigest()

def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'PS5SyncTool'})
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except: return None

def format_datetime(iso_str):
    try: return iso_str.replace('T', ' ').replace('Z', '')[:16]
    except: return iso_str

def download_file_to_memory(url):
    try:
        with urllib.request.urlopen(url) as response:
            if response.status == 200:
                return response.read()
    except Exception as e:
        print(f"[ERR] Download failed: {e}")
    return None

def inject_payload(ip, port, data_bytes):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((ip, port))
            s.sendall(data_bytes)
        return True
    except Exception as e:
        print(f"[INJECT ERR] {e}")
        return False

def check_port_open(ip, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            return s.connect_ex((ip, port)) == 0
    except:
        return False

# --- GUI CLASSES ---

class ConsoleRedirector:
    """Przekierowuje print() do okna tekstowego z dodawaniem Timestampów."""
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, str_val):
        if str_val.strip():
            current_time = datetime.now().strftime("[%H:%M:%S] ")
            str_val = f"{current_time}{str_val}"
            
        try:
            self.text_widget.configure(state="normal")
            self.text_widget.insert("end", str_val)
            self.text_widget.see("end")
            self.text_widget.configure(state="disabled")
        except: pass

    def flush(self): pass

# --- WINDOW: DUMP RUNNER MANAGER (UPDATED) ---
class PayloadUpdateWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.geometry("600x600")
        self.title("Dump Runner Manager")
        self.attributes("-topmost", True)
        
        self.head_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.head_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(self.head_frame, text="Dump Runner Releases", font=("Roboto", 18, "bold")).pack(side="left")
        
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.status_lbl = ctk.CTkLabel(self, text="Fetching GitHub Data...", text_color="orange")
        self.status_lbl.pack(pady=5)

        threading.Thread(target=self.fetch_info, daemon=True).start()

    def fetch_info(self):
        # 1. Fetch Beta (Actions)
        beta_url = "https://api.github.com/repos/EchoStretch/dump_runner/actions/runs?branch=main&status=success&per_page=1"
        beta_data = fetch_json(beta_url)
        
        if not self.winfo_exists(): return
        
        # 2. Fetch Releases
        releases_url = "https://api.github.com/repos/EchoStretch/dump_runner/releases"
        releases_data = fetch_json(releases_url)
        
        if not self.winfo_exists(): return
        
        self.status_lbl.configure(text=f"Found {len(releases_data) if releases_data else 0} releases.", text_color="gray")

        # --- BETA CARD ---
        if beta_data and beta_data.get('workflow_runs'):
            run = beta_data['workflow_runs'][0]
            sha = run.get('head_sha', '')[:7]
            date = format_datetime(run.get('updated_at', ''))
            msg = run.get('head_commit', {}).get('message', '').split('\n')[0][:60]
            d_url = "https://nightly.link/EchoStretch/dump_runner/workflows/build.yml/main/dump_runner.zip"
            
            card = ctk.CTkFrame(self.scroll, border_width=1, border_color="#E0A800")
            card.pack(fill="x", pady=10, padx=5)
            
            ctk.CTkLabel(card, text=f"⚡ LATEST BETA (Nightly)", font=("Roboto", 14, "bold"), text_color="#E0A800").pack(anchor="w", padx=10, pady=(10,0))
            ctk.CTkLabel(card, text=f"Commit: {sha} | {date}", font=("Consolas", 12)).pack(anchor="w", padx=10)
            ctk.CTkLabel(card, text=f"Msg: {msg}", font=("Consolas", 11), text_color="gray").pack(anchor="w", padx=10, pady=(0,5))
            
            btn = ctk.CTkButton(card, text="DOWNLOAD & UPDATE LOCAL", fg_color="#E0A800", text_color="black", hover_color="#C69500",
                                command=lambda: self.download_and_install(d_url, f"Beta {sha}", date))
            btn.pack(fill="x", padx=10, pady=10)

        # --- RELEASES CARDS ---
        if releases_data:
            for release in releases_data:
                tag = release.get('tag_name', 'v?')
                name = release.get('name', tag)
                body = release.get('body', '').replace('\r\n', '\n')
                date = format_datetime(release.get('published_at', ''))
                assets = release.get('assets', [])
                
                # Find zip or elf
                d_url = next((a['browser_download_url'] for a in assets if a['name'].endswith('.zip') or a['name'].endswith('.elf')), None)
                
                if not d_url: continue

                card = ctk.CTkFrame(self.scroll, border_width=1, border_color="#444")
                card.pack(fill="x", pady=10, padx=5)
                
                info_frame = ctk.CTkFrame(card, fg_color="transparent")
                info_frame.pack(fill="x", padx=10, pady=(10, 5))
                ctk.CTkLabel(info_frame, text=f"{name} ({tag})", font=("Roboto", 12), text_color="gray").pack(anchor="w")
                ctk.CTkLabel(info_frame, text=f"Released: {date}", font=("Roboto", 12), text_color="gray").pack(anchor="w")
                
                # Changelog
                changelog_box = ctk.CTkTextbox(info_frame, height=80, font=("Consolas", 11), text_color="#ccc", fg_color="#2b2b2b", wrap="word")
                changelog_box.insert("0.0", body)
                changelog_box.configure(state="disabled")
                changelog_box.pack(fill="x", pady=5)
                
                btn = ctk.CTkButton(card, text=f"DOWNGRADE / INSTALL {tag}", fg_color="#333", hover_color="#222",
                                     command=lambda u=d_url, t=tag, d=date: self.download_and_install(u, t, d))
                btn.pack(fill="x", padx=10, pady=10)

    def download_and_install(self, url, label, date):
        self.status_lbl.configure(text=f"Downloading {label}...", text_color="orange")
        threading.Thread(target=self._worker_install, args=(url, label, date), daemon=True).start()

    def _worker_install(self, url, label, date):
        try:
            data_bytes = download_file_to_memory(url)
            if data_bytes:
                # Check if zip or elf
                is_zip = url.endswith('.zip') or (data_bytes[:2] == b'PK')
                
                if is_zip:
                    with io.BytesIO(data_bytes) as bio:
                        with zipfile.ZipFile(bio) as z:
                            elf_name = next((n for n in z.namelist() if n.endswith('dump_runner.elf')), None)
                            if elf_name:
                                with open("dump_runner.elf", "wb") as f_out:
                                    f_out.write(z.read(elf_name))
                else:
                    # Assume direct elf
                    with open("dump_runner.elf", "wb") as f_out:
                        f_out.write(data_bytes)

                LOCAL_PAYLOAD_META["version"] = label
                LOCAL_PAYLOAD_META["date"] = date
                LOCAL_PAYLOAD_META["md5"] = calculate_file_md5("dump_runner.elf")
                
                print(f"[GUI] Updated local payload to {label}")
                self.status_lbl.configure(text=f"Updated to {label}", text_color="green")
            else:
                self.status_lbl.configure(text="Download failed", text_color="red")
        except Exception as e:
            print(f"[ERR] {e}")
            self.status_lbl.configure(text="Error", text_color="red")

# --- WINDOW: KSTUFF MANAGER (NEW) ---
class KstuffManagerWindow(ctk.CTkToplevel):
    def __init__(self, parent, ip, port_ftp):
        super().__init__(parent)
        self.geometry("600x600")
        self.title("Kstuff Manager")
        self.attributes("-topmost", True)
        self.ip = ip
        self.port_f = port_ftp

        self.head_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.head_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(self.head_frame, text="Kstuff Releases", font=("Roboto", 18, "bold")).pack(side="left")
        
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.status_lbl = ctk.CTkLabel(self, text="Fetching releases...", text_color="orange")
        self.status_lbl.pack(pady=5)

        threading.Thread(target=self.fetch_releases, daemon=True).start()

    def fetch_releases(self):
        url = "https://api.github.com/repos/EchoStretch/kstuff/releases"
        releases = fetch_json(url)
        
        if not self.winfo_exists(): return 

        if not releases:
            self.status_lbl.configure(text="Error fetching releases.", text_color="red")
            return
            
        self.status_lbl.configure(text=f"Found {len(releases)} releases.", text_color="gray")

        for release in releases:
            if not self.winfo_exists(): return

            tag = release.get('tag_name', 'Unknown')
            name = release.get('name', tag)
            body = release.get('body', '').replace('\r\n', '\n')
            assets = release.get('assets', [])
            date = format_datetime(release.get('published_at', ''))
            
            d_url = next((a['browser_download_url'] for a in assets if a['name'].endswith('.elf') or a['name'].endswith('.bin')), None)
            
            if not d_url: continue 

            try:
                card = ctk.CTkFrame(self.scroll, border_width=1, border_color="#444")
                card.pack(fill="x", pady=10, padx=5)
                
                info_frame = ctk.CTkFrame(card, fg_color="transparent")
                info_frame.pack(fill="x", padx=10, pady=(10, 5))
                ctk.CTkLabel(info_frame, text=f"{name} ({tag})", font=("Roboto", 14, "bold")).pack(anchor="w")
                ctk.CTkLabel(info_frame, text=f"Released: {date}", font=("Roboto", 12), text_color="gray").pack(anchor="w")
                
                changelog_box = ctk.CTkTextbox(info_frame, height=80, font=("Consolas", 11), text_color="#ccc", fg_color="#2b2b2b", wrap="word")
                changelog_box.insert("0.0", body)
                changelog_box.configure(state="disabled")
                changelog_box.pack(fill="x", pady=5)
                
                btn_install = ctk.CTkButton(card, text=f"INSTALL {tag} (FTP)", width=140, fg_color="#333", hover_color="#222",
                                          command=lambda u=d_url, t=tag: self.ftp_install(u, t))
                btn_install.pack(fill="x", padx=10, pady=10)
            except Exception: return

    def ftp_install(self, url, tag):
        threading.Thread(target=self._worker_install, args=(url, tag), daemon=True).start()

    def _worker_install(self, url, tag):
        self.status_lbl.configure(text=f"Downloading {tag}...", text_color="orange")
        bin_data = download_file_to_memory(url)
        if not bin_data:
            self.status_lbl.configure(text="Download failed.", text_color="red")
            return

        try:
            ftp = ftplib.FTP()
            ftp.connect(self.ip, self.port_f, timeout=10)
            ftp.login()
            
            remote_dir = "/data/etaHEN"
            try: ftp.mkd(remote_dir)
            except: pass
            
            remote_path = f"{remote_dir}/kstuff.elf"
            print(f"\n[FTP] Uploading kstuff.elf to {remote_path}...")
            ftp.storbinary(f"STOR {remote_path}", io.BytesIO(bin_data))
            ftp.quit()
            
            print(f"[FTP] Installed Kstuff {tag}. REBOOT PS5!")
            self.status_lbl.configure(text=f"Installed {tag}. Reboot required!", text_color="green")
        except Exception as e:
            print(f"[FTP ERR] {e}")
            self.status_lbl.configure(text="FTP Error.", text_color="red")

# --- WINDOW: SHADOWMOUNT CENTER ---
class ShadowMountWindow(ctk.CTkToplevel):
    def __init__(self, parent, ip, port_payload, port_ftp):
        super().__init__(parent)
        self.geometry("600x600")
        self.title("ShadowMount Center")
        self.attributes("-topmost", True)
        self.ip = ip
        self.port_p = port_payload
        self.port_f = port_ftp

        self.head_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.head_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(self.head_frame, text="ShadowMount Releases", font=("Roboto", 18, "bold")).pack(side="left")
        
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.status_lbl = ctk.CTkLabel(self, text="Fetching versions from GitHub...", text_color="orange")
        self.status_lbl.pack(pady=5)

        threading.Thread(target=self.fetch_releases, daemon=True).start()

    def fetch_releases(self):
        url = "https://api.github.com/repos/voidwhisper-ps/ShadowMount/releases"
        releases = fetch_json(url)
        
        if not self.winfo_exists(): return
        
        if not releases:
            self.status_lbl.configure(text="Error fetching releases.", text_color="red")
            return
            
        self.status_lbl.configure(text=f"Found {len(releases)} releases.", text_color="gray")

        for release in releases:
            if not self.winfo_exists(): return
            tag = release.get('tag_name', 'Unknown')
            name = release.get('name', tag)
            body = release.get('body', '').replace('\r\n', '\n') 
            assets = release.get('assets', [])
            
            url_shadow = next((a['browser_download_url'] for a in assets if a['name'].lower() == 'shadowmount.elf'), None)
            url_notify = next((a['browser_download_url'] for a in assets if a['name'].lower() == 'notify.elf'), None)
            
            if not url_shadow: continue 

            card = ctk.CTkFrame(self.scroll, border_width=1, border_color="#444")
            card.pack(fill="x", pady=10, padx=5)
            
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(fill="x", padx=10, pady=(10, 5))
            ctk.CTkLabel(info_frame, text=f"{name} ({tag})", font=("Roboto", 14, "bold")).pack(anchor="w")
            
            changelog_box = ctk.CTkTextbox(info_frame, height=100, font=("Consolas", 11), text_color="#ccc", fg_color="#2b2b2b", wrap="word")
            changelog_box.insert("0.0", body)
            changelog_box.configure(state="disabled")
            changelog_box.pack(fill="x", pady=5)
            
            btn_frame = ctk.CTkFrame(card, fg_color="transparent")
            btn_frame.pack(fill="x", padx=10, pady=10)

            if url_notify:
                btn_launch = ctk.CTkButton(btn_frame, text="⚡ LAUNCH (Inject)", width=140, fg_color="#E0A800", text_color="black", hover_color="#C69500",
                                         command=lambda u1=url_notify, u2=url_shadow, t=tag: self.sequence_inject(u1, u2, t))
                btn_launch.pack(side="right", padx=5)
            else:
                btn_launch = ctk.CTkButton(btn_frame, text="⚠ No notify.elf", state="disabled", width=140)
                btn_launch.pack(side="right", padx=5)

            btn_install = ctk.CTkButton(btn_frame, text="💾 INSTALL (FTP)", width=140, fg_color="#333", hover_color="#222",
                                      command=lambda u=url_shadow, t=tag: self.ftp_install(u, t))
            btn_install.pack(side="right", padx=5)

    def sequence_inject(self, url_notify, url_shadow, tag):
        threading.Thread(target=self._worker_inject, args=(url_notify, url_shadow, tag), daemon=True).start()

    def _worker_inject(self, url_notify, url_shadow, tag):
        self.status_lbl.configure(text=f"Downloading {tag}...", text_color="orange")
        
        bin_notify = download_file_to_memory(url_notify)
        bin_shadow = download_file_to_memory(url_shadow)
        
        if not bin_notify or not bin_shadow:
            self.status_lbl.configure(text="Download failed.", text_color="red")
            return

        self.status_lbl.configure(text="Injecting notify.elf...", text_color="cyan")
        print(f"\n[INJECT] Sending notify.elf ({len(bin_notify)} bytes) to {self.ip}:{self.port_p}...")
        
        if inject_payload(self.ip, self.port_p, bin_notify):
            print("[INJECT] Notify sent. Waiting 3 seconds...")
            self.status_lbl.configure(text="Waiting 3s...", text_color="cyan")
            time.sleep(3)
            
            print(f"[INJECT] Sending shadowmount.elf ({len(bin_shadow)} bytes)...")
            self.status_lbl.configure(text="Injecting ShadowMount...", text_color="cyan")
            if inject_payload(self.ip, self.port_p, bin_shadow):
                print("[INJECT] SUCCESS! ShadowMount should be active.")
                self.status_lbl.configure(text=f"Success! {tag} injected.", text_color="green")
            else:
                self.status_lbl.configure(text="Failed to send ShadowMount.", text_color="red")
        else:
            self.status_lbl.configure(text="Failed to send Notify.", text_color="red")

    def ftp_install(self, url_shadow, tag):
        threading.Thread(target=self._worker_install, args=(url_shadow, tag), daemon=True).start()

    def _worker_install(self, url_shadow, tag):
        self.status_lbl.configure(text=f"Installing {tag}...", text_color="orange")
        bin_shadow = download_file_to_memory(url_shadow)
        if not bin_shadow:
            self.status_lbl.configure(text="Download failed.", text_color="red")
            return

        try:
            ftp = ftplib.FTP()
            ftp.connect(self.ip, self.port_f, timeout=10)
            ftp.login()
            
            remote_dir = "/data/etaHEN/payloads"
            try: ftp.mkd(remote_dir)
            except: pass
            
            print(f"\n[FTP] Uploading shadowmount.elf to {remote_dir}...")
            ftp.storbinary(f"STOR {remote_dir}/shadowmount.elf", io.BytesIO(bin_shadow))
            ftp.quit()
            
            print("[FTP] Install Complete.")
            self.status_lbl.configure(text=f"Installed {tag} to FTP.", text_color="green")
        except Exception as e:
            print(f"[FTP ERR] {e}")
            self.status_lbl.configure(text="FTP Error.", text_color="red")


# --- MAIN APP ---
class PS5SyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()

        self.title(f"PS5 Dump Game Sync Tool {TOOL_VERSION}")
        self.geometry("850x650")
        self.resizable(False, False)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("green")

        # Tabs
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)
        self.tab_dash = self.tabview.add("Dashboard")
        self.tab_settings = self.tabview.add("Settings")
        self.tab_console = self.tabview.add("Console Log")

        # --- DASHBOARD ---
        self.frame_status = ctk.CTkFrame(self.tab_dash, fg_color="transparent")
        self.frame_status.pack(fill="x", pady=10)
        self.lbl_status_icon = ctk.CTkLabel(self.frame_status, text="●", font=("Arial", 24), text_color="gray")
        self.lbl_status_icon.pack(side="left", padx=(10, 5))
        self.lbl_status_text = ctk.CTkLabel(self.frame_status, text="Not Connected", font=("Roboto", 16, "bold"))
        self.lbl_status_text.pack(side="left")
        
        self.btn_check_conn = ctk.CTkButton(self.frame_status, text="Test Connection", width=120, fg_color="#444", command=self.check_connection_gui)
        self.btn_check_conn.pack(side="right", padx=10)

        self.frame_main = ctk.CTkFrame(self.tab_dash)
        self.frame_main.pack(fill="both", expand=True, pady=10, padx=10)
        
        self.btn_sync = ctk.CTkButton(self.frame_main, text="START GAME SYNC", font=("Roboto", 20, "bold"), height=80, 
                                      fg_color="#1f6aa5", hover_color="#144870", command=self.start_sync_thread)
        self.btn_sync.pack(fill="x", padx=40, pady=(40, 20))
        
        self.progress = ctk.CTkProgressBar(self.frame_main)
        self.progress.pack(fill="x", padx=40, pady=10)
        self.progress.set(0)

        # --- NOWA ETYKIETA SUKCESU ---
        self.lbl_sync_status = ctk.CTkLabel(self.frame_main, text="", font=("Roboto", 14, "bold"))
        self.lbl_sync_status.pack(pady=(5, 0))

        self.frame_updates = ctk.CTkFrame(self.tab_dash, fg_color="transparent")
        self.frame_updates.pack(fill="x", pady=10)

        self.btn_payload = ctk.CTkButton(self.frame_updates, text="Dump Runner\nManager", command=self.open_payload_manager, fg_color="#333", hover_color="#222")
        self.btn_payload.pack(side="left", fill="x", expand=True, padx=5)
        
        self.btn_kstuff = ctk.CTkButton(self.frame_updates, text="Kstuff\nManager", command=self.open_kstuff_manager, fg_color="#333", hover_color="#222")
        self.btn_kstuff.pack(side="left", fill="x", expand=True, padx=5)

        self.btn_shadow = ctk.CTkButton(self.frame_updates, text="ShadowMount\nCenter", command=self.open_shadow_center, fg_color="#E0A800", text_color="black", hover_color="#C69500")
        self.btn_shadow.pack(side="left", fill="x", expand=True, padx=5)

        # --- SETTINGS ---
        self.lbl_ip = ctk.CTkLabel(self.tab_settings, text="PS5 IP Address:", font=("Roboto", 14))
        self.lbl_ip.pack(pady=(20, 5))
        self.entry_ip = ctk.CTkEntry(self.tab_settings, width=200, justify="center")
        self.entry_ip.pack(pady=5)
        self.entry_ip.insert(0, self.cfg.get("ps5_ip", ""))

        self.lbl_port = ctk.CTkLabel(self.tab_settings, text="FTP Port:", font=("Roboto", 14))
        self.lbl_port.pack(pady=(10, 5))
        self.entry_port = ctk.CTkEntry(self.tab_settings, width=100, justify="center")
        self.entry_port.pack(pady=5)
        self.entry_port.insert(0, str(self.cfg.get("ps5_ftp_port", 1337)))

        self.lbl_port_pl = ctk.CTkLabel(self.tab_settings, text="Payload Port (default: 9021):", font=("Roboto", 14))
        self.lbl_port_pl.pack(pady=(10, 5))
        self.entry_port_pl = ctk.CTkEntry(self.tab_settings, width=100, justify="center")
        self.entry_port_pl.pack(pady=5)
        self.entry_port_pl.insert(0, str(self.cfg.get("ps5_payload_port", 9021)))

        self.btn_save = ctk.CTkButton(self.tab_settings, text="Save Settings", width=150, fg_color="green", command=self.save_settings)
        self.btn_save.pack(pady=30)

        # --- CONSOLE ---
        self.txt_console = ctk.CTkTextbox(self.tab_console, font=("Consolas", 11))
        self.txt_console.pack(fill="both", expand=True, padx=5, pady=5)
        self.txt_console.configure(state="disabled")

        self.redirector = ConsoleRedirector(self.txt_console)
        sys.stdout = self.redirector
        sys.stderr = self.redirector
        
        if os.path.exists("dump_runner.elf"):
            LOCAL_PAYLOAD_META["md5"] = calculate_file_md5("dump_runner.elf")
            print(f"[INIT] Local dump_runner ready.")
        else:
            print("[INIT] Missing payload. Go to Dashboard -> Dump Runner Manager.")

    # --- FUNCTIONS ---
    def save_settings(self):
        self.cfg["ps5_ip"] = self.entry_ip.get()
        self.cfg["ps5_ftp_port"] = int(self.entry_port.get())
        self.cfg["ps5_payload_port"] = int(self.entry_port_pl.get())
        save_config(self.cfg)
        print("[CFG] Settings saved.")

    def open_payload_manager(self): PayloadUpdateWindow(self)
    
    def open_kstuff_manager(self):
        ip = self.entry_ip.get()
        port_f = int(self.entry_port.get())
        KstuffManagerWindow(self, ip, port_f)
    
    def open_shadow_center(self):
        ip = self.entry_ip.get()
        port_p = int(self.entry_port_pl.get())
        port_f = int(self.entry_port.get())
        ShadowMountWindow(self, ip, port_p, port_f)
    
    def check_connection_gui(self): threading.Thread(target=self._logic_check_conn, daemon=True).start()

    def start_sync_thread(self):
        if not os.path.exists("dump_runner.elf"):
            print("[ERR] Missing dump_runner.elf! Download it first.")
            self.tabview.set("Console Log")
            return
        
        # Reset GUI
        self.btn_sync.configure(state="disabled", text="SYNCING...")
        self.progress.configure(mode="indeterminate")
        self.lbl_sync_status.configure(text="") # Clear previous status
        self.progress.start()
        
        threading.Thread(target=self._logic_sync, daemon=True).start()

    def _connect_ftp(self):
        ip = self.entry_ip.get()
        port = int(self.entry_port.get())

        try:
            ftp = ftplib.FTP()
            ftp.connect(ip, port, timeout=10)
            ftp.login()
            return ftp
        except Exception as e:
            print(f"[ERR] FTP Connection failed: {e}")
            return None

    def _logic_check_conn(self):
        ip = self.entry_ip.get()
        port_ftp = int(self.entry_port.get())
        port_pl = int(self.entry_port_pl.get())
        
        self.lbl_status_icon.configure(text_color="orange")
        self.lbl_status_text.configure(text="Checking services...")
        
        ftp_ok = check_port_open(ip, port_ftp)
        pl_ok = check_port_open(ip, port_pl)
        
        if ftp_ok and pl_ok:
            self.lbl_status_icon.configure(text_color="#2CC985")
            self.lbl_status_text.configure(text=f"Connected (Full Access)")
            print(f"[CONN] FTP:{port_ftp} [OK] | Payload:{port_pl} [OK]")
        elif ftp_ok:
            self.lbl_status_icon.configure(text_color="orange")
            self.lbl_status_text.configure(text=f"FTP Only (No Injection)")
            print(f"[CONN] FTP:{port_ftp} [OK] | Payload:{port_pl} [FAIL]")
        else:
            self.lbl_status_icon.configure(text_color="red")
            self.lbl_status_text.configure(text="Connection Failed")
            print(f"[CONN] Failed to connect to {ip}")

    # --- SYNC LOGIC ---
    def _logic_sync(self):
        print("\n--- STARTING SYNC ---")
        self.check_connection_gui()
        
        ftp = self._connect_ftp()
        if not ftp: self._stop_sync_ui(); return

        target_base = self.cfg['target_base_path']
        search_paths = ["/data/homebrew", "/data/etaHEN/games", "/data/games"]
        for i in range(8): search_paths.extend([f"/mnt/usb{i}/homebrew", f"/mnt/usb{i}/etaHEN/games"])
        for i in range(8): search_paths.append(f"/mnt/ext{i}/homebrew")

        found_games = []
        processed = set()
        
        print("[SCAN] Scanning storage...")
        for path in search_paths:
            try:
                ftp.cwd(path)
                items = ftp.nlst()
                for item in items:
                    if "." in item: continue
                    full_path = f"{path}/{item}"
                    if full_path in processed: continue
                    try:
                        ftp.size(f"{full_path}/sce_sys/param.json")
                        found_games.append((item, full_path))
                        processed.add(full_path)
                    except: pass
            except: continue
        
        print(f"[SCAN] Found {len(found_games)} games.")
        try: ftp.mkd(target_base)
        except: pass
        
        for name, src_path in found_games:
            print(f"Syncing: {name}...")
            self._deploy_game(ftp, name, src_path, target_base)
        
        print("[DONE] Sync Complete.")
        ftp.quit()
        self._stop_sync_ui(success=True)

    def _stop_sync_ui(self, success=False):
        self.progress.stop()
        self.progress.set(1)
        self.btn_sync.configure(state="normal", text="START GAME SYNC")
        
        if success:
            self.lbl_sync_status.configure(text="✔ Synchronizacja zakończona pomyślnie!", text_color="#2CC985")
        else:
            self.lbl_sync_status.configure(text="❌ Błąd synchronizacji (Sprawdź konsolę)", text_color="red")

    def _deploy_game(self, ftp, game_name, src_path, target_base):
        tgt_dir = f"{target_base}/{game_name}"
        try: ftp.mkd(tgt_dir)
        except: pass

        remote_meta_path = f"{tgt_dir}/payload_version.json"
        remote_md5 = None
        try:
            bio = io.BytesIO()
            ftp.retrbinary(f"RETR {remote_meta_path}", bio.write)
            remote_md5 = json.loads(bio.getvalue().decode()).get("md5")
        except: pass

        if remote_md5 != LOCAL_PAYLOAD_META["md5"]:
            try:
                with open("dump_runner.elf", "rb") as f:
                    ftp.storbinary(f"STOR {tgt_dir}/dump_runner.elf", f)
                m_json = json.dumps(LOCAL_PAYLOAD_META).encode()
                ftp.storbinary(f"STOR {remote_meta_path}", io.BytesIO(m_json))
                print("  -> Payload Updated")
            except: pass

        js_code = JS_TEMPLATE.format(usb_path=src_path, tool_version=TOOL_VERSION)
        remote_js = ""
        try:
            bio = io.BytesIO()
            ftp.retrbinary(f"RETR {tgt_dir}/homebrew.js", bio.write)
            remote_js = bio.getvalue().decode()
        except: pass
        
        if remote_js.strip() != js_code.strip():
             ftp.storbinary(f"STOR {tgt_dir}/homebrew.js", io.BytesIO(js_code.encode()))
             print("  -> JS Updated")

        for img in ["icon0.png", "pic1.png", "pic0.png"]:
            try:
                if ftp.size(f"{tgt_dir}/{img}") > 0: continue
            except: pass
            try:
                bio = io.BytesIO()
                ftp.retrbinary(f"RETR {src_path}/sce_sys/{img}", bio.write)
                bio.seek(0)
                ftp.storbinary(f"STOR {tgt_dir}/{img}", bio)
            except: pass

if __name__ == "__main__":
    app = PS5SyncApp()
    app.mainloop()