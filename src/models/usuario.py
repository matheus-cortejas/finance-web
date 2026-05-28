from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class Usuario:
    id: Optional[int]
    name: str = "default"
    watchlist_assets: list[int] = field(default_factory=list)
