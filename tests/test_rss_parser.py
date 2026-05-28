from __future__ import annotations

import os
import sys
import time
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from parsers.rss_parser import RSSParser


class FakeEntry(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


class RSSParserTests(unittest.TestCase):
    def test_fetch_converts_feed_entries(self):
        fake_feedparser = types.SimpleNamespace(
            parse=lambda url: types.SimpleNamespace(
                href=url,
                entries=[
                    FakeEntry(
                        title="Example title",
                        description="Example description",
                        summary="Example summary",
                        content=[{"value": "Body text"}],
                        link="https://example.test/article",
                        published_parsed=time.gmtime(0),
                    )
                ],
            )
        )

        with patch.dict(sys.modules, {"feedparser": fake_feedparser}):
            result = RSSParser("https://example.test/feed").fetch()

        self.assertEqual(result["href"], "https://example.test/feed")
        self.assertEqual(len(result["entries"]), 1)
        entry = result["entries"][0]
        self.assertEqual(entry["title"], "Example title")
        self.assertEqual(entry["description"], "Example description")
        self.assertEqual(entry["summary"], "Example summary")
        self.assertEqual(entry["content"], ["Body text"])
        self.assertEqual(entry["link"], "https://example.test/article")
        self.assertEqual(int(entry["published"].timestamp()), int(time.mktime(time.gmtime(0))))


if __name__ == "__main__":
    unittest.main()