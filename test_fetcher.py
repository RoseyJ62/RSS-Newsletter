from datetime import UTC
import unittest
from xml.etree import ElementTree as ET

from news_digest.fetcher import _parse_atom, _parse_rss
from news_digest.models import Source


class FetcherTests(unittest.TestCase):
    def test_parse_rss_feed_item(self):
        root = ET.fromstring(
            """
            <rss version="2.0">
              <channel>
                <item>
                  <title>Headline</title>
                  <link>https://example.com/a</link>
                  <description><![CDATA[<p>Short summary.</p>]]></description>
                  <pubDate>Mon, 20 Apr 2026 13:30:00 GMT</pubDate>
                </item>
              </channel>
            </rss>
            """
        )

        articles = _parse_rss(root, Source(name="Example", url="https://example.com/rss", category="Top"))

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "Headline")
        self.assertEqual(articles[0].summary, "Short summary.")
        self.assertEqual(articles[0].published.tzinfo, UTC)


    def test_parse_atom_feed_item(self):
        root = ET.fromstring(
            """
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title>Atom Headline</title>
                <link href="https://example.com/atom" />
                <summary>Atom summary.</summary>
                <updated>2026-04-20T13:30:00Z</updated>
              </entry>
            </feed>
            """
        )

        articles = _parse_atom(root, Source(name="Example", url="https://example.com/atom", category="World"))

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].link, "https://example.com/atom")
        self.assertEqual(articles[0].category, "World")


if __name__ == "__main__":
    unittest.main()
