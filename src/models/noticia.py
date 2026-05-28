from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class Noticia:
    id: Optional[int]
    link: str
    title: str
    description: str
    published_ts: Optional[int] = None
    feed_url: Optional[str] = None
    matched_assets: list[str] = field(default_factory=list)
