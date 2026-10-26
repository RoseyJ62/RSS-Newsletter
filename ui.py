import datetime
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox
from tkinter import ttk
from typing import List, Dict, Any, Callable, Optional
from urllib.parse import urlsplit
import webbrowser
import profile
import saved_articles

ARTICLE_BATCH_SIZE = 10

# --- Visual theme ---------------------------------------------------------
COLORS = {
    "bg": "#f4f5f7",
    "card": "#ffffff",
    "border": "#d9dce1",
    "text": "#1f2933",
    "muted": "#5f6b7a",
    "accent": "#2563eb",
    "accent_active": "#1d4ed8",
    "accent_soft": "#e8effd",
    "success": "#15803d",
    "success_soft": "#e7f5ec",
    "danger": "#b91c1c",
    "warning": "#a16207",
}
PAD = 12          # outer padding used by tabs and views
CARD_PAD = 14     # inner padding of a card
GAP = 8           # space between related controls


def apply_theme(root):
    """Configure ttk styles shared by every window. Safe to call more than once."""
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    base = tkfont.nametofont("TkDefaultFont")
    family = base.actual("family")
    fonts = {
        "body": (family, 10),
        "small": (family, 9),
        "small_italic": (family, 9, "italic"),
        "bold": (family, 10, "bold"),
        "title": (family, 12, "bold"),
        "heading": (family, 16, "bold"),
        "subheading": (family, 11, "bold"),
    }
    # Classic Tk widgets (Listbox, tooltips) only; ttk labels take their font from styles.
    root.option_add("*Listbox.Font", fonts["body"])
    try:
        root.configure(background=COLORS["bg"])
    except tk.TclError:
        pass

    c = COLORS
    style.configure(".", background=c["bg"], foreground=c["text"], font=fonts["body"])
    style.configure("TFrame", background=c["bg"])
    style.configure("TLabel", background=c["bg"], foreground=c["text"])
    style.configure("Heading.TLabel", font=fonts["heading"])
    style.configure("Subheading.TLabel", font=fonts["subheading"])
    style.configure("Muted.TLabel", foreground=c["muted"], font=fonts["small"])
    style.configure("Status.TLabel", foreground=c["success"], font=fonts["small"])
    style.configure("Error.TLabel", foreground=c["danger"], font=fonts["small"])
    style.configure("Warning.TLabel", foreground=c["warning"], font=fonts["small"])

    style.configure("Card.TFrame", background=c["card"])
    style.configure("Card.TLabel", background=c["card"], foreground=c["text"])
    style.configure("CardTitle.TLabel", background=c["card"], foreground=c["accent"], font=fonts["title"])
    style.configure("CardMeta.TLabel", background=c["card"], foreground=c["muted"], font=fonts["small"])
    style.configure("CardNote.TLabel", background=c["card"], foreground=c["muted"], font=fonts["small_italic"])
    style.configure("CardStatus.TLabel", background=c["card"], foreground=c["success"], font=fonts["small"])
    style.configure("CardWarning.TLabel", background=c["card"], foreground=c["warning"], font=fonts["small"])
    style.configure("Score.TLabel", background=c["success_soft"], foreground=c["success"],
                    font=fonts["bold"], padding=(8, 2))
    style.configure("Card.TSeparator", background=c["border"])

    style.configure("TLabelframe", background=c["bg"], bordercolor=c["border"], padding=PAD)
    style.configure("TLabelframe.Label", background=c["bg"], foreground=c["text"], font=fonts["subheading"])

    style.configure("TNotebook", background=c["bg"], borderwidth=0, tabmargins=(PAD, PAD // 2, PAD, 0))
    style.configure("TNotebook.Tab", padding=(16, 8), font=fonts["bold"],
                    background=c["bg"], foreground=c["muted"])
    style.map("TNotebook.Tab",
              background=[("selected", c["card"])],
              foreground=[("selected", c["accent"])])

    style.configure("TButton", padding=(12, 6), background=c["card"], foreground=c["text"],
                    bordercolor=c["border"], focuscolor=c["accent"])
    style.map("TButton",
              background=[("disabled", c["bg"]), ("active", c["accent_soft"])],
              foreground=[("disabled", c["muted"])])
    style.configure("Accent.TButton", background=c["accent"], foreground="#ffffff",
                    bordercolor=c["accent"], font=fonts["bold"])
    style.map("Accent.TButton",
              background=[("disabled", c["border"]), ("active", c["accent_active"])],
              foreground=[("disabled", c["muted"])])
    style.configure("Saved.TButton", background=c["success_soft"], foreground=c["success"],
                    bordercolor=c["success"], font=fonts["bold"])
    style.map("Saved.TButton", background=[("active", "#d3ecdc")])
    style.configure("Danger.TButton", foreground=c["danger"])
    style.map("Danger.TButton", background=[("active", "#fbeaea")])
    style.configure("Rating.TButton", padding=(8, 4), font=fonts["small"])
    style.configure("RatingSelected.TButton", padding=(8, 4), font=fonts["small"],
                    background=c["accent"], foreground="#ffffff", bordercolor=c["accent"])
    style.map("RatingSelected.TButton",
              background=[("disabled", c["accent"])], foreground=[("disabled", "#ffffff")])
    style.configure("Link.TButton", padding=(4, 2), background=c["bg"], foreground=c["accent"],
                    bordercolor=c["bg"], font=fonts["small"])
    style.map("Link.TButton", background=[("active", c["accent_soft"])])

    style.configure("TEntry", padding=6, fieldbackground=c["card"], bordercolor=c["border"])
    style.configure("TCombobox", padding=4)
    return fonts


# --- Helpers --------------------------------------------------------------
def display_source(source: str) -> str:
    """Feeds are registered with their URL as the name; show the host instead."""
    source = (source or "").strip()
    if source.startswith(("http://", "https://")):
        host = urlsplit(source).netloc
        return host[4:] if host.startswith("www.") else host
    return source


def display_date(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime("%b %d, %Y")


def open_url(url: str):
    if url:
        webbrowser.open_new_tab(url)


def bind_wraplength(container, labels, padding=0):
    """Keep label text wrapped to the container's current width."""
    def on_resize(event):
        width = max(event.width - padding, 120)
        for label in labels:
            label.configure(wraplength=width)
    container.bind("<Configure>", on_resize, add="+")


class Tooltip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _event=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, background="#1f2933", foreground="#ffffff",
                 padx=8, pady=4, justify=tk.LEFT, wraplength=280).pack()

    def hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class FlowFrame(ttk.Frame):
    """Lays out children left to right and wraps them onto new rows when narrow."""
    def __init__(self, parent, gap=GAP // 2, **kwargs):
        super().__init__(parent, **kwargs)
        self.gap = gap
        self._last_width = None
        self.bind("<Configure>", self._reflow)

    def add(self, widget):
        widget.grid(row=0, column=len(self.grid_slaves()), padx=(0, self.gap), pady=(0, self.gap), sticky=tk.W)

    def _reflow(self, event):
        if event.width == self._last_width:
            return
        self._last_width = event.width
        children = sorted(self.grid_slaves(), key=lambda w: (int(w.grid_info()["row"]), int(w.grid_info()["column"])))
        row = col = used = 0
        for child in children:
            width = child.winfo_reqwidth() + self.gap
            if col > 0 and used + width > event.width:
                row, col, used = row + 1, 0, 0
            child.grid_configure(row=row, column=col)
            col += 1
            used += width


class ScrollableFrame(ttk.Frame):
    _instances = []
    _wheel_bound = False

    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)

        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, background=COLORS["bg"])
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        # Stretch the content to the visible width so cards reflow when resized.
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window_id, width=e.width))

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # One global wheel binding routes scrolling to whichever list is under the pointer.
        ScrollableFrame._instances.append(self)
        if not ScrollableFrame._wheel_bound:
            self.canvas.bind_all("<MouseWheel>", ScrollableFrame._on_mousewheel)
            self.canvas.bind_all("<Button-4>", ScrollableFrame._on_mousewheel)
            self.canvas.bind_all("<Button-5>", ScrollableFrame._on_mousewheel)
            ScrollableFrame._wheel_bound = True

    def scroll_to_top(self):
        self.canvas.yview_moveto(0)

    @classmethod
    def _on_mousewheel(cls, event):
        try:
            widget = event.widget.winfo_containing(event.x_root, event.y_root)
        except (AttributeError, KeyError, tk.TclError):
            return
        while widget is not None and not isinstance(widget, ScrollableFrame):
            widget = getattr(widget, "master", None)
        if widget is None or widget.canvas.yview() == (0.0, 1.0):
            return
        if getattr(event, "num", None) == 4:
            step = -1
        elif getattr(event, "num", None) == 5:
            step = 1
        else:
            step = int(-1 * (event.delta / 120)) or (-1 if event.delta > 0 else 1)
        widget.canvas.yview_scroll(step, "units")


