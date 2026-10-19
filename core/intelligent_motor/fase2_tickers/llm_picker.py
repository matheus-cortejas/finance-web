"""A4 — LLM como primeiro nível da associação notícia → ticker.

Em vez de decidir só por similaridade de embeddings, um LLM recebe a notícia e
uma lista curta de candidatos (ticker + descrição) e devolve apenas os tickers
materialmente afetados. A ideia do TCC é rodar isso **localmente** (custo zero,
privacidade) e **escalar para a nuvem** (GPT-4o-mini) só quando o modelo local
falha ou não responde.

O provedor local é acessado por um endpoint **OpenAI-compatível** (Ollama,
llama.cpp server, vLLM): basta apontar ``base_url`` (ex.:
``http://localhost:11434/v1``). Assim não há dependência nova no projeto.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("fase4.llm_classifier")

DEFAULT_MODEL_LOCAL = "llama3.1:8b"
DEFAULT_MODEL_OPENAI = "gpt-4o-mini"
DEFAULT_BASE_URL_LOCAL = "http://localhost:11434/v1"

_TICKER_RE = re.compile(r"\b[A-Z]{4,5}\d\b")
_NENHUM = {"nenhum", "nenhuma", "none", "n/a", "na", "vazio", "sem", "[]"}


def build_prompt(
    noticia_texto: str,
    candidatos: Sequence[Tuple[str, str]],
    max_chars: int = 1500,
) -> str:
    """Prompt determinístico pedindo JSON com os tickers afetados."""
    lista = "\n".join(
        f"- {ticker}: {(descricao or ticker)[:160]}"
        for ticker, descricao in candidatos
    )
    return (
        "Você é um analista do mercado financeiro. Recebe uma notícia e uma "
        "lista de ativos candidatos.\n"
        "Responda SOMENTE com os tickers cuja empresa é mencionada ou é "
        "afetada de forma MATERIAL e não especulativa pela notícia.\n"
        "NÃO inclua empresas apenas do mesmo setor.\n"
        'Formato: {"tickers": ["XXXX3", ...]} — use {"tickers": []} se nenhum.\n'
        "Não escreva nada além do JSON.\n\n"
        f"NOTÍCIA:\n{(noticia_texto or '')[:max_chars]}\n\n"
        f"CANDIDATOS:\n{lista}\n"
    )


def extrair_tickers(texto: str, universo: Sequence[str]) -> Optional[List[str]]:
    """Extrai a lista de tickers da resposta do LLM.

    Tolerante a JSON, blocos markdown e texto solto. Devolve ``None`` quando a
    resposta é vazia/não interpretável (para o chamador escalar/fallback).
    """
    if texto is None:
        return None
    universo_map = {t.upper(): t for t in universo}
    bruto = texto.strip()
    if not bruto:
        return None

    if bruto.lower() in _NENHUM:
        return []

    def _filtrar(itens: Sequence[Any]) -> List[str]:
        resultado: List[str] = []
        for item in itens:
            chave = str(item).strip().upper()
            if chave in universo_map and chave not in resultado:
                resultado.append(chave)
        return resultado

    payload = None
    try:
        payload = json.loads(bruto)
    except Exception:
        match = re.search(r"[\[{].*[\]}]", bruto, re.DOTALL)
        if match:
            try:
                payload = json.loads(match.group(0))
            except Exception:
                payload = None

    if isinstance(payload, list):
        return _filtrar(payload)
    if isinstance(payload, dict):
        for chave in ("tickers", "ativos", "relacionados", "empresas", "result"):
            valor = payload.get(chave)
            if isinstance(valor, list):
                return _filtrar(valor)
            if isinstance(valor, str):
                return _filtrar(_TICKER_RE.findall(valor))
        # fallback: procura tickers em qualquer campo do dict
        return _filtrar(_TICKER_RE.findall(json.dumps(payload, ensure_ascii=False)))

    # Texto solto: procura tickers do universo; se achar, usa.
    achados = _filtrar(_TICKER_RE.findall(bruto))
    if achados:
        return achados
    if any(p in bruto.lower() for p in _NENHUM):
        return []
    return None


class LLMPicker:
    """Decide os tickers com um LLM (local, escalando para a nuvem)."""

    def __init__(self, cfg: Optional[dict] = None):
        cfg = cfg or {}
        self.provider = str(cfg.get("provider", "local")).strip().lower()
        self.model = cfg.get("model") or (
            DEFAULT_MODEL_OPENAI if self.provider == "openai" else DEFAULT_MODEL_LOCAL
        )
        self.base_url = cfg.get("base_url") or (
            None if self.provider == "openai" else DEFAULT_BASE_URL_LOCAL
        )
        self.api_key = cfg.get("api_key") or os.environ.get("OPENAI_API_KEY")
        self.timeout = float(cfg.get("timeout_seconds", 30))
        self.max_tokens = int(cfg.get("max_tokens", 300))
        self.temperature = float(cfg.get("temperature", 0.0))
        self.escalar_para = cfg.get("escalar_para") or {}
        self.client = self._build_client(self.provider, self.base_url)

    # --------------------------------------------------------------- client
    def _build_client(self, provider: str, base_url: Optional[str]):
        try:
            from openai import OpenAI
        except Exception:
            return None
        try:
            if provider == "openai":
                if not self.api_key:
                    return None
                return OpenAI(api_key=self.api_key, timeout=self.timeout)
            return OpenAI(
                base_url=base_url or DEFAULT_BASE_URL_LOCAL,
                api_key=self.api_key or "local",
                timeout=self.timeout,
            )
        except Exception:
            logger.exception("Falha ao criar cliente LLM da Fase 2")
            return None

    def _cliente_escalada(self):
        cfg = self.escalar_para or {}
        if not cfg:
            return None
        provider = str(cfg.get("provider", "openai")).strip().lower()
        base_url = cfg.get("base_url") or (
            None if provider == "openai" else DEFAULT_BASE_URL_LOCAL
        )
        modelo = cfg.get("model") or (
            DEFAULT_MODEL_OPENAI if provider == "openai" else DEFAULT_MODEL_LOCAL
        )
        cliente = self._build_client(provider, base_url)
        if cliente is None:
            return None
        return cliente, modelo, provider

    # ----------------------------------------------------------------- call
    def _chamar(self, cliente, modelo: str, prompt: str) -> Optional[str]:
        try:
            resposta = cliente.chat.completions.create(
                model=modelo,
                messages=[{"role": "user", "content": prompt}],
                n=1,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            escolhas = getattr(resposta, "choices", None)
            if not escolhas:
                return None
            mensagem = getattr(escolhas[0], "message", None)
            conteudo = getattr(mensagem, "content", None) if mensagem else None
            if conteudo:
                return conteudo
            return getattr(escolhas[0], "text", None)
        except Exception:
            logger.exception("Erro ao chamar o LLM da Fase 2")
            return None

    def escolher(
        self,
        noticia_texto: str,
        candidatos: Sequence[Tuple[str, str]],
    ) -> Tuple[Optional[List[str]], str]:
        """Retorna ``(tickers, provider_usado)``.

        ``tickers`` é ``None`` quando nenhum provedor conseguiu responder de
        forma interpretável — o chamador mantém o resultado da similaridade.
        """
        universo = [ticker for ticker, _ in candidatos]
        if not universo:
            return [], "vazio"

        prompt = build_prompt(noticia_texto, candidatos)

        tentativas = [(self.client, self.model, self.provider)]
        secundario = self._cliente_escalada()
        if secundario is not None:
            tentativas.append(secundario)

        for cliente, modelo, nome in tentativas:
            if cliente is None:
                continue
            conteudo = self._chamar(cliente, modelo, prompt)
            if conteudo is None:
                continue
            tickers = extrair_tickers(conteudo, universo)
            if tickers is not None:
                return tickers, nome
        return None, "fallback"


__all__ = [
    "DEFAULT_BASE_URL_LOCAL",
    "DEFAULT_MODEL_LOCAL",
    "DEFAULT_MODEL_OPENAI",
    "LLMPicker",
    "build_prompt",
    "extrair_tickers",
]
