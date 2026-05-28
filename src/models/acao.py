from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class Acao:
    id: Optional[int]
    source: str
    code: str
    name: str
