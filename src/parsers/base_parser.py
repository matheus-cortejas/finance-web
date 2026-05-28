from __future__ import annotations

from abc import ABC, abstractmethod


class BaseParser(ABC):
    @abstractmethod
    def fetch(self):
        raise NotImplementedError
