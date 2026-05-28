from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class DatabaseRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        os.environ["DB_PATH"] = os.path.join(self.temp_dir.name, "test.db")

        for module_name in [
            "config.settings",
            "database.connection",
            "database.acao_repo",
            "database.noticia_repo",
        ]:
            sys.modules.pop(module_name, None)

        self.settings = importlib.import_module("config.settings")
        self.connection = importlib.import_module("database.connection")
        self.acao_repo = importlib.import_module("database.acao_repo")
        self.noticia_repo = importlib.import_module("database.noticia_repo")

        self.connection.init_db()
        self.addCleanup(self._clear_env)

    def _clear_env(self):
        os.environ.pop("DB_PATH", None)

    def test_insert_asset_and_watchlist_flow(self):
        self.acao_repo.insert_asset("b3", "PETR4", "PETROBRAS")

        asset = self.acao_repo.asset_exists(code="PETR4")
        self.assertIsNotNone(asset)
        self.assertEqual(asset["code"], "PETR4")
        self.assertEqual(self.acao_repo.count_assets_by_source("b3"), 1)

        self.acao_repo.add_to_watchlist(asset["id"])
        watchlist = self.acao_repo.get_watchlist_assets()
        self.assertEqual(len(watchlist), 1)
        self.assertEqual(watchlist[0]["code"], "PETR4")

    def test_save_and_purge_articles(self):
        self.acao_repo.insert_asset("b3", "ABEV3", "AMBEV")
        asset = self.acao_repo.asset_exists(code="ABEV3")
        self.acao_repo.add_to_watchlist(asset["id"])

        article_id = self.noticia_repo.save_article(
            "https://example.test/ambev",
            "Ambev reporta vendas",
            "ABEV3 cresce",
            published_ts=1,
            feed_url="https://example.test/feed",
        )
        self.assertIsInstance(article_id, int)

        self.noticia_repo.mark_article_seen("https://example.test/ambev", published_ts=1)
        self.noticia_repo.link_article_match(article_id, asset["id"])

        self.assertTrue(self.noticia_repo.seen_article("https://example.test/ambev"))

        deleted = self.noticia_repo.purge_articles_older_than_days(1)
        self.assertEqual(deleted, 1)
        self.assertFalse(self.noticia_repo.seen_article("https://example.test/ambev"))


if __name__ == "__main__":
    unittest.main()