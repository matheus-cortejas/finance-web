from __future__ import annotations

import os
from datetime import datetime, timezone
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
from core.forms import PerfilInvestidorForm, RegistroForm
from core.parsers.factory import create_parser
from core.parsers.rss_parser import RSSParser
from core.parsers.custom_parser import CustomParser
from core.services import noticia_service
from core.services.interacao_service import update_profile_from_interactions
from core.services.scoring_service import (
    calculate_relevance_score,
    is_priority_at_least,
    score_to_priority,
)
from core.services.usuario_service import list_watchlist_assets

TEST_FEED = "https://example.test/feed"
TEST_TICKER = "PETR4"


def _make_feed(title, link, description="", content=None):
    return {
        "href": TEST_FEED,
        "entries": [
            {
                "title": title,
                "description": description,
                "content": content or [],
                "link": link,
                "published": datetime.now(timezone.utc),
            }
        ],
    }


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
        self.asset, _ = Ativo.objects.get_or_create(ticker=TEST_TICKER, defaults={"nome": "Petrobras", "source": "b3"})

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
        response = self.client.post(reverse("dashboard"), {"asset_term": TEST_TICKER}, follow=True)
        self.assertEqual(response.status_code, 200)
        carteira = Carteira.objects.get(usuario=self.user)
        self.assertTrue(carteira.ativos.filter(ticker=TEST_TICKER).exists())

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
        self.assertIn(TEST_TICKER, tickers)
        self.assertIn("PETZ3", tickers)
        self.assertNotIn("VALE3", tickers)

    def test_dashboard_removes_asset_from_carteira(self):
        carteira, _ = Carteira.objects.get_or_create(usuario=self.user)
        carteira.ativos.add(self.asset)

        self.client.login(username=self.username, password="secret")
        response = self.client.post(reverse("dashboard"), {"remove_asset_id": str(self.asset.id)}, follow=True)

        self.assertEqual(response.status_code, 200)
        carteira.refresh_from_db()
        self.assertFalse(carteira.ativos.filter(ticker=TEST_TICKER).exists())
        self.assertContains(response, f"{TEST_TICKER} removido da sua carteira.")

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
        self.client.post(reverse("dashboard"), {"asset_term": TEST_TICKER}, follow=True)

        mock_create_parser.return_value.fetch.return_value = _make_feed(
            title="Petrobras anuncia investimento",
            description=f"{TEST_TICKER} amplia refino",
            link="https://example.test/petrobras-dashboard",
        )

        pipeline_result = _make_pipeline_result(
            title="Petrobras anuncia investimento",
            description=f"{TEST_TICKER} amplia refino",
            tickers=[TEST_TICKER],
        )
        mock_pipeline.return_value = pipeline_result
        mock_decidir.return_value = _make_decision()

        noticia_service.check_feeds_and_report(
            [TEST_FEED],
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
        self.client.post(reverse("dashboard"), {"asset_term": TEST_TICKER}, follow=True)

        mock_create_parser.return_value.fetch.return_value = _make_feed(
            title="Mercado em foco",
            link="https://example.test/petrobras-content",
        )

        pipeline_result = _make_pipeline_result(
            title="Mercado em foco",
            tickers=[TEST_TICKER],
        )
        mock_pipeline.return_value = pipeline_result
        mock_decidir.return_value = _make_decision()

        noticia_service.check_feeds_and_report(
            [TEST_FEED],
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
        self.client.post(reverse("dashboard"), {"asset_term": TEST_TICKER}, follow=True)

        mock_create_parser.return_value.fetch.return_value = _make_feed(
            title="Noticias do setor",
            link="https://example.test/petrobras-alias",
        )

        pipeline_result = _make_pipeline_result(
            title="Noticias do setor",
            tickers=[TEST_TICKER],
        )
        mock_pipeline.return_value = pipeline_result
        mock_decidir.return_value = _make_decision()

        noticia_service.check_feeds_and_report(
            [TEST_FEED],
            within_days=1,
        )

        self.assertTrue(Alerta.objects.filter(usuario=self.user, noticia__link="https://example.test/petrobras-alias").exists())


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


class ScoringServiceTests(TestCase):
    def test_calculate_relevance_score_returns_priority(self):
        classificacao = {
            "sentimento": "negativo",
            "impacto": "alto",
            "urgencia": "alta",
            "setor": "energia",
            "tickers_relacionados": [TEST_TICKER],
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
            carteira_tickers=[TEST_TICKER],
            fonte_confiabilidade=1.0,
        )

        self.assertGreaterEqual(result["score_final"], 85.0)
        self.assertEqual(result["prioridade"], "critica")
        self.assertEqual(score_to_priority(result["score_final"]), "critica")


class PriorityPipelineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username=f"user_{uuid4().hex[:6]}", password="secret")
        self.asset, _ = Ativo.objects.get_or_create(ticker=TEST_TICKER, defaults={"nome": "Petrobras", "source": "b3"})
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
        mock_create_parser.return_value.fetch.return_value = _make_feed(
            title="Petrobras anuncia investimento",
            description=f"{TEST_TICKER} amplia refino",
            link="https://example.test/petrobras-score",
        )

        pipeline_result = _make_pipeline_result(
            title="Petrobras anuncia investimento",
            description=f"{TEST_TICKER} amplia refino",
            tickers=[TEST_TICKER],
        )
        mock_pipeline.return_value = pipeline_result
        mock_decidir.return_value = _make_decision(prioridade="alta", score_final=0.85)

        noticia_service.check_feeds_and_report(
            [TEST_FEED],
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
        mock_create_parser.return_value.fetch.return_value = _make_feed(
            title="Nota neutra",
            description=f"{TEST_TICKER} noticia sem impacto",
            link="https://example.test/petrobras-low",
        )

        pipeline_result = _make_pipeline_result(
            title="Nota neutra",
            description=f"{TEST_TICKER} noticia sem impacto",
            tickers=[TEST_TICKER],
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
            [TEST_FEED],
            within_days=1,
        )

        self.assertTrue(NoticiaScore.objects.filter(usuario=self.user).exists())
        self.assertFalse(Alerta.objects.filter(usuario=self.user, ativos=self.asset).exists())


# =============================================================================
# ScoringServiceUnitTests - testes puros de scoring (sem banco)
# =============================================================================


class ScoringServiceUnitTests(TestCase):
    """Testes unitários do scoring_service - comportamento observável."""

    def _base_classificacao(self, **overrides):
        base = {
            "sentimento": "neutro",
            "impacto": "medio",
            "urgencia": "media",
            "setor": "",
            "tickers_relacionados": [],
            "relevancia_llm": 0.5,
        }
        base.update(overrides)
        return base

    # --- Faixas de prioridade ---

    def test_score_to_priority_39_baixa(self):
        self.assertEqual(score_to_priority(39), "baixa")

    def test_score_to_priority_40_media(self):
        self.assertEqual(score_to_priority(40), "media")

    def test_score_to_priority_64_media(self):
        self.assertEqual(score_to_priority(64), "media")

    def test_score_to_priority_65_alta(self):
        self.assertEqual(score_to_priority(65), "alta")

    def test_score_to_priority_84_alta(self):
        self.assertEqual(score_to_priority(84), "alta")

    def test_score_to_priority_85_critica(self):
        self.assertEqual(score_to_priority(85), "critica")

    # --- Regras de negócio ---

    def test_matching_ticker_increases_score(self):
        base = self._base_classificacao()
        perfil = PerfilInvestidor(perfil_risco="moderado", sensibilidade_negativo=0.5)

        without_ticker = calculate_relevance_score(base, perfil=perfil, carteira_tickers=[])
        with_ticker = calculate_relevance_score(base, perfil=perfil, carteira_tickers=[TEST_TICKER])

        self.assertGreater(with_ticker["score_final"], without_ticker["score_final"])

    def test_matching_sector_increases_score(self):
        base = self._base_classificacao(setor="energia")
        perfil = PerfilInvestidor(perfil_risco="moderado", sensibilidade_negativo=0.5, setores_preferidos=["energia"])

        result = calculate_relevance_score(base, perfil=perfil)
        self.assertTrue(result["motivos"]["setor_match"])

    def test_higher_source_reliability_increases_score(self):
        base = self._base_classificacao()
        perfil = PerfilInvestidor(perfil_risco="moderado", sensibilidade_negativo=0.5)

        low = calculate_relevance_score(base, perfil=perfil, fonte_confiabilidade=0.0)
        high = calculate_relevance_score(base, perfil=perfil, fonte_confiabilidade=1.0)

        self.assertGreater(high["score_final"], low["score_final"])

    def test_negative_sentiment_high_sensitivity_scores_higher(self):
        base = self._base_classificacao(sentimento="negativo")
        perfil_low = PerfilInvestidor(perfil_risco="moderado", sensibilidade_negativo=0.2)
        perfil_high = PerfilInvestidor(perfil_risco="moderado", sensibilidade_negativo=0.9)

        low = calculate_relevance_score(base, perfil=perfil_low)
        high = calculate_relevance_score(base, perfil=perfil_high)

        self.assertGreater(high["score_final"], low["score_final"])

    def test_risk_profiles_produce_different_scores(self):
        base = self._base_classificacao(sentimento="positivo")

        conservador = calculate_relevance_score(base, perfil=PerfilInvestidor(perfil_risco="conservador", sensibilidade_negativo=0.5))
        agressivo = calculate_relevance_score(base, perfil=PerfilInvestidor(perfil_risco="agressivo", sensibilidade_negativo=0.5))

        self.assertNotEqual(conservador["score_final"], agressivo["score_final"])

    def test_missing_classification_fields_use_safe_defaults(self):
        result = calculate_relevance_score({})
        self.assertIn("score_final", result)
        self.assertIn("prioridade", result)
        self.assertGreaterEqual(result["score_final"], 0.0)

    def test_score_is_clamped_to_maximum(self):
        base = self._base_classificacao(
            sentimento="negativo", impacto="alto", urgencia="alta",
            relevancia_llm=1.0, setor="energia", tickers_relacionados=[TEST_TICKER],
        )
        perfil = PerfilInvestidor(perfil_risco="moderado", sensibilidade_negativo=1.0, setores_preferidos=["energia"])
        result = calculate_relevance_score(base, perfil=perfil, carteira_tickers=[TEST_TICKER], fonte_confiabilidade=1.0)

        self.assertLessEqual(result["score_final"], 100.0)

    # --- is_priority_at_least ---

    def test_priority_comparison_valid_combinations(self):
        self.assertTrue(is_priority_at_least("critica", "alta"))
        self.assertTrue(is_priority_at_least("alta", "media"))
        self.assertTrue(is_priority_at_least("media", "baixa"))
        self.assertTrue(is_priority_at_least("baixa", "baixa"))

    def test_invalid_priority_returns_false(self):
        self.assertFalse(is_priority_at_least("invalida", "alta"))
        self.assertFalse(is_priority_at_least("alta", "invalida"))


# =============================================================================
# InteracaoServiceTests - atualização do perfil do investidor
# =============================================================================


class InteracaoServiceTests(TestCase):
    """Testes de update_profile_from_interactions."""

    def setUp(self):
        self.user = User.objects.create_user(username=f"inter_{uuid4().hex[:6]}", password="secret")

    def test_no_profile_returns_none(self):
        PerfilInvestidor.objects.filter(usuario=self.user).delete()
        result = update_profile_from_interactions(self.user)
        self.assertIsNone(result)

    def test_no_interactions_keeps_profile_unchanged(self):
        perfil = PerfilInvestidor.objects.get(usuario=self.user)
        original = perfil.sensibilidade_negativo
        update_profile_from_interactions(self.user)
        perfil.refresh_from_db()
        self.assertEqual(perfil.sensibilidade_negativo, original)

    def test_opening_negative_news_increases_sensitivity(self):
        perfil = PerfilInvestidor.objects.get(usuario=self.user)
        perfil.sensibilidade_negativo = 0.5
        perfil.save(update_fields=["sensibilidade_negativo"])

        noticia = Noticia.objects.create(link="https://example.test/neg1", titulo="Queda")
        NoticiaClassificacao.objects.create(noticia=noticia, sentimento="negativo", impacto="alto", urgencia="alta")
        InteracaoNoticia.objects.create(usuario=self.user, noticia=noticia, abriu=True)

        update_profile_from_interactions(self.user)
        perfil.refresh_from_db()
        self.assertGreater(perfil.sensibilidade_negativo, 0.5)

    def test_ignoring_negative_news_reduces_sensitivity(self):
        perfil = PerfilInvestidor.objects.get(usuario=self.user)
        perfil.sensibilidade_negativo = 0.8
        perfil.save(update_fields=["sensibilidade_negativo"])

        noticia = Noticia.objects.create(link="https://example.test/neg2", titulo="Crise")
        NoticiaClassificacao.objects.create(noticia=noticia, sentimento="negativo", impacto="alto", urgencia="alta")
        InteracaoNoticia.objects.create(usuario=self.user, noticia=noticia, ignorou=True)

        update_profile_from_interactions(self.user)
        perfil.refresh_from_db()
        self.assertLess(perfil.sensibilidade_negativo, 0.8)

    def test_small_delta_does_not_persist(self):
        perfil = PerfilInvestidor.objects.get(usuario=self.user)
        perfil.sensibilidade_negativo = 0.55
        perfil.save(update_fields=["sensibilidade_negativo"])

        noticia = Noticia.objects.create(link="https://example.test/neg3", titulo="Leve")
        NoticiaClassificacao.objects.create(noticia=noticia, sentimento="negativo", impacto="baixo", urgencia="baixa")
        InteracaoNoticia.objects.create(usuario=self.user, noticia=noticia, abriu=True, ignorou=True)

        update_profile_from_interactions(self.user)
        perfil.refresh_from_db()
        self.assertEqual(perfil.sensibilidade_negativo, 0.55)

    def test_preferred_sectors_are_updated(self):
        perfil = PerfilInvestidor.objects.get(usuario=self.user)
        perfil.setores_preferidos = []
        perfil.save(update_fields=["setores_preferidos"])

        for i in range(3):
            n = Noticia.objects.create(link=f"https://example.test/s{i}", titulo=f"Not {i}")
            NoticiaClassificacao.objects.create(noticia=n, sentimento="neutro", impacto="medio", setor="tecnologia")
            InteracaoNoticia.objects.create(usuario=self.user, noticia=n, abriu=True)

        update_profile_from_interactions(self.user)
        perfil.refresh_from_db()
        self.assertIn("tecnologia", perfil.setores_preferidos)

    def test_existing_sectors_are_preserved(self):
        perfil = PerfilInvestidor.objects.get(usuario=self.user)
        perfil.setores_preferidos = ["saude"]
        perfil.save(update_fields=["setores_preferidos"])

        n = Noticia.objects.create(link="https://example.test/s99", titulo="Tech")
        NoticiaClassificacao.objects.create(noticia=n, sentimento="neutro", impacto="medio", setor="tecnologia")
        InteracaoNoticia.objects.create(usuario=self.user, noticia=n, abriu=True)

        update_profile_from_interactions(self.user)
        perfil.refresh_from_db()
        self.assertEqual(perfil.setores_preferidos, ["saude"])


# =============================================================================
# NoticiaServiceHelperTests - funções auxiliares críticas
# =============================================================================


class NoticiaServiceHelperTests(TestCase):
    """Testes das funções auxiliares de noticia_service."""

    # --- _normalize_link ---

    def test_normalize_link_removes_utm_params(self):
        raw = "https://example.test/article?utm_source=rss&utm_medium=feed&id=123"
        result = noticia_service._normalize_link(raw)
        self.assertNotIn("utm_source", result)
        self.assertNotIn("utm_medium", result)
        self.assertIn("id=123", result)

    def test_normalize_link_removes_fbclid(self):
        raw = "https://example.test/article?fbclid=abc123&id=1"
        result = noticia_service._normalize_link(raw)
        self.assertNotIn("fbclid", result)
        self.assertIn("id=1", result)

    def test_normalize_link_without_query_unchanged(self):
        raw = "https://example.test/article"
        result = noticia_service._normalize_link(raw)
        self.assertEqual(result, "https://example.test/article")

    def test_normalize_link_empty_string(self):
        self.assertEqual(noticia_service._normalize_link(""), "")

    def test_normalize_link_invalid_url(self):
        raw = "not-a-url"
        result = noticia_service._normalize_link(raw)
        self.assertEqual(result, raw)

    # --- _parse_date ---

    def test_parse_date_returns_datetime(self):
        now = datetime.now(timezone.utc)
        result = noticia_service._parse_date({"published": now})
        self.assertEqual(result, now)

    def test_parse_date_falls_back_when_invalid(self):
        result = noticia_service._parse_date({"published": "invalid"})
        self.assertIsInstance(result, datetime)

    # --- seen_article ---

    def test_seen_article_returns_true(self):
        Noticia.objects.create(link="https://example.test/seen1", titulo="Seen")
        self.assertTrue(noticia_service.seen_article("https://example.test/seen1"))

    def test_seen_article_returns_false(self):
        self.assertFalse(noticia_service.seen_article("https://example.test/notseen"))


# =============================================================================
# FormTests - validação e persistência
# =============================================================================


class FormTests(TestCase):
    """Testes de PerfilInvestidorForm e RegistroForm."""

    def setUp(self):
        self.user = User.objects.create_user(username=f"form_{uuid4().hex[:6]}", password="secret")
        self.perfil = PerfilInvestidor.objects.get(usuario=self.user)

    def test_perfil_form_save_with_sectors(self):
        form = PerfilInvestidorForm(
            data={
                "perfil_risco": "agressivo",
                "horizonte": "longo",
                "frequencia_alertas": "diario",
                "alerta_min_prioridade": "alta",
                "sensibilidade_negativo": "0.7",
                "notificacao_email": True,
                "notificacao_push": False,
                "notificacao_dashboard": True,
                "setores_preferidos_text": "energia, bancos",
            },
            instance=self.perfil,
        )
        self.assertTrue(form.is_valid(), form.errors)
        perfil = form.save()
        self.assertEqual(perfil.perfil_risco, "agressivo")
        self.assertIn("energia", perfil.setores_preferidos)
        self.assertIn("bancos", perfil.setores_preferidos)

    def _perfil_form_data(self, **overrides):
        data = {
            "perfil_risco": "moderado",
            "horizonte": "medio",
            "frequencia_alertas": "imediato",
            "alerta_min_prioridade": "media",
            "sensibilidade_negativo": "0.5",
            "notificacao_email": True,
            "notificacao_push": True,
            "notificacao_dashboard": True,
            "setores_preferidos_text": "",
        }
        data.update(overrides)
        return data

    def test_perfil_form_parse_comma_separated_sectors(self):
        form = PerfilInvestidorForm(
            data=self._perfil_form_data(setores_preferidos_text="a, b, c"),
            instance=self.perfil,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["setores_preferidos_text"], ["a", "b", "c"])

    def test_perfil_form_parse_semicolon_separated_sectors(self):
        form = PerfilInvestidorForm(
            data=self._perfil_form_data(setores_preferidos_text="x; y; z"),
            instance=self.perfil,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["setores_preferidos_text"], ["x", "y", "z"])

    def test_perfil_form_empty_sectors(self):
        form = PerfilInvestidorForm(
            data=self._perfil_form_data(setores_preferidos_text=""),
            instance=self.perfil,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["setores_preferidos_text"], [])

    def test_register_form_valid(self):
        form = RegistroForm(data={
            "username": f"newuser_{uuid4().hex[:6]}",
            "email": "test@example.test",
            "password1": "TestPass123!",
            "password2": "TestPass123!",
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_register_form_password_mismatch(self):
        form = RegistroForm(data={
            "username": f"newuser_{uuid4().hex[:6]}",
            "email": "test@example.test",
            "password1": "TestPass123!",
            "password2": "DifferentPass!",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)


# =============================================================================
# ParserTests - parsers e factory
# =============================================================================


class ParserTests(TestCase):
    """Testes de parsers/factory e RSSParser."""

    def test_create_rss_parser(self):
        parser = create_parser("https://example.test/feed.xml")
        self.assertIsInstance(parser, RSSParser)

    def test_create_html_parser(self):
        parser = create_parser("https://example.test/page.html")
        self.assertIsInstance(parser, CustomParser)

    def test_create_htm_parser(self):
        parser = create_parser("https://example.test/page.htm")
        self.assertIsInstance(parser, CustomParser)

    def test_clean_html_removes_tags(self):
        result = RSSParser._clean_html("<p>Hello <b>world</b></p>")
        self.assertNotIn("<p>", result)
        self.assertNotIn("<b>", result)
        self.assertIn("Hello", result)
        self.assertIn("world", result)

    def test_clean_html_decodes_entities(self):
        result = RSSParser._clean_html("Pre&ccedil;o &amp; valor")
        self.assertIn("Preço", result)
        self.assertIn("&", result)


# =============================================================================
# UsuarioServiceTests - watchlist
# =============================================================================


class UsuarioServiceTests(TestCase):
    """Testes de usuario_service."""

    def setUp(self):
        self.user = User.objects.create_user(username=f"watch_{uuid4().hex[:6]}", password="secret")

    def test_returns_only_portfolio_assets(self):
        asset = Ativo.objects.create(ticker="ITUB4", nome="Itau", source="b3")
        Ativo.objects.create(ticker="MGLU3", nome="Magazine Luiza", source="b3")
        carteira, _ = Carteira.objects.get_or_create(usuario=self.user)
        carteira.ativos.add(asset)

        result = list_watchlist_assets()
        tickers = [a["code"] for a in result]
        self.assertIn("ITUB4", tickers)
        self.assertNotIn("MGLU3", tickers)

    def test_returns_empty_when_no_portfolios(self):
        Ativo.objects.create(ticker="BBAS3", nome="Banco do Brasil", source="b3")
        result = list_watchlist_assets()
        self.assertEqual(result, [])


# =============================================================================
# SignalTests - auto-criação de perfil
# =============================================================================


class SignalTests(TestCase):
    """Teste de signals.py."""

    def test_user_creation_creates_investor_profile(self):
        user = User.objects.create_user(username=f"sig_{uuid4().hex[:6]}", password="secret")
        self.assertTrue(PerfilInvestidor.objects.filter(usuario=user).exists())


# =============================================================================
# ViewEdgeCaseTests - comportamentos observáveis das views
# =============================================================================


class ViewEdgeCaseTests(TestCase):
    """Edge cases das views não cobertos pelos WebViewsTests."""

    def setUp(self):
        self.username = f"edge_{uuid4().hex[:8]}"
        self.user = User.objects.create_user(username=self.username, password="secret")
        self.client.login(username=self.username, password="secret")
        self.asset, _ = Ativo.objects.get_or_create(ticker=TEST_TICKER, defaults={"nome": "Petrobras", "source": "b3"})

    def _create_scored_news(self, sentimento="negativo", impacto="alto", prioridade="alta", ticker=TEST_TICKER):
        noticia = Noticia.objects.create(
            link=f"https://example.test/news_{uuid4().hex[:6]}",
            titulo=f"Noticia {sentimento}",
            relevancia_binaria=True,
        )
        NoticiaClassificacao.objects.create(
            noticia=noticia,
            sentimento=sentimento,
            impacto=impacto,
            urgencia="alta",
            setor="energia",
            tickers_relacionados=[ticker],
        )
        NoticiaScore.objects.create(
            noticia=noticia,
            usuario=self.user,
            score_final=0.8,
            prioridade=prioridade,
        )
        return noticia

    def test_lista_noticias_filters_by_sentiment(self):
        self._create_scored_news(sentimento="negativo")
        self._create_scored_news(sentimento="positivo")

        response = self.client.get(reverse("lista_noticias"), {"sentimento": "negativo"})
        self.assertEqual(response.status_code, 200)

    def test_lista_noticias_filters_by_ticker(self):
        noticia = self._create_scored_news()
        response = self.client.get(reverse("lista_noticias"), {"ticker": TEST_TICKER})
        self.assertEqual(response.status_code, 200)

    def test_detalhe_noticia_shows_score(self):
        noticia = self._create_scored_news()
        response = self.client.get(reverse("detalhe_noticia", args=[noticia.id]))
        self.assertEqual(response.status_code, 200)

    def test_detalhe_noticia_without_score(self):
        noticia = Noticia.objects.create(
            link=f"https://example.test/noscore_{uuid4().hex[:6]}",
            titulo="Sem score",
        )
        response = self.client.get(reverse("detalhe_noticia", args=[noticia.id]))
        self.assertEqual(response.status_code, 200)

    def test_meus_alertas_filters_by_priority(self):
        noticia = self._create_scored_news(prioridade="alta")
        Alerta.objects.create(usuario=self.user, noticia=noticia)
        alerta = Alerta.objects.get(usuario=self.user, noticia=noticia)
        alerta.ativos.add(self.asset)

        response = self.client.get(reverse("meus_alertas"), {"prioridade": "alta"})
        self.assertEqual(response.status_code, 200)

    def test_record_interaction_invalid_action_returns_400(self):
        noticia = Noticia.objects.create(link="https://example.test/inv", titulo="Test")
        response = self.client.post(
            reverse("record_interaction"),
            {"noticia_id": noticia.id, "acao": "invalida"},
        )
        self.assertEqual(response.status_code, 400)

    def test_record_interaction_noticia_not_found_returns_404(self):
        response = self.client.post(
            reverse("record_interaction"),
            {"noticia_id": 999999, "acao": "abriu"},
        )
        self.assertEqual(response.status_code, 404)

    def test_record_interaction_get_returns_405(self):
        response = self.client.get(reverse("record_interaction"))
        self.assertEqual(response.status_code, 405)

    def test_dashboard_no_asset_found_for_term(self):
        response = self.client.post(reverse("dashboard"), {"asset_term": "INEXISTENTE"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nenhum ativo encontrado")

    def test_dashboard_update_profile(self):
        perfil = PerfilInvestidor.objects.get(usuario=self.user)
        response = self.client.post(reverse("dashboard"), {
            "update_profile": "1",
            "perfil_risco": "agressivo",
            "horizonte": "longo",
            "frequencia_alertas": "diario",
            "alerta_min_prioridade": "alta",
            "sensibilidade_negativo": "0.8",
            "setores_preferidos_text": "tecnologia",
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        perfil.refresh_from_db()
        self.assertEqual(perfil.perfil_risco, "agressivo")

    def test_dashboard_remove_nonexistent_asset(self):
        response = self.client.post(reverse("dashboard"), {"remove_asset_id": "999999"}, follow=True)
        self.assertEqual(response.status_code, 200)
