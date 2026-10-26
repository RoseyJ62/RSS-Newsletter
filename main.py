import json
import os
import sys
import threading
import time
import datetime
import re
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    SOURCE_APP_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(__file__)
    SOURCE_APP_DIR = APP_DIR
SRC_DIR = os.path.join(os.path.dirname(APP_DIR), "src")

# Ensure local modules and the news_digest package are importable.
sys.path.insert(0, SOURCE_APP_DIR)
sys.path.insert(0, SRC_DIR)

from news_digest.models import Source
from news_digest.fetcher import fetch_articles

import scorer
import profile
import ui

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    print("Plyer is not installed. Notifications will be printed to console.")

CONFIG_PATH = os.path.join(APP_DIR, "config_local.json")
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SCHEDULER_POLL_SECONDS = 10
STARTUP_APP_NAME = "NewsDigestController"
DEFAULT_CONFIG = {
    "rss_feeds": [],
    "frequency": "daily",
    "schedule_time": "08:00",
    "schedule_day": "Monday",
    "auto_start_schedule": False,
}

def parse_json_with_trailing_commas(text):
    cleaned = re.sub(r",(\s*[\]}])", r"\1", text)
    return json.loads(cleaned)

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return parse_json_with_trailing_commas(f.read())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Failed to load config_local.json: {exc}")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

def get_startup_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'

    script_path = os.path.abspath(__file__)
    return f'"{sys.executable}" "{script_path}"'

def configure_windows_startup(enabled):
    if os.name != "nt":
        return

    import winreg

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, STARTUP_APP_NAME, 0, winreg.REG_SZ, get_startup_command())
            return

        try:
            winreg.DeleteValue(key, STARTUP_APP_NAME)
        except FileNotFoundError:
            pass

def is_valid_schedule_time(value):
    try:
        datetime.datetime.strptime(value, "%H:%M")
        return True
    except ValueError:
        return False

def should_run_schedule(config, now, last_run_key):
    freq = config.get("frequency", "daily")
    sched_time = config.get("schedule_time", "08:00")
    sched_day = config.get("schedule_day", "Monday")

    if not is_valid_schedule_time(sched_time):
        return False, last_run_key

    current_time_str = now.strftime("%H:%M")
    current_day_str = now.strftime("%A")
    current_date_str = now.strftime("%Y-%m-%d")
    run_key = f"{current_date_str}:{sched_time}"

    if current_time_str != sched_time or last_run_key == run_key:
        return False, last_run_key

    if freq == "daily":
        return True, run_key

    if freq == "weekly" and current_day_str == sched_day:
        return True, run_key

    return False, last_run_key

def notify_digest_ready():
    if not PLYER_AVAILABLE:
        print("NOTIFICATION: Your digest is ready!")
        return

    try:
        notification.notify(
            title="Re(ed)-wind",
            message="Your digest is ready!",
            app_name="News App",
            timeout=5
        )
    except Exception as exc:
        print(f"Notification unavailable: {exc}")

