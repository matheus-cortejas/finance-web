from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from llm import openai_client
from services import noticia_service


class NoticiaServiceTests(unittest.TestCase):
    def test_filters_and_persists_matching_article(self):
        parser = Mock()
        parser.fetch.return_value = {
            "href": "https://example.test/feed",
            "entries": [
                {
                    "title": "Petrobras anuncia investimento",
                    "description": "PETR4 amplia refino",
                    "summary": "",
                    "content": ["PETR4 confirma plano"],
                    "link": "https://example.test/petrobras",
                    "published": datetime.now(timezone.utc),
                }
            ],
        }

        with patch.object(noticia_service, "create_parser", return_value=parser), \
            patch.object(noticia_service, "seen_article", return_value=False), \
            patch.object(noticia_service, "mark_article_seen") as mark_seen, \
            patch.object(noticia_service, "save_article", return_value=42) as save_article, \
            patch.object(noticia_service, "link_article_match") as link_match, \
            patch.object(noticia_service, "is_relevant", return_value={"relevant": True, "matched": ["PETR4"], "reason": "match"}) as is_relevant:
            reports = noticia_service.check_feeds_and_report(
                ["https://example.test/feed"],
                [{"id": 7, "code": "PETR4", "name": "PETROBRAS"}],
                within_days=1,
            )

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["title"], "Petrobras anuncia investimento")
        self.assertEqual(reports[0]["matches"], [("PETR4", "PETROBRAS")])
        mark_seen.assert_called_once()
        save_article.assert_called_once()
        link_match.assert_called_once_with(42, 7)
        is_relevant.assert_called_once()

    def test_skips_entries_outside_cutoff(self):
        parser = Mock()
        parser.fetch.return_value = {
            "href": "https://example.test/feed",
            "entries": [
                {
                    "title": "Antiga",
                    "description": "PETR4",
                    "summary": "",
                    "content": [],
                    "link": "https://example.test/old",
                    "published": datetime(2000, 1, 1, tzinfo=timezone.utc),
                }
            ],
        }

        with patch.object(noticia_service, "create_parser", return_value=parser), \
            patch.object(noticia_service, "seen_article", return_value=False), \
            patch.object(noticia_service, "mark_article_seen") as mark_seen, \
            patch.object(noticia_service, "save_article") as save_article:
            reports = noticia_service.check_feeds_and_report(
                ["https://example.test/feed"],
                [{"id": 7, "code": "PETR4", "name": "PETROBRAS"}],
                within_days=1,
            )

        self.assertEqual(reports, [])
        mark_seen.assert_not_called()
        save_article.assert_not_called()

    def test_heuristic_relevance_fallback_without_openai_key(self):
        with patch.object(openai_client, "OPENAI_API_KEY", None):
            result = openai_client.judge_article_relevance(
                "Vale estende vida útil do complexo de Itabira (MG) até 2053",
                "",
                "",
                [{"id": 1, "code": "VALE3", "name": "VALE"}],
            )

        self.assertTrue(result["relevant"])
        self.assertEqual(result["matched"], ["VALE3"])
        self.assertIn("Heuristic fallback", result["reason"])

    def test_content_only_mentions_do_not_alert(self):
        parser = Mock()
        parser.fetch.return_value = {
            "href": "https://example.test/feed",
            "entries": [
                {
                    "title": "Atualização de mercado sem gatilho no título",
                    "description": "Resumo neutro",
                    "summary": "",
                    "content": ["O texto menciona PETR4 apenas no corpo da notícia."],
                    "link": "https://example.test/content-only",
                    "published": datetime.now(timezone.utc),
                }
            ],
        }

        with patch.object(noticia_service, "create_parser", return_value=parser), \
            patch.object(noticia_service, "seen_article", return_value=False), \
            patch.object(noticia_service, "mark_article_seen") as mark_seen, \
            patch.object(noticia_service, "save_article", return_value=99) as save_article, \
            patch.object(noticia_service, "is_relevant") as is_relevant, \
            patch.object(noticia_service, "link_article_match") as link_match:
            reports = noticia_service.check_feeds_and_report(
                ["https://example.test/feed"],
                [{"id": 7, "code": "PETR4", "name": "PETROBRAS"}],
                within_days=1,
            )

        self.assertEqual(reports, [])
        mark_seen.assert_called_once()
        save_article.assert_called_once()
        is_relevant.assert_not_called()
        link_match.assert_not_called()

    def test_description_only_mentions_do_not_alert(self):
        parser = Mock()
        parser.fetch.return_value = {
            "href": "https://example.test/feed",
            "entries": [
                {
                    "title": "Mercado em destaque sem empresa no título",
                    "description": "PETR4 aparece só no resumo da matéria.",
                    "summary": "",
                    "content": [],
                    "link": "https://example.test/description-only",
                    "published": datetime.now(timezone.utc),
                }
            ],
        }

        with patch.object(noticia_service, "create_parser", return_value=parser), \
            patch.object(noticia_service, "seen_article", return_value=False), \
            patch.object(noticia_service, "mark_article_seen") as mark_seen, \
            patch.object(noticia_service, "save_article", return_value=100) as save_article, \
            patch.object(noticia_service, "is_relevant") as is_relevant, \
            patch.object(noticia_service, "link_article_match") as link_match:
            reports = noticia_service.check_feeds_and_report(
                ["https://example.test/feed"],
                [{"id": 7, "code": "PETR4", "name": "PETROBRAS"}],
                within_days=1,
            )

        self.assertEqual(reports, [])
        mark_seen.assert_called_once()
        save_article.assert_called_once()
        is_relevant.assert_not_called()
        link_match.assert_not_called()


if __name__ == "__main__":
    unittest.main()