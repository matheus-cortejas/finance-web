from __future__ import annotations

import os
from uuid import uuid4

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from core.models import (
    Alerta,
    Ativo,
    Carteira,
    InteracaoNoticia,
    Noticia,
    NoticiaClassificacao,
    NoticiaScore,
    PerfilInvestidor,
)
from core.services import noticia_service
from core.services.interacao_service import update_profile_from_interactions
from core.services.scoring_service import calculate_relevance_score, score_to_priority


def _make_pipeline_result(title="Noticia", description="Descricao", content="Conteudo", tickers=None):
    return {
        "id": None,
        "titulo": title,
        "descricao": description,
        "conteudo": content,
        "relevancia_binaria": 1,
        "relevancia_global": 0.8,
        "score_heuristico": 8,
        "sentimento": "negativo",
        "impacto": "alto",
        "urgencia": 7,
        "categoria": "empresa",
        "explicacao": "Ticker mencionado explicitamente.",
        "tickers_relacionados": tickers or [],
    }


def _make_decision(prioridade="alta", score_final=0.85):
    return {
        "prioridade": prioridade,
        "acao_sugerida": ["push", "dashboard"],
        "score_final": score_final,
        "explicacao_regra": "Alto impacto ou urgencia elevada.",
    }


class WebViewsTests(TestCase):
    def setUp(self):
        self.username = f"webuser_{uuid4().hex[:8]}"
        self.user = User.objects.create_user(username=self.username, password="secret")
        self.asset, _ = Ativo.objects.get_or_create(ticker="PETR4", defaults={"nome": "Petrobras", "source": "b3"})

    def test_dashboard_redirects_anonymous_users(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_home_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_home_redirects_authenticated_users_to_dashboard(self):
        self.client.login(username=self.username, password="secret")
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard"), response.url)

    def test_dashboard_renders_for_authenticated_user(self):
        self.client.login(username=self.username, password="secret")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Monitor Financeiro")

    def test_search_with_multiple_matches_shows_info_message(self):
        Ativo.objects.get_or_create(ticker="VALE3", defaults={"nome": "Vale S.A."})
        Ativo.objects.get_or_create(ticker="VALE4", defaults={"nome": "Vale S.A. PN"})
        self.client.login(username=self.username, password="secret")
        response = self.client.post(reverse("dashboard"), {"asset_term": "VALE"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mais de um ativo encontrado")

    def test_empty_asset_term_shows_warning(self):
        self.client.login(username=self.username, password="secret")
        response = self.client.post(reverse("dashboard"), {"asset_term": ""}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "c\u00f3digo ou nome de ativo")

    def test_dashboard_adds_unique_asset_to_carteira(self):
        self.client.login(username=self.username, password="secret")
        response = self.client.post(reverse("dashboard"), {"asset_term": "PETR4"}, follow=True)
        self.assertEqual(response.status_code, 200)
        carteira = Carteira.objects.get(usuario=self.user)
        self.assertTrue(carteira.ativos.filter(ticker="PETR4").exists())

    def test_asset_suggestions_returns_prefix_matches(self):
        Ativo.objects.get_or_create(ticker="PETZ3", defaults={"nome": "Petz", "source": "b3"})
        Ativo.objects.get_or_create(ticker="PEAB3", defaults={"nome": "Peabirus", "source": "b3"})
        Ativo.objects.get_or_create(ticker="VALE3", defaults={"nome": "Vale S.A.", "source": "b3"})

        self.client.login(username=self.username, password="secret")
        response = self.client.get(reverse("asset_suggestions"), {"q": "pe"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        tickers = [item["ticker"] for item in payload["results"]]
        self.assertIn("PEAB3", tickers)
        self.assertIn("PETR4", tickers)
        self.assertIn("PETZ3", tickers)
        self.assertNotIn("VALE3", tickers)

    def test_dashboard_removes_asset_from_carteira(self):
        carteira, _ = Carteira.objects.get_or_create(usuario=self.user)
        carteira.ativos.add(self.asset)

        self.client.login(username=self.username, password="secret")
        response = self.client.post(reverse("dashboard"), {"remove_asset_id": str(self.asset.id)}, follow=True)

        self.assertEqual(response.status_code, 200)
        carteira.refresh_from_db()
        self.assertFalse(carteira.ativos.filter(ticker="PETR4").exists())
        self.assertContains(response, "PETR4 removido da sua carteira.")

    def test_dashboard_logout_uses_post_and_redirects_to_login(self):
        self.client.login(username=self.username, password="secret")
        response = self.client.post(reverse("logout"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Entrar")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    @patch("core.services.noticia_service.decidir_alerta")
    @patch("core.services.noticia_service.processar_noticia_completa")
    @patch("core.services.noticia_service.seen_article", return_value=False)
    @patch("core.services.noticia_service.create_parser")
    def test_dashboard_added_asset_receives_alerts_from_news_pipeline(
        self, mock_create_parser, mock_seen, mock_pipeline, mock_decidir
    ):
        self.client.login(username=self.username, password="secret")
        self.client.post(reverse("dashboard"), {"asset_term": "PETR4"}, follow=True)

        mock_create_parser.return_value.fetch.return_value = {
            "href": "https://example.test/feed",
            "entries": [
                {
                    "title": "Petrobras anuncia investimento",
                    "description": "PETR4 amplia refino",
                    "content": [],
                    "link": "https://example.test/petrobras-dashboard",
                    "published": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                }
            ],
        }

        pipeline_result = _make_pipeline_result(
            title="Petrobras anuncia investimento",
            description="PETR4 amplia refino",
            tickers=["PETR4"],
        )
        mock_pipeline.return_value = pipeline_result
        mock_decidir.return_value = _make_decision()

        noticia_service.check_feeds_and_report(
            ["https://example.test/feed"],
            within_days=1,
        )

        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Petrobras anuncia investimento")
        self.assertContains(response, "/noticia/")

    @patch("core.services.noticia_service.decidir_alerta")
    @patch("core.services.noticia_service.processar_noticia_completa")
    @patch("core.services.noticia_service.seen_article", return_value=False)
    @patch("core.services.noticia_service.create_parser")
    def test_alert_created_when_match_only_in_content(
        self, mock_create_parser, mock_seen, mock_pipeline, mock_decidir
    ):
        self.client.login(username=self.username, password="secret")
        self.client.post(reverse("dashboard"), {"asset_term": "PETR4"}, follow=True)

        mock_create_parser.return_value.fetch.return_value = {
            "href": "https://example.test/feed",
            "entries": [
                {
                    "title": "Mercado em foco",
                    "description": "",
                    "content": [],
                    "link": "https://example.test/petrobras-content",
                    "published": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                }
            ],
        }

        pipeline_result = _make_pipeline_result(
            title="Mercado em foco",
            tickers=["PETR4"],
        )
        mock_pipeline.return_value = pipeline_result
        mock_decidir.return_value = _make_decision()

        noticia_service.check_feeds_and_report(
            ["https://example.test/feed"],
            within_days=1,
        )

        self.assertTrue(Alerta.objects.filter(usuario=self.user, noticia__link="https://example.test/petrobras-content").exists())

    @patch("core.services.noticia_service.decidir_alerta")
    @patch("core.services.noticia_service.processar_noticia_completa")
    @patch("core.services.noticia_service.seen_article", return_value=False)
    @patch("core.services.noticia_service.create_parser")
    def test_alert_created_when_alias_matches_content(
        self, mock_create_parser, mock_seen, mock_pipeline, mock_decidir
    ):
        self.client.login(username=self.username, password="secret")
        self.client.post(reverse("dashboard"), {"asset_term": "PETR4"}, follow=True)

        mock_create_parser.return_value.fetch.return_value = {
            "href": "https://example.test/feed",
            "entries": [
                {
                    "title": "Noticias do setor",
                    "description": "",
                    "content": [],
                    "link": "https://example.test/petrobras-alias",
                    "published": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                }
            ],
        }

        pipeline_result = _make_pipeline_result(
            title="Noticias do setor",
            tickers=["PETR4"],
        )
        mock_pipeline.return_value = pipeline_result
        mock_decidir.return_value = _make_decision()

        noticia_service.check_feeds_and_report(
            ["https://example.test/feed"],
            within_days=1,
        )

        self.assertTrue(Alerta.objects.filter(usuario=self.user, noticia__link="https://example.test/petrobras-alias").exists())


class ScoringServiceTests(TestCase):
    def test_calculate_relevance_score_returns_priority(self):
        classificacao = {
            "sentimento": "negativo",
            "impacto": "alto",
            "urgencia": "alta",
            "setor": "energia",
            "tickers_relacionados": ["PETR4"],
            "relevancia_llm": 1.0,
        }
        perfil = PerfilInvestidor(
            perfil_risco="moderado",
            sensibilidade_negativo=0.6,
            setores_preferidos=["energia"],
        )
        result = calculate_relevance_score(
            classificacao,
            perfil=perfil,
            carteira_tickers=["PETR4"],
            fonte_confiabilidade=1.0,
        )

        self.assertGreaterEqual(result["score_final"], 85.0)
        self.assertEqual(result["prioridade"], "critica")
        self.assertEqual(score_to_priority(result["score_final"]), "critica")


class InteractionProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username=f"user_{uuid4().hex[:6]}", password="secret")

    def test_record_interaction_updates_profile(self):
        noticia = Noticia.objects.create(
            link="https://example.test/n1",
            titulo="Queda forte",
        )
        NoticiaClassificacao.objects.create(
            noticia=noticia,
            sentimento="negativo",
            impacto="alto",
            urgencia="alta",
            setor="energia",
        )

        self.client.login(username=self.user.username, password="secret")
        response = self.client.post(
            reverse("record_interaction"),
            {"noticia_id": noticia.id, "acao": "abriu", "origem": "dashboard"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            InteracaoNoticia.objects.filter(usuario=self.user, noticia=noticia, abriu=True).exists()
        )

        perfil = PerfilInvestidor.objects.get(usuario=self.user)
        update_profile_from_interactions(self.user)
        perfil.refresh_from_db()
        self.assertGreaterEqual(perfil.sensibilidade_negativo, 0.8)
        self.assertIn("energia", perfil.setores_preferidos)


class PriorityPipelineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username=f"user_{uuid4().hex[:6]}", password="secret")
        self.asset, _ = Ativo.objects.get_or_create(ticker="PETR4", defaults={"nome": "Petrobras", "source": "b3"})
        carteira, _ = Carteira.objects.get_or_create(usuario=self.user)
        carteira.ativos.add(self.asset)

    @override_settings(ENABLE_PRIORITY_ENGINE=True, ALERT_MIN_PRIORITY="alta")
    @patch("core.services.noticia_service.decidir_alerta")
    @patch("core.services.noticia_service.processar_noticia_completa")
    @patch("core.services.noticia_service.seen_article", return_value=False)
    @patch("core.services.noticia_service.create_parser")
    def test_priority_engine_creates_score_and_alert(
        self, mock_create_parser, mock_seen, mock_pipeline, mock_decidir
    ):
        mock_create_parser.return_value.fetch.return_value = {
            "href": "https://example.test/feed",
            "entries": [
                {
                    "title": "Petrobras anuncia investimento",
                    "description": "PETR4 amplia refino",
                    "content": [],
                    "link": "https://example.test/petrobras-score",
                    "published": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                }
            ],
        }

        pipeline_result = _make_pipeline_result(
            title="Petrobras anuncia investimento",
            description="PETR4 amplia refino",
            tickers=["PETR4"],
        )
        mock_pipeline.return_value = pipeline_result
        mock_decidir.return_value = _make_decision(prioridade="alta", score_final=0.85)

        noticia_service.check_feeds_and_report(
            ["https://example.test/feed"],
            within_days=1,
        )

        self.assertTrue(NoticiaScore.objects.filter(usuario=self.user).exists())
        self.assertTrue(Alerta.objects.filter(usuario=self.user, ativos=self.asset).exists())

    @override_settings(ENABLE_PRIORITY_ENGINE=True, ALERT_MIN_PRIORITY="alta")
    @patch("core.services.noticia_service.decidir_alerta")
    @patch("core.services.noticia_service.processar_noticia_completa")
    @patch("core.services.noticia_service.seen_article", return_value=False)
    @patch("core.services.noticia_service.create_parser")
    def test_priority_engine_respects_threshold(
        self, mock_create_parser, mock_seen, mock_pipeline, mock_decidir
    ):
        mock_create_parser.return_value.fetch.return_value = {
            "href": "https://example.test/feed",
            "entries": [
                {
                    "title": "Nota neutra",
                    "description": "PETR4 noticia sem impacto",
                    "content": [],
                    "link": "https://example.test/petrobras-low",
                    "published": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                }
            ],
        }

        pipeline_result = _make_pipeline_result(
            title="Nota neutra",
            description="PETR4 noticia sem impacto",
            tickers=["PETR4"],
        )
        pipeline_result["sentimento"] = "neutro"
        pipeline_result["impacto"] = "baixo"
        pipeline_result["urgencia"] = 2
        pipeline_result["relevancia_global"] = 0.1
        mock_pipeline.return_value = pipeline_result
        mock_decidir.return_value = _make_decision(prioridade="baixa", score_final=0.15)

        perfil = PerfilInvestidor.objects.get(usuario=self.user)
        perfil.alerta_min_prioridade = "alta"
        perfil.save(update_fields=["alerta_min_prioridade"])

        noticia_service.check_feeds_and_report(
            ["https://example.test/feed"],
            within_days=1,
        )

        self.assertTrue(NoticiaScore.objects.filter(usuario=self.user).exists())
        self.assertFalse(Alerta.objects.filter(usuario=self.user, ativos=self.asset).exists())
