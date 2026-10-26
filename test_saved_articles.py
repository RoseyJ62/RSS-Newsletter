from datetime import UTC, datetime
from types import SimpleNamespace
import json
import os
import tempfile
import unittest
from unittest import mock

import saved_articles


def make_article(title="Headline", link="https://example.com/a", summary="Short summary."):
    return SimpleNamespace(
        title=title,
        link=link,
        source="https://example.com/rss",
        category="General",
        published=datetime(2026, 4, 20, 13, 30, tzinfo=UTC),
        summary=summary,
    )


class SavedArticlesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "saved_articles.json")
        patcher = mock.patch.object(saved_articles, "SAVED_PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_record_keeps_title_url_summary_and_metadata(self):
        record = saved_articles.article_to_record(make_article(), {"matched_keywords": ["ai"]})

        self.assertEqual(record["title"], "Headline")
        self.assertEqual(record["url"], "https://example.com/a")
        self.assertEqual(record["summary"], "Short summary.")
        self.assertEqual(record["source"], "https://example.com/rss")
        self.assertEqual(record["published"], "2026-04-20T13:30:00+00:00")
        self.assertEqual(record["matched_keywords"], ["ai"])
        self.assertIn("saved_at", record)

    def test_add_persists_to_disk_and_survives_reload(self):
        self.assertTrue(saved_articles.add_article(saved_articles.article_to_record(make_article())))

        with open(self.path, encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk["articles"][0]["url"], "https://example.com/a")
        self.assertTrue(saved_articles.is_saved("https://example.com/a"))

    def test_duplicates_are_rejected_including_url_variants(self):
        saved_articles.add_article(saved_articles.article_to_record(make_article()))

        self.assertFalse(saved_articles.add_article(saved_articles.article_to_record(make_article())))
        variant = make_article(link="HTTPS://EXAMPLE.com/a/#comments")
        self.assertFalse(saved_articles.add_article(saved_articles.article_to_record(variant)))
        self.assertEqual(len(saved_articles.list_articles()), 1)

    def test_different_query_strings_are_different_articles(self):
        saved_articles.add_article(saved_articles.article_to_record(make_article(link="https://example.com/p?id=1")))
        self.assertTrue(saved_articles.add_article(
            saved_articles.article_to_record(make_article(link="https://example.com/p?id=2"))))

    def test_remove(self):
        saved_articles.add_article(saved_articles.article_to_record(make_article()))

        self.assertTrue(saved_articles.remove_article("https://example.com/a/"))
        self.assertFalse(saved_articles.is_saved("https://example.com/a"))
        self.assertFalse(saved_articles.remove_article("https://example.com/a"))

    def test_article_without_url_is_keyed_by_title(self):
        record = saved_articles.article_to_record(make_article(link=""))
        self.assertTrue(saved_articles.add_article(record))
        self.assertFalse(saved_articles.add_article(saved_articles.article_to_record(make_article(link=""))))
        self.assertTrue(saved_articles.remove_article("", "Headline"))

    def test_list_is_most_recent_first(self):
        first = dict(saved_articles.article_to_record(make_article(link="https://example.com/1")),
                     saved_at="2026-01-01T00:00:00")
        second = dict(saved_articles.article_to_record(make_article(link="https://example.com/2")),
                      saved_at="2026-02-01T00:00:00")
        saved_articles.add_article(first)
        saved_articles.add_article(second)

        self.assertEqual([a["url"] for a in saved_articles.list_articles()],
                         ["https://example.com/2", "https://example.com/1"])

    def test_missing_file_is_empty(self):
        self.assertEqual(saved_articles.list_articles(), [])

    def test_corrupt_file_is_kept_aside_not_overwritten(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{not json")

        self.assertEqual(saved_articles.list_articles(), [])
        backups = [n for n in os.listdir(self.tmp.name) if n.startswith("saved_articles.json.corrupt-")]
        self.assertEqual(len(backups), 1)


if __name__ == "__main__":
    unittest.main()
