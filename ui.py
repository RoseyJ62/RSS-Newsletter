import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Any
import webbrowser
import profile

ARTICLE_BATCH_SIZE = 10

class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        self.canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Mouse wheel binding for Windows
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

class NewsAppUI:
    def __init__(self, root, scored_articles: List[Dict[str, Any]]):
        self.root = root
        self.root.title("Executive News Digest - Standalone")
        self.root.geometry("800x800")
        self.scored_articles = scored_articles
        self.visible_article_count = 0
        
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_label = ttk.Label(
            self.main_frame, 
            text="Executive News Digest", 
            font=("Helvetica", 16, "bold")
        )
        header_label.pack(pady=(0, 10))
        
        # Scrollable area for articles
        self.scroll_frame = ScrollableFrame(self.main_frame)
        self.scroll_frame.pack(fill=tk.BOTH, expand=True)

        self.load_more_frame = ttk.Frame(self.main_frame)
        self.load_more_frame.pack(fill=tk.X, pady=(10, 0))
        self.load_more_button = ttk.Button(
            self.load_more_frame,
            text="Load 10 more articles",
            command=self.load_more_articles
        )
        self.load_more_button.pack()
        
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
            self.load_more_button.config(state=tk.DISABLED, text="All articles loaded")
            return

        next_count = min(ARTICLE_BATCH_SIZE, remaining)
        self.load_more_button.config(state=tk.NORMAL, text=f"Load {next_count} more articles")

    def populate_articles(self, scored_articles):
        # articles come in as a list of dicts:
        # { 'article': Article(obj), 'score_data': {'score': float, 'explanation': str, 'matched_keywords': []} }
        for item in scored_articles:
            article = item['article']
            score_data = item['score_data']
            
            card = ttk.Frame(self.scroll_frame.scrollable_frame, padding="10", relief="solid", borderwidth=1)
            card.pack(fill=tk.X, padx=5, pady=5, expand=True)
            
            # Title & Score
            header_frame = ttk.Frame(card)
            header_frame.pack(fill=tk.X)
            
            title_lbl = ttk.Label(
                header_frame, 
                text=article.title, 
                font=("Helvetica", 12, "bold"),
                wraplength=600
            )
            title_lbl.pack(side=tk.LEFT)
            
            # Make title clickable
            title_lbl.bind("<Button-1>", lambda e, url=article.link: webbrowser.open_new(url))
            title_lbl.configure(foreground="blue", cursor="hand2")
            
            score_lbl = ttk.Label(
                header_frame, 
                text=f"Score: {score_data['score']:.1f}", 
                font=("Helvetica", 10, "bold"),
                foreground="green"
            )
            score_lbl.pack(side=tk.RIGHT)
            
            # Summary
            summary_lbl = ttk.Label(
                card, 
                text=article.summary, 
                wraplength=700, 
                justify=tk.LEFT
            )
            summary_lbl.pack(fill=tk.X, pady=(5, 5))
            
            # Explanation
            explanation_lbl = ttk.Label(
                card, 
                text=f"Why this matters: {score_data['explanation']}", 
                wraplength=700, 
                justify=tk.LEFT,
                font=("Helvetica", 9, "italic")
            )
            explanation_lbl.pack(fill=tk.X, pady=(0, 5))
            
            # Ratings
            rating_frame = ttk.Frame(card)
            rating_frame.pack(fill=tk.X, pady=(5, 0))
            
            ttk.Label(rating_frame, text="Rate this article:").pack(side=tk.LEFT, padx=(0, 10))
            
            keywords = score_data['matched_keywords']
            self.create_rating_buttons(rating_frame, keywords)
            
    def create_rating_buttons(self, parent, keywords):
        buttons_frame = ttk.Frame(parent)
        buttons_frame.pack(side=tk.LEFT)
        
        status_lbl = ttk.Label(parent, text="")
        status_lbl.pack(side=tk.LEFT, padx=10)
        
        def on_rate(rating):
            profile.update_weights(keywords, rating)
            status_lbl.config(text=f"Rated {rating}/5 - Thanks!", foreground="green")
            # Disable buttons after rating
            for child in buttons_frame.winfo_children():
                child.configure(state=tk.DISABLED)
                
        for i in range(1, 6):
            btn = ttk.Button(
                buttons_frame, 
                text=str(i), 
                width=3,
                command=lambda r=i: on_rate(r)
            )
            btn.pack(side=tk.LEFT, padx=2)

def launch_ui(scored_articles):
    root = tk.Tk()
    app = NewsAppUI(root, scored_articles)
    root.mainloop()
