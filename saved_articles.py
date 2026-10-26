import datetime
import json
import os
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(__file__)
SAVED_PATH = os.path.join(APP_DIR, "saved_articles.json")


def _empty() -> Dict[str, Any]:
    return {"articles": []}


def load_saved() -> Dict[str, Any]:
    if not os.path.exists(SAVED_PATH):
        return _empty()

    try:
        with open(SAVED_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        # Keep the unreadable file so saved articles are never silently overwritten.
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        try:
            os.replace(SAVED_PATH, f"{SAVED_PATH}.corrupt-{stamp}")
        except OSError:
            pass
        return _empty()

    if not isinstance(data, dict) or not isinstance(data.get("articles"), list):
        return _empty()
    return data


def save_saved(data: Dict[str, Any]) -> None:
    # Write to a temp file first so a crash mid-write cannot corrupt the saved list.
    tmp_path = SAVED_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, SAVED_PATH)


def article_key(url: str, title: str = "") -> str:
    """Identity used to prevent duplicates: the URL, ignoring case of scheme/host,
    fragments and a trailing slash. Falls back to the title when there is no URL."""
    url = (url or "").strip()
    if not url:
        return "title:" + " ".join((title or "").split()).casefold()

    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def article_to_record(article, score_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    published = getattr(article, "published", None)
    if isinstance(published, datetime.datetime):
        published = published.isoformat()

    record = {
        "title": getattr(article, "title", "") or "",
        "url": getattr(article, "link", "") or "",
        "summary": getattr(article, "summary", "") or "",
        "source": getattr(article, "source", "") or "",
        "category": getattr(article, "category", "") or "",
        "published": published,
        "saved_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    if score_data:
        record["matched_keywords"] = list(score_data.get("matched_keywords", []))
    return record


def list_articles() -> List[Dict[str, Any]]:
    """Saved articles, most recently saved first."""
    articles = load_saved()["articles"]
    return sorted(articles, key=lambda a: a.get("saved_at") or "", reverse=True)


def is_saved(url: str, title: str = "") -> bool:
    key = article_key(url, title)
    return any(article_key(a.get("url", ""), a.get("title", "")) == key for a in load_saved()["articles"])


def add_article(record: Dict[str, Any]) -> bool:
    """Returns False if the article was already saved."""
    data = load_saved()
    key = article_key(record.get("url", ""), record.get("title", ""))
    if any(article_key(a.get("url", ""), a.get("title", "")) == key for a in data["articles"]):
        return False

    data["articles"].append(record)
    save_saved(data)
    return True


def remove_article(url: str, title: str = "") -> bool:
    """Returns False if the article was not in the saved list."""
    data = load_saved()
    key = article_key(url, title)
    remaining = [a for a in data["articles"] if article_key(a.get("url", ""), a.get("title", "")) != key]
    if len(remaining) == len(data["articles"]):
        return False

    data["articles"] = remaining
    save_saved(data)
    return True
