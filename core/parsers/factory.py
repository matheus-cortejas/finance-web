from __future__ import annotations

from core.parsers.custom_parser import CustomParser
from core.parsers.rss_parser import RSSParser


def create_parser(url: str):
    lowered = url.lower()
    if lowered.endswith(".html") or lowered.endswith(".htm"):
        return CustomParser(url)
    return RSSParser(url)