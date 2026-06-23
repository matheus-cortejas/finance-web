# fase4/llm_classifier.py
from __future__ import annotations

import logging
from typing import Optional, Dict


import json
import hashlib
import re
import os
import time

import yaml

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger("fase4.llm_classifier")

try:
    from .cache import prompt_hash, get_cached_decision, set_cached_decision, cache_enabled, cache_ttl
except Exception:
    # fail gracefully if the cache module is unavailable
    def prompt_hash(p):
        return None

    def get_cached_decision(p):
        return None

    def set_cached_decision(p, d, ttl=None):
        return None

    def cache_enabled():
        return False

    def cache_ttl():
        return 86400

def _extract_json_object(text: str) -> dict | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None

def _extract_first_binary(text: str) -> int | None:
    if not text:
        return None
    # Try exact match
    t = text.strip()
    if t in ("0", "1"):
        return int(t)

    # Try JSON payload
    parsed = _extract_json_object(text)
    if isinstance(parsed, dict):
        for key in ("decision", "decisao", "result", "resultado", "value", "relevancia", "relevancia_binaria", "relevante"):
            if key in parsed:
                v = parsed.get(key)
                if isinstance(v, bool):
                    return 1 if v else 0
                try:
                    vi = int(v)
                    if vi in (0, 1):
                        return vi
                except Exception:
                    pass

    # Find first standalone 0/1 in text
    m = re.search(r"(?<!\d)([01])(?!\d)", text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None

    # Interpret yes/no words
    low = text.lower()
    if any(k in low for k in ("relevante", "sim", "yes", "true", "verdadeiro")):
        return 1
    if any(k in low for k in ("irrelevante", "nao", "não", "no", "false", "falso")):
        return 0

    return None

def _extract_decision_and_confidence(text: str) -> tuple[int | None, float | None]:
    if not text:
        return (None, None)

    # Try explicit pattern like '1|0.90' anywhere in the text
    m = re.search(r"(?<!\d)([01])\s*\|\s*([01](?:\.\d+)?)(?!\d)", text)
    if m:
        try:
            decision = int(m.group(1))
            conf = float(m.group(2))
            # clamp
            if conf < 0.0:
                conf = 0.0
            if conf > 1.0:
                conf = 1.0
            return (decision, conf)
        except Exception:
            pass

    # Try JSON payload for decision + confidence
    parsed = _extract_json_object(text)
    if isinstance(parsed, dict):
        # common keys
        for dkey in ("decision", "decisao", "result", "resultado", "value", "relevancia", "relevancia_binaria", "relevante"):
            if dkey in parsed:
                try:
                    d = parsed.get(dkey)
                    if isinstance(d, bool):
                        decision = 1 if d else 0
                    else:
                        decision = int(d)
                except Exception:
                    decision = None
                # try confidence keys
                for ckey in ("confidence", "confianca", "confianca_fase4", "score"):
                    if ckey in parsed:
                        try:
                            conf = float(parsed.get(ckey))
                            return (decision, conf)
                        except Exception:
                            return (decision, None)
                return (decision, None)

    # Fallback: try to extract first binary decision only
    decision = _extract_first_binary(text)
    return (decision, None)

def _build_token_kwargs(token_limit: int | None, openai_model: str | None = None) -> dict:
    try:
        limit = int(token_limit) if token_limit is not None else None
    except Exception:
        limit = None
    if not limit:
        return {}
    if openai_model and "gpt-5" in openai_model:
        return {"max_completion_tokens": limit}
    return {"max_tokens": limit}

def _build_temperature_kwargs(temp_value: float | None, openai_model: str | None = None) -> dict:
    try:
        t = float(temp_value) if temp_value is not None else None
    except Exception:
        return {}
    if t is None:
        return {}
    if openai_model and "gpt-5" in openai_model:
        if t == 1.0:
            return {"temperature": t}
        return {}
    return {"temperature": t}

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


def _build_cache_hash(provider: str, model: str, prompt: str) -> str:
    payload = {"provider": provider, "model": model, "prompt": prompt}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


class LLMClassifier:
    def __init__(self, config: Optional[dict] = None, model: Optional[str] = None):
        """
        Parâmetros:
            config: dicionário completo de configuração (carregado pelo orquestrador)
            model: nome do modelo (opcional, sobrescreve o que vier na config)
        """
        # Extrai configuração da fase4
        if config is None:
            fase_cfg = {}
        else:
            fase_cfg = config.get("fase4", {})

        llm_cfg = fase_cfg.get("llm", {})
        cache_cfg = fase_cfg.get("cache", {})

        # --- Atributos principais ---
        self.provider = llm_cfg.get("provider", "openai")
        self.model = model or llm_cfg.get("model", "gpt-4o-mini")
        self.temperature = llm_cfg.get("temperature", 0.0)
        self.max_tokens = llm_cfg.get("max_tokens", 300)
        self.timeout_seconds = llm_cfg.get("timeout_seconds", 30)
        self.retry_attempts = llm_cfg.get("retry_attempts", 1)
        self.cache_enabled = cache_cfg.get("enabled", True)
        self.cache_ttl = cache_cfg.get("ttl_seconds", 86400)

        # Inicializa cliente OpenAI (se houver chave)
        self.client = None
        api_key = llm_cfg.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if self.provider == "openai" and api_key and OpenAI:
            try:
                self.client = OpenAI(api_key=api_key, timeout=self.timeout_seconds)
                logger.info("Cliente OpenAI criado com sucesso na Fase 4")
            except Exception as e:
                logger.exception("Falha ao criar cliente OpenAI")
                self.client = None
        else:
            logger.warning("Nenhuma chave API fornecida – usará fallback")

        # Fallback result (valor padrão caso LLM falhe)
        self.fallback_result = int(fase_cfg.get("fallback_resultado", 1))

        # Cache manager (opcional)
        self.cache_manager = None
        if self.cache_enabled:
            try:
                from ..fase1_global_filter.cache_manager import get_cache_manager
                self.cache_manager = get_cache_manager()
            except Exception:
                logger.exception("Cache manager não disponível")
                self.cache_enabled = False

    def classificar(self, prompt: str, timeout_seconds: int = 30) -> int:
        """Envia prompt para a LLM e normaliza a resposta para 0/1.

        Retorna `fallback_result` em caso de erro ou resposta inválida.
        """
        logger.info("LLMClassifier.classificar model=%s", self.model)
        if not prompt:
            logger.warning("Prompt vazio; retornando fallback=%s", self.fallback_result)
            # set last_confidence to 1.0 for deterministic fallback
            self.last_confidence = 1.0
            return int(self.fallback_result)

        # Cache lookup
        try:
            if cache_enabled():
                cached = get_cached_decision(prompt)
                if cached is not None:
                    h = prompt_hash(prompt)
                    logger.info("CACHE_HIT fase4 hash=%s decision=%s", h, cached)
                    # cached may be dict; attempt to set last_confidence if present
                    try:
                        if isinstance(cached, dict) and "confidence" in cached:
                            self.last_confidence = float(cached.get("confidence"))
                        else:
                            self.last_confidence = None
                    except Exception:
                        self.last_confidence = None
                    return int(cached)
                else:
                    h = prompt_hash(prompt)
                    logger.info("CACHE_MISS fase4 hash=%s", h)
        except Exception:
            # ignore cache errors
            pass

        if not self.client:
            logger.info("OpenAI client indisponível; retornando fallback=%s", self.fallback_result)
            self.last_confidence = 1.0
            return int(self.fallback_result)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                n=1,
                **_build_token_kwargs(self.max_tokens, self.model),
                **_build_temperature_kwargs(self.temperature, self.model),
            )

            # extract content from several possible response shapes
            output = ""
            choices = None
            if hasattr(response, "choices"):
                choices = getattr(response, "choices")
            elif isinstance(response, dict):
                choices = response.get("choices")

            if choices and isinstance(choices, (list, tuple)) and choices:
                choice = choices[0]
                # choice can be object or dict
                if isinstance(choice, dict):
                    msg = choice.get("message")
                    if isinstance(msg, dict):
                        output = msg.get("content") or msg.get("text") or choice.get("text") or ""
                    else:
                        output = (msg or choice.get("text") or "")
                else:
                    msg = getattr(choice, "message", None)
                    if msg is not None:
                        output = getattr(msg, "content", "") or getattr(choice, "text", "") or ""
                    else:
                        output = getattr(choice, "text", "") or ""

            # Final fallback for older shapes
            if not output and isinstance(response, dict):
                try:
                    output = response["choices"][0]["message"]["content"]
                except Exception:
                    output = output

            output = (output or "").strip()
            logger.info("Resposta bruta da LLM (truncada): %s", output[:200])

            # extract decision and confidence if provided
            dec, conf = _extract_decision_and_confidence(output)
            if dec is None:
                logger.warning("Não foi possível normalizar resposta LLM; usando fallback=%s", self.fallback_result)
                # still attempt to cache the fallback decision
                try:
                    if cache_enabled():
                        set_cached_decision(prompt, int(self.fallback_result), ttl=cache_ttl())
                except Exception:
                    pass
                self.last_confidence = 1.0
                return int(self.fallback_result)

            # set last_confidence (may be None)
            try:
                self.last_confidence = float(conf) if conf is not None else None
            except Exception:
                self.last_confidence = None

            # cache positive result (store decision; also include confidence when possible)
            try:
                if cache_enabled():
                    if self.last_confidence is not None:
                        set_cached_decision(prompt, int(dec), ttl=cache_ttl())
                        # also store confidence by writing payload via set_cached_decision (which stores dict)
                        mgr = None
                    else:
                        set_cached_decision(prompt, int(dec), ttl=cache_ttl())
            except Exception:
                pass

            return int(dec)

        except Exception as exc:
            logger.exception("Erro ao chamar LLM; retornando fallback=%s", self.fallback_result)
            return int(self.fallback_result)
