import os
import sys
import json
import zipfile
import threading
import subprocess

# ==========================================
# 🛡️ 關鍵修正：必須先 import tkinter，讓 PyInstaller 靜態掃描能抓到庫
# ==========================================
import tkinter as tk
from tkinter import ttk, messagebox

# ==========================================
# 🛡️ 系統層級防禦：強行校正 Tcl/Tk 路徑（放在 import 之後）
# ==========================================
if getattr(sys, 'frozen', False):
    pass
else:
    python_home = os.path.dirname(sys.executable)
    os.environ["TCL_LIBRARY"] = os.path.join(python_home, "tcl", "tcl8.6")
    os.environ["TK_LIBRARY"] = os.path.join(python_home, "tcl", "tk8.6")

# ==========================================
# 📂 模組 1：路徑與設定管理 (Config)
# ==========================================
class AppConfig:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.engines_dir = os.path.join(self.base_dir, "engines")
        self.standard_dir = os.path.join(self.engines_dir, "standard")
        self.mono_dir = os.path.join(self.engines_dir, "mono")
        self.config_file = os.path.join(self.base_dir, "launcher_config.json")

        os.makedirs(self.standard_dir, exist_ok=True)
        os.makedirs(self.mono_dir, exist_ok=True)
        
        self.current_lang = self.load_lang()
        self.setup_translations()

    def load_lang(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f).get("language", "en")
            except: pass
        return "en"

    def save_lang(self, lang):
        self.current_lang = lang
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump({"language": lang}, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"設定存檔失敗: {e}")

    def setup_translations(self):
        self.translations = {
            "zh_TW": {
                "checking": "正在檢查 Godot 最新版本...", "skip": "跳過檢查", "latest_v": "最新版本: ",
                "checking_local": "檢查本地檔案...", "dl_std": "正在下載 Standard {}...", "dl_mono": "正在下載 C# Mono {}...",
                "title": "Godot 引擎啟動器", "side_title": "快捷與管理", "btn_check": "🔄 檢查更新",
                "btn_open_std": "開啟 Standard 目錄", "btn_open_mono": "開啟 Mono 目錄", "btn_open_all": "開啟總資料夾",
                "btn_run_std": "🚀 啟動 Standard 一般版本", "btn_run_mono": "🛠️ 啟動 C# (Mono) 版本",
                "tip": "提示：若點擊無反應，請確認資料夾內是否有對應的執行檔。", "checking_all": "正在檢查與校正引擎版本...",
                "msg_success_t": "檢查完成", "msg_success_c": "版本檢查與補件完成！", "msg_err_t": "錯誤",
                "msg_err_c": "檢查失敗: ", "msg_no_exe": "找不到 Godot 執行檔！請重新下載。", "lang_label": "語言:"
            },
            "en": {
                "checking": "Checking for updates...", "skip": "Skip", "latest_v": "Latest: ",
                "checking_local": "Checking local files...", "dl_std": "Downloading Standard {}...", "dl_mono": "Downloading Mono {}...",
                "title": "Godot Launcher", "side_title": "Management", "btn_check": "🔄 Check Update",
                "btn_open_std": "Open Standard", "btn_open_mono": "Open Mono", "btn_open_all": "Open Root",
                "btn_run_std": "🚀 Launch Standard", "btn_run_mono": "🛠️ Launch C# (Mono)",
                "tip": "Tip: Make sure the executable exists if no response.", "checking_all": "Checking engine versions...",
                "msg_success_t": "Completed", "msg_success_c": "Check and install completed!", "msg_err_t": "Error",
                "msg_err_c": "Check failed: ", "msg_no_exe": "Executable not found! Please redownload.", "lang_label": "Language:"
            }
        }

    def t(self, key):
        return self.translations[self.current_lang].get(key, key)

# ==========================================
# ⚙️ 模組 2：核心業務邏輯 (Manager)
# ==========================================
class GodotManager:
    def __init__(self, config: AppConfig):
        self.config = config
        self.latest_version = None
        self.download_links = {"standard": None, "mono": None}

    def fetch_latest_info(self):
        import requests
        api_url = "https://api.github.com/repos/godotengine/godot/releases/latest"
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()
        data = response.json()
        self.latest_version = data["tag_name"]  # 例如 "4.3-stable"
        
        for asset in data.get("assets", []):
            name = asset["name"]
            url = asset["browser_download_url"]
            if "win64" in name:
                if "mono" in name: self.download_links["mono"] = url
                else: self.download_links["standard"] = url

    def has_version_locally(self, target_dir, version_tag):
        """
        掃描特定目錄，確認是否有檔案或資料夾名稱包含最新的版號（例如 "4.3-stable"）。
        如果找到，代表最新版已存在，不需要重複下載。
        """
        if not os.path.exists(target_dir):
            return False
            
        # 清除 tag 前面的 'v'（如果 API 回傳帶有 v 像是 v4.3-stable）
        v_clean = version_tag.lstrip('v')
        
        for name in os.listdir(target_dir):
            if v_clean in name:
                return True
        return False

    def download_and_extract(self, url, target_dir):
        import requests
        zip_path = os.path.join(self.config.engines_dir, "temp.zip")
        res = requests.get(url, stream=True)
        with open(zip_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
        os.remove(zip_path)

    def launch_engine(self, target_dir):
        # 收集目錄下所有的執行檔路徑
        exe_files = []
        for root_path, dirs, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".exe"):
                    exe_files.append(os.path.join(root_path, file))

        if not exe_files:
            return False

        # 核心優化：優先排除 Console 版本的執行檔
        valid_exes = [e for e in exe_files if "Console" not in os.path.basename(e)]
        if not valid_exes:
            valid_exes = exe_files

        # 排序策略：依照路徑與檔名排序，確保最新版本（字母/數字排序最高者）排在最後面
        valid_exes.sort()
        executable = valid_exes[-1]

        if executable:
            subprocess.Popen([executable])
            return True
        return False

