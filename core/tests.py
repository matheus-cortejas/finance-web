from __future__ import annotations

import os
from uuid import uuid4

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.contrib.auth.models import User
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from core.models import Ativo, Carteira
from core.services import noticia_service


class HomeAutoLoginTests(TestCase):
    def test_home_auto_logs_in_admin_when_runserver_is_active(self):
        with patch("core.views._is_runserver_context", return_value=True), patch.object(
            settings, "AUTO_LOGIN_ADMIN_ON_SERVER", True
        ):
            response = self.client.get(reverse("home"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user.username, settings.AUTO_LOGIN_ADMIN_USERNAME)


class WebViewsTests(TestCase):
    def setUp(self):
        self.username = f"webuser_{uuid4().hex[:8]}"
        self.user = User.objects.create_user(username=self.username, password="secret")
        self.asset, _ = Ativo.objects.get_or_create(ticker="PETR4", defaults={"nome": "Petrobras", "source": "b3"})

    def test_dashboard_redirects_anonymous_users(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_dashboard_renders_for_authenticated_user(self):
        self.client.login(username=self.username, password="secret")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Monitor Financeiro")

    def test_search_with_multiple_matches_shows_info_message(self):
        Ativo.objects.create(ticker="VALE3", nome="Vale S.A.")
        Ativo.objects.create(ticker="VALE4", nome="Vale S.A. PN")
        self.client.login(username=self.username, password="secret")
        response = self.client.post(reverse("dashboard"), {"asset_term": "VALE"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mais de um ativo encontrado")

    def test_empty_asset_term_shows_warning(self):
        self.client.login(username=self.username, password="secret")
        response = self.client.post(reverse("dashboard"), {"asset_term": ""}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe um código ou nome de ativo.")

    def test_dashboard_adds_unique_asset_to_carteira(self):
        self.client.login(username=self.username, password="secret")
        response = self.client.post(reverse("dashboard"), {"asset_term": "PETR4"}, follow=True)
        self.assertEqual(response.status_code, 200)
        carteira = Carteira.objects.get(usuario=self.user)
        self.assertTrue(carteira.ativos.filter(ticker="PETR4").exists())

    def test_dashboard_logout_uses_post_and_redirects_to_login(self):
        self.client.login(username=self.username, password="secret")
        response = self.client.post(reverse("logout"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Entrar")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_dashboard_added_asset_receives_alerts_from_news_pipeline(self):
        self.client.login(username=self.username, password="secret")
        self.client.post(reverse("dashboard"), {"asset_term": "PETR4"}, follow=True)

        parser = type(
            "ParserStub",
            (),
            {
                "fetch": lambda self: {
                    "href": "https://example.test/feed",
                    "entries": [
                        {
                            "title": "Petrobras anuncia investimento",
                            "description": "PETR4 amplia refino",
                            "summary": "",
                            "content": [],
                            "link": "https://example.test/petrobras-dashboard",
                            "published": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                        }
                    ],
                }
            },
        )()

        original_asset = self.asset
        with patch.object(noticia_service, "create_parser", return_value=parser), \
            patch.object(noticia_service, "seen_article", return_value=False), \
            patch.object(noticia_service, "is_relevant", return_value={"relevant": True, "matched": ["PETR4"], "reason": "match"}):
            noticia_service.check_feeds_and_report(
                ["https://example.test/feed"],
                [{"id": original_asset.id, "code": original_asset.ticker, "name": original_asset.nome}],
                within_days=1,
            )

        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Petrobras anuncia investimento")
        self.assertContains(response, 'target="_blank"')