def run_digest(app_root):
    # 1. Load config
    config = load_config()
    
    # 2. Load context
    context = scorer.load_context()
    
    # 3. Load profile
    user_profile = profile.load_profile()
    
    # 4. Fetch articles
    sources = tuple(
        Source(name=url, url=url, category="General", enabled=True)
        for url in config.get("rss_feeds", [])
    )
    
    lookback = 24 if config.get("frequency", "daily") == "daily" else 24 * 7
    articles = fetch_articles(sources, lookback_hours=lookback, max_items=50)
    
    # 5. Score articles
    scored_articles = []
    for art in articles:
        score_data = scorer.score_article(art.title, art.summary, user_profile, context)
        scored_articles.append({
            "article": art,
            "score_data": score_data
        })
        
    # 6. Sort by score DESC
    scored_articles.sort(key=lambda x: x["score_data"]["score"], reverse=True)
    
    notify_digest_ready()
        
    # 7. Display in UI
    # We create a Toplevel window for the digest
    digest_window = tk.Toplevel(app_root)
    ui.NewsAppUI(digest_window, scored_articles)

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("News Digest Controller")
        self.geometry("500x500")
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        self.tab_dashboard = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_dashboard, text="Dashboard")
        self.notebook.add(self.tab_settings, text="Settings")
        
        self.setup_dashboard()
        self.setup_settings()
        
        self.schedule_thread = None
        self.running_schedule = False
        if load_config().get("auto_start_schedule", False):
            self.start_schedule()

    def setup_dashboard(self):
        self.lbl = ttk.Label(self.tab_dashboard, text="Healthcare Innovation News", font=("Helvetica", 14, "bold"))
        self.lbl.pack(pady=20)
        
        self.btn_run = ttk.Button(self.tab_dashboard, text="Run Now", command=self.on_run_now)
        self.btn_run.pack(pady=10)
        
        self.btn_schedule = ttk.Button(self.tab_dashboard, text="Start Schedule", command=self.on_start_schedule)
        self.btn_schedule.pack(pady=10)

    def setup_settings(self):
        config = load_config()
        
        # --- RSS Feeds ---
        frame_rss = ttk.LabelFrame(self.tab_settings, text="RSS Feeds")
        frame_rss.pack(fill=tk.X, padx=10, pady=10)
        
        self.listbox_rss = tk.Listbox(frame_rss, height=5)
        self.listbox_rss.pack(fill=tk.X, padx=5, pady=5)
        for feed in config.get("rss_feeds", []):
            self.listbox_rss.insert(tk.END, feed)
            
        frame_rss_btns = ttk.Frame(frame_rss)
        frame_rss_btns.pack(fill=tk.X, padx=5, pady=5)
        
        self.entry_rss = ttk.Entry(frame_rss_btns)
        self.entry_rss.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        btn_add_rss = ttk.Button(frame_rss_btns, text="Add", command=self.add_rss)
        btn_add_rss.pack(side=tk.LEFT)
        btn_remove_rss = ttk.Button(frame_rss_btns, text="Remove Selected", command=self.remove_rss)
        btn_remove_rss.pack(side=tk.LEFT, padx=(5, 0))
        
        # --- Knowledge Base Keywords ---
        frame_kb = ttk.LabelFrame(self.tab_settings, text="Knowledge Base Keywords (High Signal)")
        frame_kb.pack(fill=tk.X, padx=10, pady=10)
        
        frame_kb_btns = ttk.Frame(frame_kb)
        frame_kb_btns.pack(fill=tk.X, padx=5, pady=5)
        
        self.entry_kb = ttk.Entry(frame_kb_btns)
        self.entry_kb.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        btn_add_kb = ttk.Button(frame_kb_btns, text="Add Keyword", command=self.add_kb_keyword)
        btn_add_kb.pack(side=tk.LEFT)

        # --- Automation ---
        frame_auto = ttk.LabelFrame(self.tab_settings, text="Schedule Automation")
        frame_auto.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(frame_auto, text="Frequency:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.combo_freq = ttk.Combobox(frame_auto, values=["daily", "weekly"], state="readonly")
        self.combo_freq.set(config.get("frequency", "daily"))
        self.combo_freq.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        self.combo_freq.bind("<<ComboboxSelected>>", self.on_frequency_change)
        
        ttk.Label(frame_auto, text="Day of Week (if weekly):").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.combo_day = ttk.Combobox(frame_auto, values=WEEKDAYS, state="readonly")
        self.combo_day.set(config.get("schedule_day", "Monday"))
        self.combo_day.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(frame_auto, text="Time of Day (HH:MM):").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.entry_time = ttk.Entry(frame_auto)
        self.entry_time.insert(0, config.get("schedule_time", "08:00"))
        self.entry_time.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        self.auto_start_schedule = tk.BooleanVar(value=bool(config.get("auto_start_schedule", False)))
        self.check_auto_start = ttk.Checkbutton(
            frame_auto,
            text="Run schedule automatically when Windows starts",
            variable=self.auto_start_schedule
        )
        self.check_auto_start.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)

        # --- Save Settings ---
        btn_save = ttk.Button(self.tab_settings, text="Save Settings", command=self.save_settings)
        btn_save.pack(pady=10)
        self.update_day_selector_state()

    def update_day_selector_state(self):
        if self.combo_freq.get() == "daily":
            self.combo_day.config(state=tk.DISABLED)
        else:
            self.combo_day.config(state="readonly")

    def on_frequency_change(self, _event=None):
        self.update_day_selector_state()

    def add_rss(self):
        val = self.entry_rss.get().strip()
        if val:
            self.listbox_rss.insert(tk.END, val)
            self.entry_rss.delete(0, tk.END)

    def remove_rss(self):
        sel = self.listbox_rss.curselection()
        if sel:
            self.listbox_rss.delete(sel[0])

    def add_kb_keyword(self):
        kw = self.entry_kb.get().strip()
        if kw:
            try:
                context = scorer.load_context()
                if "keyword_rules" not in context:
                    context["keyword_rules"] = {}
                if "high_signal" not in context["keyword_rules"]:
                    context["keyword_rules"]["high_signal"] = []
                
                if kw not in context["keyword_rules"]["high_signal"]:
                    context["keyword_rules"]["high_signal"].append(kw)
                    scorer.save_context(context)
                    messagebox.showinfo("Success", f"Keyword '{kw}' added to knowledge base.")
                    self.entry_kb.delete(0, tk.END)
                else:
                    messagebox.showinfo("Info", "Keyword already exists in high_signal.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save context:\n{e}")

    def save_settings(self):
        schedule_time = self.entry_time.get().strip()
        if not is_valid_schedule_time(schedule_time):
            messagebox.showerror("Error", "Schedule time must be HH:MM in 24-hour time.")
            return

        config = load_config()
        config["rss_feeds"] = list(self.listbox_rss.get(0, tk.END))
        config["frequency"] = self.combo_freq.get()
        config["schedule_day"] = self.combo_day.get()
        config["schedule_time"] = schedule_time
        config["auto_start_schedule"] = self.auto_start_schedule.get()
        
        try:
            save_config(config)
            configure_windows_startup(config["auto_start_schedule"])
            if config["auto_start_schedule"]:
                self.start_schedule()
            self.update_day_selector_state()
            messagebox.showinfo("Success", "Settings saved!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config:\n{e}")

    def on_run_now(self):
        self.btn_run.config(state=tk.DISABLED)
        self.update()
        try:
            run_digest(self)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run digest:\n{str(e)}")
        finally:
            self.btn_run.config(state=tk.NORMAL)
            
    def schedule_loop(self):
        last_run_key = None
        
        while self.running_schedule:
            config = load_config()
            now = datetime.datetime.now()
            should_run, next_run_key = should_run_schedule(config, now, last_run_key)
            
            if should_run:
                try:
                    self.after(0, lambda: run_digest(self))
                    last_run_key = next_run_key
                except Exception as e:
                    print(f"Schedule error: {e}")
                    
            # Sleep in chunks to allow interruption while still catching newly saved times.
            for _ in range(SCHEDULER_POLL_SECONDS):
                if not self.running_schedule:
                    break
                time.sleep(1)
                
    def start_schedule(self):
        if self.running_schedule:
            return

        self.running_schedule = True
        self.btn_schedule.config(text="Stop Schedule")
        self.lbl.config(text="Schedule running...")
        self.schedule_thread = threading.Thread(target=self.schedule_loop, daemon=True)
        self.schedule_thread.start()

    def stop_schedule(self):
        if not self.running_schedule:
            return

        self.running_schedule = False
        self.btn_schedule.config(text="Start Schedule")
        self.lbl.config(text="Schedule stopped")

    def on_start_schedule(self):
        if self.running_schedule:
            self.stop_schedule()
        else:
            self.start_schedule()

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
