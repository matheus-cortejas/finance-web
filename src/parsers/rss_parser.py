from __future__ import annotations

import time
from datetime import datetime, timezone

from parsers.base_parser import BaseParser


class RSSParser(BaseParser):
    def __init__(self, url: str):
        self.url = url

    @staticmethod
    def _parse_date(entry) -> datetime:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            return datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)
        return datetime.now(timezone.utc)

    def fetch(self):
        try:
            import feedparser
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("feedparser is required to parse RSS feeds") from exc

        parsed = feedparser.parse(self.url)
        entries = []
        for entry in parsed.entries:
            content_values = []
            if entry.get("content"):
                try:
                    content_values = [content.get("value", "") for content in entry.get("content") if content.get("value")]
                except Exception:
                    content_values = []
            entries.append(
                {
                    "title": entry.get("title", "") or "",
                    "description": entry.get("description", "") or "",
                    "summary": entry.get("summary", "") or "",
                    "content": content_values,
                    "link": entry.get("link") or entry.get("id") or "",
                    "published": self._parse_date(entry),
                    "raw": entry,
                }
            )
        return {"href": getattr(parsed, "href", self.url), "entries": entries}
