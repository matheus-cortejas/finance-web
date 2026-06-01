from __future__ import annotations

import html
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.parsers.base_parser import BaseParser


class RSSParser(BaseParser):
    """Parser para feeds RSS/RDF/Atom usando feedparser."""

    def __init__(self, url: str):
        self.url = url

    @staticmethod
    def _parse_date(entry) -> datetime:
        """Extrai a data de publicação do entry do feed."""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            return datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)
        return datetime.now(timezone.utc)

    @staticmethod
    def _clean_html(text: str) -> str:
        """Remove tags HTML, decodifica entidades e normaliza espaços."""
        if not text:
            return ""
        # Decodifica entidades HTML (&nbsp;, &amp;, etc.)
        text = html.unescape(text)
        # Remove tags HTML (qualquer coisa entre < e >)
        text = re.sub(r"<[^>]+>", " ", text)
        # Remove frases comuns de rodapé
        text = re.sub(r"The post .*? appeared first on .*", "", text)
        text = re.sub(r"Leia também.*$", "", text, flags=re.DOTALL)
        # Remove whitespace excessivo
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _extract_description(self, entry) -> str:
        """Extrai a descrição/resumo da notícia."""
        # Tenta description, depois summary
        raw = entry.get("description", "") or entry.get("summary", "") or ""
        if not raw:
            return ""
        return self._clean_html(raw)

    def _extract_content(self, entry) -> str:
        """
        Extrai o conteúdo completo da notícia (content:encoded ou content).
        Retorna uma string limpa (sem HTML).
        """
        content_parts = []

        # 1. Tenta o campo 'content' (geralmente usado por content:encoded)
        if entry.get("content"):
            for c in entry.get("content"):
                if isinstance(c, dict):
                    value = c.get("value", "")
                    if value:
                        content_parts.append(value)
                elif isinstance(c, str):
                    content_parts.append(c)

        # 2. Se não achou, tenta o campo 'summary' (se for mais completo que description)
        if not content_parts and entry.get("summary"):
            content_parts.append(entry.get("summary"))

        # 3. Fallback para description (caso não haja content)
        if not content_parts and entry.get("description"):
            content_parts.append(entry.get("description"))

        if not content_parts:
            return ""

        # Junta todas as partes e limpa HTML
        raw_content = " ".join(content_parts)
        return self._clean_html(raw_content)

    def fetch(self) -> Dict[str, Any]:
        """
        Busca e parseia o feed RSS.
        Retorna um dicionário com:
            - href: URL do feed
            - entries: lista de dicionários com os dados de cada notícia
        """
        try:
            import feedparser
        except ImportError as exc:
            raise RuntimeError("feedparser is required to parse RSS feeds") from exc

        parsed = feedparser.parse(self.url)
        entries = []

        for entry in parsed.entries:
            # Extrai os campos
            title = (entry.get("title") or "").strip()
            link = entry.get("link") or entry.get("id") or ""
            description = self._extract_description(entry)
            content = self._extract_content(entry)
            published = self._parse_date(entry)

            # Se description estiver vazia mas content existe, usa content como fallback
            if not description and content:
                description = content[:500]  # resumo curto

            entries.append({
                "title": title,
                "link": link,
                "description": description,
                "summary": description,   # compatibilidade
                "content": content,       # agora é string, não lista
                "published": published,
                "raw": entry,             # dados brutos para debug
            })

        return {
            "href": getattr(parsed, "href", self.url),
            "entries": entries,
        }