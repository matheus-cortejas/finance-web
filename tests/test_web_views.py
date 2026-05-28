from __future__ import annotations

import os
from uuid import uuid4

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Ativo, Carteira
from core.services import noticia_service


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

    def test_home_shows_bootstrap_based_landing_page(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bootstrap@5.3.3")
        self.assertContains(response, "Criar conta")

    def test_chat_page_renders_for_authenticated_user(self):
        self.client.login(username=self.username, password="secret")
        response = self.client.get(reverse("chat"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assistente")
        self.assertContains(response, "Prompts rápidos")

    def test_chat_api_returns_ai_reply_and_stores_history(self):
        self.client.login(username=self.username, password="secret")

        with __import__("unittest.mock").mock.patch("core.services.chat_service.generate_chat_reply", return_value={"reply": "Resposta de teste", "provider": "fallback"}) as generate_reply:
            response = self.client.post(reverse("chat_api"), {"message": "Como funciona a dashboard?"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reply"], "Resposta de teste")
        generate_reply.assert_called_once()
        history = self.client.session.get("monitor_chat_history")
        self.assertIsNotNone(history)
        self.assertGreaterEqual(len(history), 3)

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
        self.assertContains(response, "Entre para acompanhar sua carteira.")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_home_registers_user_and_logs_in(self):
        username = f"homeuser_{uuid4().hex[:8]}"
        response = self.client.post(
            reverse("home"),
            {
                "action": "signup",
                "username": username,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username=username).exists())
        self.assertContains(response, "Monitor Financeiro")

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
        with __import__("unittest.mock").mock.patch.object(noticia_service, "create_parser", return_value=parser), \
            __import__("unittest.mock").mock.patch.object(noticia_service, "seen_article", return_value=False), \
            __import__("unittest.mock").mock.patch.object(noticia_service, "is_relevant", return_value={"relevant": True, "matched": ["PETR4"], "reason": "match"}):
            noticia_service.check_feeds_and_report(
                ["https://example.test/feed"],
                [{"id": original_asset.id, "code": original_asset.ticker, "name": original_asset.nome}],
                within_days=1,
            )

        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Petrobras anuncia investimento")
        self.assertContains(response, 'target="_blank"')
