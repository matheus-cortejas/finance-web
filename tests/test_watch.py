from __future__ import annotations

import os
from uuid import uuid4

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.test import TestCase

from core import data_access
from core.models import Ativo


class WatchlistSmokeTests(TestCase):
    def setUp(self):
        self.asset = Ativo.objects.create(
            ticker=f"TEST{uuid4().hex[:6].upper()}",
            nome="Ativo de teste",
            source="b3",
        )

    def test_asset_exists_by_code_and_name(self):
        found_by_code = data_access.asset_exists(code=self.asset.ticker)
        found_by_name = data_access.asset_exists(name=self.asset.nome)

        self.assertEqual(found_by_code["code"], self.asset.ticker)
        self.assertEqual(found_by_name["name"], self.asset.nome)

    def test_add_to_watchlist_registers_default_carteira(self):
        data_access.add_to_watchlist(self.asset.id)

        watchlist = data_access.get_watchlist_assets()
        self.assertTrue(any(asset["id"] == self.asset.id for asset in watchlist))
