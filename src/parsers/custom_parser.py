from __future__ import annotations

from parsers.base_parser import BaseParser


class CustomParser(BaseParser):
    def __init__(self, url: str):
        self.url = url

    def fetch(self):
        raise NotImplementedError("Custom HTML parser not implemented yet")