# ==========================================
# 🖥️ 模組 3：圖形介面 (GUI)
# ==========================================
class LauncherGUI:
    def __init__(self, root):
        self.root = root
        self.config = AppConfig()
        self.manager = GodotManager(self.config)
        
        self.root.title(self.config.t("title"))
        self.root.geometry("600x380")
        self.root.resizable(False, False)
        
        self.skip_check = False
        self.is_working = False

        self.create_check_screen()
        threading.Thread(target=self.startup_check_routine, daemon=True).start()

    def create_check_screen(self):
        self.check_frame = ttk.Frame(self.root, padding=20)
        self.check_frame.pack(fill=tk.BOTH, expand=True)
        self.status_label = ttk.Label(self.check_frame, text=self.config.t("checking"), font=("Microsoft JhengHei", 12))
        self.status_label.pack(pady=30)
        self.progress_bar = ttk.Progressbar(self.check_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, pady=10)
        self.progress_bar.start(10)
        self.skip_btn = ttk.Button(self.check_frame, text=self.config.t("skip"), command=self.do_skip)
        self.skip_btn.pack(pady=20)

    def do_skip(self):
        self.skip_check = True
        self.enter_main_screen()

    def update_status(self, text):
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.config(text=text)

    def startup_check_routine(self):
        try:
            self.manager.fetch_latest_info()
            if self.skip_check: return
            
            self.root.after(0, lambda: self.update_status(f"{self.config.t('latest_v')}{self.manager.latest_version}\n{self.config.t('checking_local')}"))
            
            c = self.config
            m = self.manager
            
            # 關鍵邏輯變更：直接比對檔名中是否含有最新 tag_name
            if not m.has_version_locally(c.standard_dir, m.latest_version) and m.download_links["standard"]:
                self.root.after(0, lambda: self.update_status(c.t("dl_std").format(m.latest_version)))
                m.download_and_extract(m.download_links["standard"], c.standard_dir)

            if not m.has_version_locally(c.mono_dir, m.latest_version) and m.download_links["mono"]:
                self.root.after(0, lambda: self.update_status(c.t("dl_mono").format(m.latest_version)))
                m.download_and_extract(m.download_links["mono"], c.mono_dir)

        except Exception as e:
            print(f"啟動檢查失敗: {e}")
        finally:
            if not self.skip_check:
                self.root.after(0, self.enter_main_screen)

    def enter_main_screen(self):
        if hasattr(self, 'check_frame') and self.check_frame.winfo_exists():
            self.check_frame.destroy()
        self.create_main_screen()

    def create_main_screen(self):
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 側邊欄
        self.side_panel = ttk.Frame(self.main_frame, width=170, relief=tk.GROOVE, padding=10)
        self.side_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.side_panel.pack_propagate(False)

        c = self.config
        self.lbl_side_title = ttk.Label(self.side_panel, text=c.t("side_title"), font=("Microsoft JhengHei", 10, "bold"))
        self.lbl_side_title.pack(pady=5)
        
        self.btn_check = ttk.Button(self.side_panel, text=c.t("btn_check"), command=self.manual_check)
        self.btn_check.pack(fill=tk.X, pady=5)
        ttk.Separator(self.side_panel, orient='horizontal').pack(fill=tk.X, pady=10)

        self.btn_open_std = ttk.Button(self.side_panel, text=c.t("btn_open_std"), command=lambda: self.open_folder(c.standard_dir))
        self.btn_open_std.pack(fill=tk.X, pady=5)
        self.btn_open_mono = ttk.Button(self.side_panel, text=c.t("btn_open_mono"), command=lambda: self.open_folder(c.mono_dir))
        self.btn_open_mono.pack(fill=tk.X, pady=5)
        self.btn_open_all = ttk.Button(self.side_panel, text=c.t("btn_open_all"), command=lambda: self.open_folder(c.engines_dir))
        self.btn_open_all.pack(fill=tk.X, pady=5)

        # 主內容區
        self.content_panel = ttk.Frame(self.main_frame, padding=20)
        self.content_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.title_var = tk.StringVar()
        self.refresh_title()
        self.lbl_title = ttk.Label(self.content_panel, textvariable=self.title_var, font=("Microsoft JhengHei", 14, "bold"))
        self.lbl_title.pack(pady=10)

        self.main_progress = ttk.Progressbar(self.content_panel, mode='indeterminate')
        
        self.btn_std = ttk.Button(self.content_panel, text=c.t("btn_run_std"), command=lambda: self.try_launch(c.standard_dir))
        self.btn_std.pack(fill=tk.X, ipady=15, pady=10)
        self.btn_mono = ttk.Button(self.content_panel, text=c.t("btn_run_mono"), command=lambda: self.try_launch(c.mono_dir))
        self.btn_mono.pack(fill=tk.X, ipady=15, pady=10)

        # 底部區塊
        self.bottom_frame = ttk.Frame(self.content_panel)
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        self.lbl_tip = ttk.Label(self.bottom_frame, text=c.t("tip"), foreground="gray", font=("Microsoft JhengHei", 8))
        self.lbl_tip.pack(side=tk.TOP, anchor=tk.W, pady=2)

        self.lang_frame = ttk.Frame(self.bottom_frame)
        self.lang_frame.pack(side=tk.BOTTOM, anchor=tk.E, pady=5)
        self.lbl_lang = ttk.Label(self.lang_frame, text=c.t("lang_label"), font=("Microsoft JhengHei", 9))
        self.lbl_lang.pack(side=tk.LEFT, padx=5)

        self.lang_combo = ttk.Combobox(self.lang_frame, values=["繁體中文 (zh_TW)", "English (en)"], width=15, state="readonly")
        self.lang_combo.current(1 if c.current_lang == "en" else 0)
        self.lang_combo.bind("<<ComboboxSelected>>", self.on_lang_change)
        self.lang_combo.pack(side=tk.LEFT)

    def refresh_title(self, custom=None):
        if custom:
            self.title_var.set(custom)
        else:
            v_text = f" ({self.config.t('latest_v')}{self.manager.latest_version})" if self.manager.latest_version else " (Offline)"
            self.title_var.set(self.config.t("title") + v_text)

    def on_lang_change(self, event):
        sel = self.lang_combo.get()
        new_lang = "zh_TW" if "繁體中文" in sel else "en"
        self.config.save_lang(new_lang)
        self.refresh_ui_text()

    def refresh_ui_text(self):
        self.root.title(self.config.t("title"))
        self.refresh_title()
        c = self.config
        self.lbl_side_title.config(text=c.t("side_title"))
        self.btn_check.config(text=c.t("btn_check"))
        self.btn_open_std.config(text=c.t("btn_open_std"))
        self.btn_open_mono.config(text=c.t("btn_open_mono"))
        self.btn_open_all.config(text=c.t("btn_open_all"))
        self.btn_std.config(text=c.t("btn_run_std"))
        self.btn_mono.config(text=c.t("btn_run_mono"))
        self.lbl_tip.config(text=c.t("tip"))
        self.lbl_lang.config(text=c.t("lang_label"))

    def open_folder(self, path):
        if sys.platform == "win32": os.startfile(path)
        else: subprocess.run(["xdg-open", path])

    def try_launch(self, target_dir):
        if not self.manager.launch_engine(target_dir):
            messagebox.showerror(self.config.t("msg_err_t"), self.config.t("msg_no_exe"))

    def manual_check(self):
        if self.is_working: return
        self.is_working = True
        self.btn_check.config(state=tk.DISABLED)
        self.main_progress.pack(fill=tk.X, pady=5)
        self.main_progress.start(10)
        self.refresh_title(self.config.t("checking_all"))
        threading.Thread(target=self.manual_check_routine, daemon=True).start()

    def manual_check_routine(self):
        try:
            self.manager.fetch_latest_info()
            c = self.config
            m = self.manager
            
            # 手動更新同樣改為名稱檢查
            if not m.has_version_locally(c.standard_dir, m.latest_version) and m.download_links["standard"]:
                self.root.after(0, lambda: self.refresh_title(c.t("dl_std").format(m.latest_version)))
                m.download_and_extract(m.download_links["standard"], c.standard_dir)

            if not m.has_version_locally(c.mono_dir, m.latest_version) and m.download_links["mono"]:
                self.root.after(0, lambda: self.refresh_title(c.t("dl_mono").format(m.latest_version)))
                m.download_and_extract(m.download_links["mono"], c.mono_dir)
            
            self.root.after(0, lambda: messagebox.showinfo(c.t("msg_success_t"), c.t("msg_success_c")))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(c.t("msg_err_t"), f"{c.t('msg_err_c')}{e}"))
        finally:
            self.root.after(0, self.reset_main_screen)

    def reset_main_screen(self):
        self.is_working = False
        self.btn_check.config(state=tk.NORMAL)
        self.main_progress.stop()
        self.main_progress.pack_forget()
        self.refresh_title()

# ==========================================
# 🚀 程式進入點
# ==========================================
if __name__ == "__main__":
    try: import requests
    except ImportError: subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    
    root = tk.Tk()
    app = LauncherGUI(root)
    root.mainloop()