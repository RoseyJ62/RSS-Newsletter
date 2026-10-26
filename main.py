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
import keywords
import saved_articles

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
    # The main window shows the digest in its Articles tab; other roots get a Toplevel window.
    if hasattr(app_root, "show_digest"):
        app_root.show_digest(scored_articles)
        return
    digest_window = tk.Toplevel(app_root)
    ui.NewsAppUI(digest_window, scored_articles)

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        ui.apply_theme(self)
        self.title("News Digest Controller")
        self.geometry("900x760")
        self.minsize(460, 480)
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        self.tab_dashboard = ttk.Frame(self.notebook)
        self.tab_articles = ui.ArticleListView(
            self.notebook,
            on_saved_changed=self.on_saved_changed,
            on_run=self.on_run_now,
        )
        self.tab_saved = ui.SavedArticlesView(self.notebook, on_saved_changed=self.on_saved_changed_from_saved_tab)
        self.tab_settings = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_dashboard, text="Dashboard")
        self.notebook.add(self.tab_articles, text="Articles")
        self.notebook.add(self.tab_saved, text="Saved Articles")
        self.notebook.add(self.tab_settings, text="Settings")
        
        self.setup_dashboard()
        self.setup_settings()
        self.update_saved_tab_label()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.schedule_thread = None
        self.running_schedule = False
        if load_config().get("auto_start_schedule", False):
            self.start_schedule()

    def setup_dashboard(self):
        frame = ttk.Frame(self.tab_dashboard, padding=ui.PAD * 2)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Healthcare Innovation News", style="Heading.TLabel").pack(anchor=tk.W)
        intro = ttk.Label(
            frame,
            style="Muted.TLabel",
            justify=tk.LEFT,
            text="Fetch the latest articles from your feeds, ranked by your keywords and ratings. "
                 "Results open in the Articles tab.",
        )
        intro.pack(fill=tk.X, pady=(4, ui.PAD))
        ui.bind_wraplength(frame, [intro], padding=4 * ui.PAD)

        buttons = ttk.Frame(frame)
        buttons.pack(anchor=tk.W, pady=(0, ui.PAD))
        self.btn_run = ttk.Button(buttons, text="Run Now", style="Accent.TButton", command=self.on_run_now)
        self.btn_run.pack(side=tk.LEFT)
        
        self.btn_schedule = ttk.Button(buttons, text="Start Schedule", command=self.on_start_schedule)
        self.btn_schedule.pack(side=tk.LEFT, padx=(ui.GAP, 0))

        # Schedule status (also updated by start/stop schedule)
        self.lbl = ttk.Label(frame, text="Schedule stopped", style="Subheading.TLabel")
        self.lbl.pack(anchor=tk.W)
        self.lbl_schedule_detail = ttk.Label(frame, style="Muted.TLabel")
        self.lbl_schedule_detail.pack(anchor=tk.W, pady=(2, ui.PAD * 2))
        self.update_schedule_detail()

        ttk.Label(frame, text="Go to", style="Subheading.TLabel").pack(anchor=tk.W, pady=(0, ui.GAP))
        nav = ttk.Frame(frame)
        nav.pack(anchor=tk.W)
        ttk.Button(nav, text="Articles", command=lambda: self.notebook.select(self.tab_articles)).pack(side=tk.LEFT)
        self.btn_nav_saved = ttk.Button(nav, text="Saved Articles",
                                        command=lambda: self.notebook.select(self.tab_saved))
        self.btn_nav_saved.pack(side=tk.LEFT, padx=(ui.GAP, 0))
        ttk.Button(nav, text="Settings", command=lambda: self.notebook.select(self.tab_settings)).pack(
            side=tk.LEFT, padx=(ui.GAP, 0))

    def on_close(self):
        if self.current_keywords() != self.saved_keywords:
            answer = messagebox.askyesnocancel(
                "Unsaved keywords",
                "You have unsaved keyword changes. Save them before closing?",
            )
            if answer is None:
                return
            if answer:
                self.save_kb_keywords()
        self.destroy()

    def update_schedule_detail(self):
        config = load_config()
        if config.get("frequency", "daily") == "weekly":
            when = f"Weekly on {config.get('schedule_day', 'Monday')} at {config.get('schedule_time', '08:00')}"
        else:
            when = f"Daily at {config.get('schedule_time', '08:00')}"
        feeds = len(config.get("rss_feeds", []))
        self.lbl_schedule_detail.configure(text=f"{when} · {feeds} feed{'s' if feeds != 1 else ''} configured")

    def show_digest(self, scored_articles):
        self.tab_articles.set_articles(scored_articles)
        self.notebook.select(self.tab_articles)
        # Bring the window forward so scheduled digests are noticed, as the old pop-up window was.
        self.deiconify()
        self.lift()
        self.focus_force()

    def update_saved_tab_label(self):
        count = len(saved_articles.list_articles())
        text = f"Saved Articles ({count})" if count else "Saved Articles"
        self.notebook.tab(self.tab_saved, text=text)
        self.btn_nav_saved.configure(text=text)

    def on_saved_changed(self):
        self.tab_saved.refresh()
        self.update_saved_tab_label()

    def on_saved_changed_from_saved_tab(self):
        self.tab_articles.refresh_saved_state()
        self.update_saved_tab_label()

    def setup_settings(self):
        config = load_config()
        scroll = ui.ScrollableFrame(self.tab_settings)
        scroll.pack(fill=tk.BOTH, expand=True)
        container = ttk.Frame(scroll.scrollable_frame, padding=(ui.PAD, ui.PAD, ui.PAD, 0))
        container.pack(fill=tk.BOTH, expand=True)
        ttk.Label(container, text="Settings", style="Heading.TLabel").pack(anchor=tk.W, pady=(0, ui.GAP))
        
        # --- RSS Feeds ---
        frame_rss = ttk.LabelFrame(container, text="RSS Feeds")
        frame_rss.pack(fill=tk.X, pady=(0, ui.PAD))
        
        self.listbox_rss = tk.Listbox(frame_rss, height=5, **self.listbox_options())
        self.listbox_rss.pack(fill=tk.X)
        for feed in config.get("rss_feeds", []):
            self.listbox_rss.insert(tk.END, feed)
            
        frame_rss_btns = ttk.Frame(frame_rss)
        frame_rss_btns.pack(fill=tk.X, pady=(ui.GAP, 0))
        
        self.entry_rss = ttk.Entry(frame_rss_btns)
        self.entry_rss.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, ui.GAP))
        self.entry_rss.bind("<Return>", lambda e: self.add_rss())
        
        btn_add_rss = ttk.Button(frame_rss_btns, text="Add", command=self.add_rss)
        btn_add_rss.pack(side=tk.LEFT)
        btn_remove_rss = ttk.Button(frame_rss_btns, text="Remove Selected", style="Danger.TButton",
                                    command=self.remove_rss)
        btn_remove_rss.pack(side=tk.LEFT, padx=(ui.GAP, 0))
        
        # --- Keyword Management (high-signal keywords in osf_context.json) ---
        self.setup_keyword_management(container)

        # --- Automation ---
        frame_auto = ttk.LabelFrame(container, text="Schedule Automation")
        frame_auto.pack(fill=tk.X, pady=(0, ui.PAD))
        
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
        btn_save = ttk.Button(container, text="Save Feed & Schedule Settings", style="Accent.TButton",
                              command=self.save_settings)
        btn_save.pack(anchor=tk.E, pady=(0, ui.PAD))
        self.update_day_selector_state()

    def listbox_options(self):
        return {
            "activestyle": "none",
            "borderwidth": 0,
            "highlightthickness": 1,
            "highlightbackground": ui.COLORS["border"],
            "highlightcolor": ui.COLORS["accent"],
            "selectbackground": ui.COLORS["accent"],
            "selectforeground": "#ffffff",
            "background": ui.COLORS["card"],
            "foreground": ui.COLORS["text"],
            "exportselection": False,
        }

    def setup_keyword_management(self, container):
        frame_kw = ttk.LabelFrame(container, text="Keyword Management")
        frame_kw.pack(fill=tk.X, pady=(0, ui.PAD))

        help_lbl = ttk.Label(
            frame_kw,
            style="Muted.TLabel",
            justify=tk.LEFT,
            text="High-signal keywords mark an article as important. When one appears, generic words "
                 "such as \"update\" or \"announces\" are also allowed to count toward its score. "
                 "Changes take effect on the next digest run after you click Save Keywords.",
        )
        help_lbl.pack(fill=tk.X, pady=(0, ui.GAP))
        ui.bind_wraplength(frame_kw, [help_lbl], padding=2 * ui.PAD + 12)

        self.keyword_count_lbl = ttk.Label(frame_kw, style="Muted.TLabel")
        self.keyword_count_lbl.pack(anchor=tk.W)

        list_frame = ttk.Frame(frame_kw)
        list_frame.pack(fill=tk.X, pady=(4, 0))
        self.listbox_kw = tk.Listbox(list_frame, height=8, **self.listbox_options())
        kw_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox_kw.yview)
        self.listbox_kw.configure(yscrollcommand=kw_scroll.set)
        self.listbox_kw.pack(side=tk.LEFT, fill=tk.X, expand=True)
        kw_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.listbox_kw.bind("<<ListboxSelect>>", self.on_keyword_select)

        entry_row = ttk.Frame(frame_kw)
        entry_row.pack(fill=tk.X, pady=(ui.GAP, 0))
        self.entry_kb = ttk.Entry(entry_row)
        self.entry_kb.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, ui.GAP))
        self.entry_kb.bind("<Return>", lambda e: self.add_kb_keyword())

        btn_row = ttk.Frame(frame_kw)
        btn_row.pack(fill=tk.X, pady=(ui.GAP, 0))
        ttk.Button(btn_row, text="Add Keyword", command=self.add_kb_keyword).pack(side=tk.LEFT)
        self.btn_update_kw = ttk.Button(btn_row, text="Update Selected", command=self.update_kb_keyword)
        self.btn_update_kw.pack(side=tk.LEFT, padx=(ui.GAP, 0))
        self.btn_remove_kw = ttk.Button(btn_row, text="Remove Selected", style="Danger.TButton",
                                        command=self.remove_kb_keyword)
        self.btn_remove_kw.pack(side=tk.LEFT, padx=(ui.GAP, 0))

        save_row = ttk.Frame(frame_kw)
        save_row.pack(fill=tk.X, pady=(ui.GAP, 0))
        self.btn_save_kw = ttk.Button(save_row, text="Save Keywords", style="Accent.TButton",
                                      command=self.save_kb_keywords)
        self.btn_save_kw.pack(side=tk.RIGHT)
        self.btn_revert_kw = ttk.Button(save_row, text="Discard Changes", command=self.revert_kb_keywords)
        self.btn_revert_kw.pack(side=tk.RIGHT, padx=(0, ui.GAP))
        self.keyword_status_lbl = ttk.Label(save_row, style="Muted.TLabel")
        self.keyword_status_lbl.pack(side=tk.LEFT)

        self.revert_kb_keywords()

    # --- Keyword management -------------------------------------------
    def current_keywords(self):
        return list(self.listbox_kw.get(0, tk.END))

    def selected_keyword_index(self):
        sel = self.listbox_kw.curselection()
        return sel[0] if sel else None

    def set_keyword_status(self, text, style="Muted.TLabel"):
        self.keyword_status_lbl.configure(text=text, style=style)

    def refresh_keyword_state(self):
        current = self.current_keywords()
        dirty = current != self.saved_keywords
        count = len(current)
        self.keyword_count_lbl.configure(text=f"{count} keyword{'s' if count != 1 else ''} configured")
        has_selection = self.selected_keyword_index() is not None
        self.btn_update_kw.configure(state=tk.NORMAL if has_selection else tk.DISABLED)
        self.btn_remove_kw.configure(state=tk.NORMAL if has_selection else tk.DISABLED)
        self.btn_save_kw.configure(state=tk.NORMAL if dirty else tk.DISABLED)
        self.btn_revert_kw.configure(state=tk.NORMAL if dirty else tk.DISABLED)
        if dirty:
            self.set_keyword_status("Unsaved changes", "Warning.TLabel")

    def on_keyword_select(self, _event=None):
        index = self.selected_keyword_index()
        if index is not None:
            self.entry_kb.delete(0, tk.END)
            self.entry_kb.insert(0, self.listbox_kw.get(index))
        self.refresh_keyword_state()

    def add_kb_keyword(self):
        kw = keywords.clean(self.entry_kb.get())
        if not kw:
            self.set_keyword_status("Type a keyword to add.", "Error.TLabel")
            return
        duplicate = keywords.find_duplicate(kw, self.current_keywords())
        if duplicate is not None:
            self.set_keyword_status(f"'{duplicate}' is already in the list.", "Error.TLabel")
            return
        self.listbox_kw.insert(tk.END, kw)
        self.listbox_kw.selection_clear(0, tk.END)
        self.listbox_kw.see(tk.END)
        self.entry_kb.delete(0, tk.END)
        self.refresh_keyword_state()

    def update_kb_keyword(self):
        index = self.selected_keyword_index()
        if index is None:
            self.set_keyword_status("Select a keyword to edit.", "Error.TLabel")
            return
        kw = keywords.clean(self.entry_kb.get())
        if not kw:
            self.set_keyword_status("A keyword cannot be empty. Use Remove Selected to delete it.", "Error.TLabel")
            return
        duplicate = keywords.find_duplicate(kw, self.current_keywords(), ignore_index=index)
        if duplicate is not None:
            self.set_keyword_status(f"'{duplicate}' is already in the list.", "Error.TLabel")
            return
        if kw == self.listbox_kw.get(index):
            return
        self.listbox_kw.delete(index)
        self.listbox_kw.insert(index, kw)
        self.listbox_kw.selection_set(index)
        self.refresh_keyword_state()

    def remove_kb_keyword(self):
        index = self.selected_keyword_index()
        if index is None:
            self.set_keyword_status("Select a keyword to remove.", "Error.TLabel")
            return
        self.listbox_kw.delete(index)
        self.entry_kb.delete(0, tk.END)
        self.refresh_keyword_state()

    def revert_kb_keywords(self):
        try:
            self.saved_keywords = keywords.load_high_signal()
        except (OSError, json.JSONDecodeError) as e:
            self.saved_keywords = []
            messagebox.showerror("Error", f"Failed to load keywords:\n{e}")
        self.listbox_kw.delete(0, tk.END)
        for kw in self.saved_keywords:
            self.listbox_kw.insert(tk.END, kw)
        self.entry_kb.delete(0, tk.END)
        self.set_keyword_status("")
        self.refresh_keyword_state()

    def save_kb_keywords(self):
        current = self.current_keywords()
        try:
            keywords.save_high_signal(current)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save context:\n{e}")
            return
        self.saved_keywords = current
        self.refresh_keyword_state()
        self.set_keyword_status(f"Saved at {datetime.datetime.now():%H:%M}", "Status.TLabel")
        messagebox.showinfo("Success", f"Keywords saved ({len(current)} total). They apply from the next digest run.")

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
            self.update_schedule_detail()
            messagebox.showinfo("Success", "Settings saved!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config:\n{e}")

    def on_run_now(self):
        run_buttons = [self.btn_run, self.tab_articles.run_button]
        for btn in run_buttons:
            btn.config(state=tk.DISABLED, text="Running…")
        self.config(cursor="watch")
        self.update()
        try:
            run_digest(self)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run digest:\n{str(e)}")
        finally:
            self.config(cursor="")
            for btn in run_buttons:
                btn.config(state=tk.NORMAL, text="Run Now")
            
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
