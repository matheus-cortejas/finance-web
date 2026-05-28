from __future__ import annotations

import argparse
import logging
import os

from config.logger import configure_logging
from config.settings import (
    DEFAULT_B3_CSV,
    DEFAULT_RSS_PATH,
    MONITOR_INTERVAL_SECONDS,
    OPENAI_API_KEY,
    OPENAI_MAX_TOKENS,
    OPENAI_MODEL,
    OPENAI_USE_CONTENT,
)
from database.acao_repo import add_to_watchlist, find_assets_by_term, list_assets
from database.connection import init_db
from services.acao_service import fetch_sp500_and_store, parse_b3_csv
from scheduler.app import run_scheduler
from scheduler.jobs import collect_initial_news


logger = logging.getLogger(__name__)


def load_feeds(path):
    feed_path = os.path.expanduser(os.fspath(path))
    if not os.path.exists(feed_path):
        return []
    with open(feed_path, "r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def interactive_register():
    print("Digite códigos ou nomes de ativos, separados por vírgula:")
    line = input("> ").strip()
    if not line:
        logger.info("Nenhum ativo informado na etapa interativa")
        return
    terms = [term.strip() for term in line.split(",") if term.strip()]
    logger.info("Processando %d termo(s) da etapa interativa", len(terms))
    for term in terms:
        matches = find_assets_by_term(term)
        if not matches:
            logger.warning("Ativo não encontrado na base: %s", term)
            continue
        if len(matches) == 1:
            asset = matches[0]
            add_to_watchlist(asset["id"])
            logger.info("Ativo adicionado à watchlist: %s - %s", asset["code"], asset["name"])
            continue
        logger.info('Múltiplas correspondências para "%s"', term)
        for index, match in enumerate(matches):
            logger.info("%d. %s - %s", index + 1, match["code"], match["name"])
        choice = input("Escolha número (ou Enter para pular): ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(matches):
                asset = matches[idx]
                add_to_watchlist(asset["id"])
                logger.info("Ativo adicionado à watchlist: %s - %s", asset["code"], asset["name"])


def main():
    configure_logging()
    logger.info("Inicializando monitor de notícias")
    logger.info(
        "Configuração OpenAI: model=%s key=%s content=%s max_tokens=%d",
        OPENAI_MODEL,
        "presente" if OPENAI_API_KEY else "ausente",
        OPENAI_USE_CONTENT,
        OPENAI_MAX_TOKENS,
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--b3-csv", default=str(DEFAULT_B3_CSV))
    parser.add_argument("--rss", default=str(DEFAULT_RSS_PATH))
    args = parser.parse_args()

    init_db()
    logger.info("Populando base S&P500")
    try:
        inserted = fetch_sp500_and_store()
        logger.info("S&P500 inseridos: %d", inserted)
    except Exception:
        logger.exception("Falha ao buscar S&P500")

    logger.info("Carregando CSV B3")
    try:
        inserted = parse_b3_csv(args.b3_csv)
        logger.info("B3 inseridos: %d", inserted)
    except Exception:
        logger.exception("Falha ao parsear CSV B3")

    logger.info("Base total de ativos: %d", len(list_assets()))
    interactive_register()

    feeds = load_feeds(args.rss)
    if not feeds:
        logger.warning("Nenhum feed RSS encontrado; saindo")
        return

    logger.info("Fazendo verificação inicial (último 1 dia) em %d feed(s)", len(feeds))
    reports = collect_initial_news(feeds)
    logger.info("Verificação inicial concluída com %d alerta(s)", len(reports))
    for report in reports:
        logger.info(
            "[ALERTA INICIAL] %s - %s -> %s | %s",
            report["published"],
            report["title"],
            report["matches"],
            report["link"],
        )

    logger.info("Scheduler ativo: verificação a cada %d minutos", MONITOR_INTERVAL_SECONDS // 60)
    try:
        run_scheduler(feeds)
    except KeyboardInterrupt:
        logger.info("Finalizando monitor por interrupção do usuário")