def make_card(parent):
    """A white card with a thin border, returning (outer, inner) frames."""
    outer = tk.Frame(parent, background=COLORS["card"], highlightthickness=1,
                     highlightbackground=COLORS["border"], highlightcolor=COLORS["border"])
    outer.pack(fill=tk.X, padx=PAD, pady=(0, GAP + 2))
    inner = ttk.Frame(outer, style="Card.TFrame", padding=CARD_PAD)
    inner.pack(fill=tk.BOTH, expand=True)
    return outer, inner


def make_title_link(parent, title, url):
    label = ttk.Label(parent, text=title or "(untitled)", style="CardTitle.TLabel", cursor="hand2", justify=tk.LEFT)
    label.bind("<Button-1>", lambda e: open_url(url))
    base_font = tkfont.Font(font=ttk.Style().lookup("CardTitle.TLabel", "font"))
    hover_font = base_font.copy()
    hover_font.configure(underline=True)
    label.bind("<Enter>", lambda e: label.configure(font=hover_font))
    label.bind("<Leave>", lambda e: label.configure(font=base_font))
    label._fonts = (base_font, hover_font)  # keep references alive
    Tooltip(label, url)
    return label


def make_empty_state(parent, title, message):
    frame = ttk.Frame(parent, padding=(PAD, 40))
    frame.pack(fill=tk.X)
    ttk.Label(frame, text=title, style="Subheading.TLabel").pack()
    msg = ttk.Label(frame, text=message, style="Muted.TLabel", justify=tk.CENTER)
    msg.pack(pady=(GAP, 0))
    bind_wraplength(frame, [msg], padding=2 * PAD)
    return frame


