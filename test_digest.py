from datetime import UTC, datetime
import unittest

from news_digest.digest import build_digest
from news_digest.models import Article, DigestSettings


class DigestTests(unittest.TestCase):
    def test_build_digest_groups_articles_and_includes_links(self):
        articles = (
            Article(
                title="Markets rally after central bank decision",
                link="https://example.com/markets",
                source="Example News",
                category="Business",
                published=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
                summary="Equities rose after policymakers held rates steady.",
            ),
        )

        digest = build_digest(articles, DigestSettings(title="Morning Brief"))

        self.assertIn("Morning Brief", digest.subject)
        self.assertIn("BUSINESS", digest.text)
        self.assertIn("Markets rally", digest.text)
        self.assertIn("https://example.com/markets", digest.html)


if __name__ == "__main__":
    unittest.main()
