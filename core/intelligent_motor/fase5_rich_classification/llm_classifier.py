import json
import hashlib
import logging
import re
import os
import time
from typing import Optional

import yaml

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from .exceptions import LLMError

logger = logging.getLogger(__name__)


def _build_cache_hash(
    provider: str,
    model: str,
    prompt: str,
) -> str:
    payload = {
        "provider": provider,
        "model": model,
        "prompt": prompt,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


class LLMClassifier:
    def __init__(self, config: Optional[dict] = None):
        # Extrai configuração da fase5 (subseção "llm")
        if config is None:
            llm_cfg = {}
        else:
            fase5_cfg = config.get("fase5", {})
            llm_cfg = fase5_cfg.get("llm", {})
            cache_cfg = fase5_cfg.get("cache", {})         

        self.provider = llm_cfg.get("provider", "openai")
        self.model = llm_cfg.get("model", "gpt-4o-mini")
        self.temperature = llm_cfg.get("temperature", 0.0)
        self.max_tokens = llm_cfg.get("max_tokens", 300)
        self.timeout = llm_cfg.get("timeout_seconds", 15)
        self.retry_attempts = llm_cfg.get("retry_attempts", 1)

        # Configurações de cache
        self.cache_enabled = cache_cfg.get("enabled", True)
        self.cache_ttl = cache_cfg.get("ttl_seconds", 86400)
        self.cache_manager = None

        api_key = llm_cfg.get("api_key") or os.environ.get("OPENAI_API_KEY")
        self.client = None
        if self.provider == "openai" and api_key:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key, timeout=self.timeout)
            logger.info("Cliente OpenAI criado na Fase 5")
        else:
            logger.warning("Nenhuma chave API fornecida para a Fase 5")

        # Inicializa cache manager (usando o singleton global do motor)
        if self.cache_enabled:
            try:
                # Use o caminho correto para o cache_manager centralizado
                from ..fase1_global_filter.cache_manager import get_cache_manager
                self.cache_manager = get_cache_manager()  # singleton já inicializado pelo orquestrador
                logger.info("Cache manager da Fase 5 inicializado")
            except Exception as e:
                logger.exception("Cache manager não disponível – cache desabilitado")
                self.cache_enabled = False

        # --- Lógica de carga da chave da API (prioridade: YAML > setup.settings > variável de ambiente) ---
        if self.client is not None:
            return  # cliente já fornecido externamente

        # 1. Tenta carregar do YAML (campo api_key)
        api_key = llm_cfg.get("api_key")

        # 3. Fallback: variável de ambiente
        if not api_key:
            api_key = os.environ.get("OPENAI_API_KEY")

        # Modelo e max_tokens também podem vir do YAML (já carregados acima) ou de setup.settings / env
        openai_model = llm_cfg.get("model")
        if not openai_model:
            openai_model = os.environ.get("OPENAI_MODEL")
        if openai_model:
            self.model = openai_model

        openai_max_tokens = llm_cfg.get("max_tokens")
        if not openai_max_tokens:
            try:
                openai_max_tokens = int(os.environ.get("OPENAI_MAX_TOKENS", "0"))
            except ValueError:
                pass
        if openai_max_tokens:
            self.max_tokens = openai_max_tokens

        # Cria cliente OpenAI se a chave estiver disponível
        if self.provider == "openai" and not self.client and api_key:
            try:
                if OpenAI is None:
                    raise ImportError("openai package not installed")
                self.client = OpenAI(api_key=api_key, timeout=self.timeout_seconds)
                logger.info("Cliente OpenAI criado com sucesso na Fase 5")
            except Exception as e:
                logger.exception(f"Falha ao criar cliente OpenAI: {e}")
                self.client = None
        else:
            if not api_key:
                logger.warning("Nenhuma chave OpenAI fornecida (nem no YAML, nem em setup.settings, nem em variável de ambiente) – a Fase 5 usará apenas fallback heurístico")
            else:
                logger.info(f"Provider '{self.provider}' configurado – cliente será criado sob demanda")

    def classificar(self, prompt: str) -> dict:
        """Recebe um prompt e retorna um dicionário (JSON) com a análise."""
        if not prompt:
            raise LLMError("Prompt vazio")

        cache_hash = _build_cache_hash(
            self.provider,
            self.model,
            prompt,
        )
        cache_key = f"fase5:result:{cache_hash}"

        # Tenta cache
        cached = self._read_cache(cache_key)
        if cached is not None:
            logger.info(
                "CACHE_HIT",
                extra={
                    "fase": "fase5",
                    "hash": cache_hash,
                    "model": self.model,
                },
            )
            return cached

        logger.info(
            "CACHE_MISS",
            extra={
                "fase": "fase5",
                "hash": cache_hash,
                "model": self.model,
            },
        )

        last_exception = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                start = time.time()
                response_text = self._call_provider(prompt)
                elapsed_ms = int((time.time() - start) * 1000)

                payload = self._parse_response(response_text)

                self._write_cache(cache_key, payload)

                logger.info(
                    "LLM_CLASSIFICATION",
                    extra={
                        "fase": "fase5",
                        "hash": cache_hash,
                        "model": self.model,
                        "tempo_ms": elapsed_ms,
                        "tentativa": attempt,
                    },
                )
                return payload

            except LLMError as exc:
                last_exception = exc
                if attempt < self.retry_attempts:
                    logger.warning(
                        "FASE5_RETRY tentativa=%s erro=%s",
                        attempt,
                        str(exc),
                    )
            except Exception as exc:
                last_exception = exc
                logger.exception("FASE5_UNEXPECTED_ERROR")
                break

        raise LLMError(
            f"Falha após {self.retry_attempts} tentativa(s): {last_exception}"
        )

    def _call_provider(self, prompt: str) -> str:
        """Chama a API da OpenAI (ou outro provider) e retorna a resposta bruta."""
        if not self.client:
            raise LLMError("Cliente LLM não disponível – verifique a chave da API no YAML ou variável de ambiente.")

        if self.provider != "openai":
            raise LLMError(f"Provider não suportado: {self.provider}")

        try:
            #print(f"DEBUG: chamando API com model={self.model}, max_tokens={self.max_tokens}")            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_completion_tokens=self.max_tokens,
                n=1,
            )
            #print("DEBUG: API retornou com sucesso")    
            content = response.choices[0].message.content.strip()
            #print(f"DEBUG: conteúdo retornado pela API: {content}")
            if not content:
                raise LLMError("Resposta vazia da LLM.")
            return content
        except Exception as exc:
            print(f"DEBUG: exceção na chamada API: {exc}")        
            raise LLMError(str(exc))

    def _parse_response(self, response_text: str) -> dict:
        """Extrai um dicionário da resposta da LLM (JSON esperado)."""
        if not response_text:
            raise LLMError("Resposta vazia da LLM.")

        # Tenta parse direto
        try:
            return json.loads(response_text)
        except Exception:
            pass

        # Tenta extrair de bloco markdown
        markdown_match = re.search(
            r"```(?:json)?\s*(\{[\s\S]*?\})\s*```",
            response_text,
        )
        if markdown_match:
            try:
                return json.loads(markdown_match.group(1))
            except Exception:
                pass

        # Tenta encontrar primeiro JSON na string
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except Exception:
                pass

        raise LLMError("Não foi possível extrair JSON válido da resposta da LLM.")

    def _read_cache(self, key: str):
        if not self.cache_enabled or not self.cache_manager:
            return None
        try:
            return self.cache_manager.get(key)
        except Exception:
            logger.exception("Erro ao consultar cache.")
            return None

    def _write_cache(self, key: str, value: dict):
        if not self.cache_enabled or not self.cache_manager:
            return
        try:
            self.cache_manager.set(key, value, ttl=self.cache_ttl)
        except Exception:
            logger.exception("Erro ao gravar cache.")