def rating_help_text(scale=None) -> str:
    scale = scale or profile.CURRENT_RATING_SCALE
    lines = [f"{value}  {label}: {desc}" for value, (label, desc, _adj) in sorted(profile.RATING_SCALES[scale].items())]
    lines.append("Unrated: leave an article unrated and your preferences stay the same.")
    lines.append("A rating adjusts the weight of the tracked keywords the article matched, "
                 "so articles sharing those keywords rank higher or lower in future digests.")
    return "\n".join(lines)


# --- Views ----------------------------------------------------------------
class ArticleListView(ttk.Frame):
    """The digest: ranked article cards with save and rating actions."""

    def __init__(self, parent, scored_articles: Optional[List[Dict[str, Any]]] = None,
                 on_saved_changed: Optional[Callable[[], None]] = None,
                 on_run: Optional[Callable[[], None]] = None, title="Executive News Digest"):
        super().__init__(parent)
        self.on_saved_changed = on_saved_changed
        self.scored_articles = []
        self.visible_article_count = 0
        self.save_buttons = {}  # article key -> (button, record)

        header = ttk.Frame(self, padding=(PAD, PAD, PAD, GAP))
        header.pack(fill=tk.X)
        ttk.Label(header, text=title, style="Heading.TLabel").pack(side=tk.LEFT)
        if on_run:
            self.run_button = ttk.Button(header, text="Run Now", style="Accent.TButton", command=on_run)
            self.run_button.pack(side=tk.RIGHT)

        self.subtitle = ttk.Label(self, style="Muted.TLabel", padding=(PAD, 0, PAD, 0), justify=tk.LEFT)
        self.subtitle.pack(fill=tk.X)
        bind_wraplength(self, [self.subtitle], padding=2 * PAD)
        self.help_button = ttk.Button(self, text="How do ratings work?", style="Link.TButton",
                                      command=self.toggle_help)
        self.help_button.pack(anchor=tk.W, padx=PAD - 4, pady=(0, GAP))

        self.help_frame = ttk.Frame(self, padding=(PAD, 0, PAD, GAP))
        self.help_label = ttk.Label(self.help_frame, text=rating_help_text(), style="Muted.TLabel", justify=tk.LEFT)
        self.help_label.pack(fill=tk.X)
        bind_wraplength(self.help_frame, [self.help_label], padding=2 * PAD)

        # Scrollable area for articles
        self.scroll_frame = ScrollableFrame(self)
        self.scroll_frame.pack(fill=tk.BOTH, expand=True)

        self.load_more_frame = ttk.Frame(self, padding=(PAD, GAP))
        self.load_more_frame.pack(fill=tk.X)
        self.load_more_button = ttk.Button(
            self.load_more_frame,
            text="Load 10 more articles",
            command=self.load_more_articles
        )
        self.load_more_button.pack()

        self.set_articles(scored_articles)

    def toggle_help(self):
        if self.help_frame.winfo_ismapped():
            self.help_frame.pack_forget()
            self.help_button.configure(text="How do ratings work?")
        else:
            self.help_frame.pack(fill=tk.X, before=self.scroll_frame)
            self.help_button.configure(text="Hide rating help")

    def set_articles(self, scored_articles: Optional[List[Dict[str, Any]]]):
        for child in self.scroll_frame.scrollable_frame.winfo_children():
            child.destroy()
        self.save_buttons = {}
        self.scored_articles = list(scored_articles or [])
        self.visible_article_count = 0
        self.scroll_frame.scroll_to_top()

        if scored_articles is None:
            self.subtitle.configure(text="No digest has been run yet in this session.")
            make_empty_state(self.scroll_frame.scrollable_frame, "No articles yet",
                             "Click Run Now to fetch the latest articles from your feeds.")
        elif not self.scored_articles:
            self.subtitle.configure(text=f"Updated {datetime.datetime.now():%b %d, %Y at %H:%M}")
            make_empty_state(self.scroll_frame.scrollable_frame, "No new articles",
                             "Your feeds returned no articles in the lookback window. "
                             "Check your feed list in Settings or try again later.")
        else:
            self.subtitle.configure(
                text=f"{len(self.scored_articles)} articles, ranked by relevance to your keywords. "
                     f"Updated {datetime.datetime.now():%b %d, %Y at %H:%M}.")
        self.load_more_articles()

    def load_more_articles(self):
        start = self.visible_article_count
        end = min(start + ARTICLE_BATCH_SIZE, len(self.scored_articles))
        self.populate_articles(self.scored_articles[start:end])
        self.visible_article_count = end
        self.update_load_more_button()

    def update_load_more_button(self):
        remaining = len(self.scored_articles) - self.visible_article_count
        if remaining <= 0:
            if self.scored_articles:
                self.load_more_button.config(state=tk.DISABLED, text="All articles loaded")
                self.load_more_frame.pack(fill=tk.X)
            else:
                self.load_more_frame.pack_forget()
            return

        next_count = min(ARTICLE_BATCH_SIZE, remaining)
        self.load_more_button.config(state=tk.NORMAL, text=f"Load {next_count} more articles")
        self.load_more_frame.pack(fill=tk.X)

    def populate_articles(self, scored_articles):
        # articles come in as a list of dicts:
        # { 'article': Article(obj), 'score_data': {'score': float, 'explanation': str, 'matched_keywords': []} }
        for item in scored_articles:
            article = item['article']
            score_data = item['score_data']

            _outer, card = make_card(self.scroll_frame.scrollable_frame)
            wrapped = []

            # Title & Score
            header_frame = ttk.Frame(card, style="Card.TFrame")
            header_frame.pack(fill=tk.X)
            header_frame.columnconfigure(0, weight=1)

            title_lbl = make_title_link(header_frame, article.title, article.link)
            title_lbl.grid(row=0, column=0, sticky=tk.W)

            score_lbl = ttk.Label(header_frame, text=f"Score {score_data['score']:.1f}", style="Score.TLabel")
            score_lbl.grid(row=0, column=1, sticky=tk.NE, padx=(GAP, 0))
            header_frame.bind("<Configure>", lambda e, t=title_lbl, s=score_lbl: t.configure(
                wraplength=max(e.width - s.winfo_reqwidth() - 2 * GAP, 120)), add="+")
            Tooltip(score_lbl, "Relevance score: the sum of each matched keyword's category weight "
                               "multiplied by your personal weight for that keyword.")

            meta = " · ".join(p for p in (display_source(getattr(article, "source", "")),
                                          display_date(getattr(article, "published", None)),
                                          getattr(article, "category", "")) if p)
            if meta:
                ttk.Label(card, text=meta, style="CardMeta.TLabel").pack(fill=tk.X, pady=(2, 0))

            # Summary
            if article.summary:
                summary_lbl = ttk.Label(card, text=article.summary, style="Card.TLabel", justify=tk.LEFT)
                summary_lbl.pack(fill=tk.X, pady=(GAP, 0))
                wrapped.append(summary_lbl)

            # Explanation
            explanation_lbl = ttk.Label(
                card,
                text=f"Why this matters: {score_data['explanation']}",
                style="CardNote.TLabel",
                justify=tk.LEFT,
            )
            explanation_lbl.pack(fill=tk.X, pady=(GAP, 0))
            wrapped.append(explanation_lbl)

            ttk.Separator(card, orient=tk.HORIZONTAL, style="Card.TSeparator").pack(fill=tk.X, pady=GAP)

            # Actions
            actions = ttk.Frame(card, style="Card.TFrame")
            actions.pack(fill=tk.X)
            ttk.Button(actions, text="Open article", command=lambda url=article.link: open_url(url)).pack(side=tk.LEFT)
            record = saved_articles.article_to_record(article, score_data)
            save_btn = ttk.Button(actions, command=lambda r=record: self.toggle_saved(r))
            save_btn.pack(side=tk.LEFT, padx=(GAP, 0))
            self.save_buttons[saved_articles.article_key(record["url"], record["title"])] = (save_btn, record)
            self.update_save_button(save_btn, saved_articles.is_saved(record["url"], record["title"]))

            # Ratings
            keywords = score_data['matched_keywords']
            self.create_rating_buttons(card, keywords, wrapped)
            bind_wraplength(card, wrapped, padding=2 * CARD_PAD)

    def update_save_button(self, button, is_saved):
        if is_saved:
            button.configure(text="★ Saved", style="Saved.TButton")
        else:
            button.configure(text="☆ Save", style="TButton")

    def toggle_saved(self, record):
        try:
            if saved_articles.is_saved(record["url"], record["title"]):
                saved_articles.remove_article(record["url"], record["title"])
            else:
                saved_articles.add_article(dict(record, saved_at=datetime.datetime.now().astimezone()
                                                .isoformat(timespec="seconds")))
        except OSError as e:
            messagebox.showerror("Error", f"Could not update saved articles:\n{e}")
            return
        self.refresh_saved_state()
        if self.on_saved_changed:
            self.on_saved_changed()

    def refresh_saved_state(self):
        saved_keys = {saved_articles.article_key(a.get("url", ""), a.get("title", ""))
                      for a in saved_articles.list_articles()}
        for key, (button, _record) in self.save_buttons.items():
            if button.winfo_exists():
                self.update_save_button(button, key in saved_keys)

    def create_rating_buttons(self, card, keywords, wrapped):
        scale = profile.CURRENT_RATING_SCALE
        options = profile.RATING_SCALES[scale]

        rating_frame = ttk.Frame(card, style="Card.TFrame")
        rating_frame.pack(fill=tk.X, pady=(GAP, 0))
        ttk.Label(rating_frame, text="Rate this article (optional):", style="CardMeta.TLabel").pack(anchor=tk.W)

        buttons_frame = FlowFrame(rating_frame, style="Card.TFrame")
        buttons_frame.pack(fill=tk.X, pady=(4, 0))

        if keywords:
            hint = "Ratings adjust these tracked keywords: " + ", ".join(keywords)
            status_lbl = ttk.Label(rating_frame, text=hint, style="CardMeta.TLabel", justify=tk.LEFT)
        else:
            status_lbl = ttk.Label(rating_frame, style="CardWarning.TLabel", justify=tk.LEFT,
                                   text="This article matched no tracked keywords, so rating it "
                                        "will not change future recommendations.")
        status_lbl.pack(fill=tk.X)
        wrapped.append(status_lbl)
        buttons = {}

        def on_rate(rating):
            try:
                profile.update_weights(keywords, rating)
            except OSError as e:
                messagebox.showerror("Error", f"Could not save rating:\n{e}")
                return
            label, desc, adjustment = options[rating]
            if keywords and adjustment:
                direction = "raised" if adjustment > 0 else "lowered"
                text = f"Rated “{label}”. {direction.capitalize()} the weight of: {', '.join(keywords)}."
            elif keywords:
                text = f"Rated “{label}”. Recommendations are unchanged."
            else:
                text = f"Rated “{label}”. No tracked keywords matched, so recommendations are unchanged."
            status_lbl.config(text=text, style="CardStatus.TLabel")
            # Disable buttons after rating, highlighting the chosen one
            for value, btn in buttons.items():
                btn.configure(state=tk.DISABLED,
                              style="RatingSelected.TButton" if value == rating else "Rating.TButton")

        for value, (label, desc, adjustment) in sorted(options.items()):
            btn = ttk.Button(
                buttons_frame,
                text=f"{value} · {label}",
                style="Rating.TButton",
                command=lambda r=value: on_rate(r)
            )
            buttons_frame.add(btn)
            Tooltip(btn, desc)
            buttons[value] = btn


