from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.contrib.auth.models import User
from django.test import TestCase

from core import data_access
from core.models import Alerta, Ativo, Carteira, Noticia


class DjangoModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username=f"alice_{uuid4().hex[:8]}", password="secret")

    def test_ativo_and_carteira_relationship(self):
        ativo, _ = Ativo.objects.get_or_create(ticker="PETR4", defaults={"nome": "PETROBRAS", "source": "b3"})
        carteira, _ = Carteira.objects.get_or_create(usuario=self.user, defaults={"nome": "Principal"})
        carteira.ativos.add(ativo)

        self.assertTrue(Ativo.objects.filter(ticker="PETR4").exists())
        self.assertEqual(carteira.ativos.first().ticker, "PETR4")

    def test_noticia_and_alerta_models(self):
        ativo, _ = Ativo.objects.get_or_create(ticker="ABEV3", defaults={"nome": "AMBEV", "source": "b3"})
        carteira, _ = Carteira.objects.get_or_create(usuario=self.user)
        carteira.ativos.add(ativo)

        unique_id = uuid4().hex[:8]
        noticia = Noticia.objects.create(
            link=f"https://example.test/ambev-{unique_id}",
            titulo="Ambev reporta vendas",
            descricao="ABEV3 cresce",
            publicado_em=datetime(2026, 1, 1, tzinfo=timezone.utc),
            feed_url="https://example.test/feed",
            impacto="alto",
        )
        alerta = Alerta.objects.create(usuario=self.user, noticia=noticia, ativo=ativo)

        self.assertEqual(alerta.noticia.link, noticia.link)
        self.assertTrue(Alerta.objects.filter(usuario=self.user, noticia=noticia, ativo=ativo).exists())

    def test_data_access_save_and_purge_articles(self):
        unique_id = uuid4().hex[:8]
        article_id = data_access.save_article(
            f"https://example.test/vale-{unique_id}",
            "Vale amplia operação",
            "VALE3 em destaque",
            published_ts=1,
            feed_url="https://example.test/feed",
        )

        self.assertIsInstance(article_id, int)
        self.assertTrue(data_access.seen_article(f"https://example.test/vale-{unique_id}"))

        deleted = data_access.purge_articles_older_than_days(1)
        self.assertGreaterEqual(deleted, 1)
        self.assertFalse(Noticia.objects.filter(link=f"https://example.test/vale-{unique_id}").exists())