class SavedArticlesView(ttk.Frame):
    """Articles the user bookmarked, read from saved_articles.json."""

    def __init__(self, parent, on_saved_changed: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.on_saved_changed = on_saved_changed

        header = ttk.Frame(self, padding=(PAD, PAD, PAD, GAP))
        header.pack(fill=tk.X)
        ttk.Label(header, text="Saved Articles", style="Heading.TLabel").pack(side=tk.LEFT)
        self.subtitle = ttk.Label(self, style="Muted.TLabel", padding=(PAD, 0, PAD, GAP))
        self.subtitle.pack(fill=tk.X)

        self.scroll_frame = ScrollableFrame(self)
        self.scroll_frame.pack(fill=tk.BOTH, expand=True)
        self.refresh()

    def refresh(self):
        for child in self.scroll_frame.scrollable_frame.winfo_children():
            child.destroy()

        articles = saved_articles.list_articles()
        if not articles:
            self.subtitle.configure(text="")
            make_empty_state(self.scroll_frame.scrollable_frame, "No saved articles yet",
                             "Use ☆ Save on any article in the Articles tab to keep it here. "
                             "Saved articles stay available even after they leave your feeds.")
            return

        noun = "article" if len(articles) == 1 else "articles"
        self.subtitle.configure(text=f"{len(articles)} saved {noun}, most recently saved first.")
        for record in articles:
            self.add_card(record)

    def add_card(self, record):
        _outer, card = make_card(self.scroll_frame.scrollable_frame)
        wrapped = []

        title_lbl = make_title_link(card, record.get("title"), record.get("url"))
        title_lbl.pack(fill=tk.X)
        wrapped.append(title_lbl)

        meta_parts = [display_source(record.get("source", "")), display_date(record.get("published"))]
        if record.get("saved_at"):
            meta_parts.append(f"Saved {display_date(record['saved_at'])}")
        meta = " · ".join(p for p in meta_parts if p)
        if meta:
            ttk.Label(card, text=meta, style="CardMeta.TLabel").pack(fill=tk.X, pady=(2, 0))

        if record.get("summary"):
            summary_lbl = ttk.Label(card, text=record["summary"], style="Card.TLabel", justify=tk.LEFT)
            summary_lbl.pack(fill=tk.X, pady=(GAP, 0))
            wrapped.append(summary_lbl)

        ttk.Separator(card, orient=tk.HORIZONTAL, style="Card.TSeparator").pack(fill=tk.X, pady=GAP)
        actions = ttk.Frame(card, style="Card.TFrame")
        actions.pack(fill=tk.X)
        open_btn = ttk.Button(actions, text="Open original", command=lambda: open_url(record.get("url")))
        open_btn.pack(side=tk.LEFT)
        if not record.get("url"):
            open_btn.configure(state=tk.DISABLED)
        ttk.Button(actions, text="Remove", style="Danger.TButton",
                   command=lambda: self.remove(record)).pack(side=tk.LEFT, padx=(GAP, 0))
        bind_wraplength(card, wrapped, padding=2 * CARD_PAD)

    def remove(self, record):
        try:
            saved_articles.remove_article(record.get("url", ""), record.get("title", ""))
        except OSError as e:
            messagebox.showerror("Error", f"Could not update saved articles:\n{e}")
            return
        self.refresh()
        if self.on_saved_changed:
            self.on_saved_changed()


class NewsAppUI:
    """Standalone digest window (used by launch_ui)."""

    def __init__(self, root, scored_articles: List[Dict[str, Any]]):
        self.root = root
        apply_theme(root)
        self.root.title("Executive News Digest - Standalone")
        self.root.geometry("800x800")
        self.root.minsize(420, 400)
        self.scored_articles = scored_articles
        self.view = ArticleListView(root, scored_articles)
        self.view.pack(fill=tk.BOTH, expand=True)

def launch_ui(scored_articles):
    root = tk.Tk()
    app = NewsAppUI(root, scored_articles)
    root.mainloop()
