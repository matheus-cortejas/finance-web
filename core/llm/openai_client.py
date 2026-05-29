from __future__ import annotations

import json
import logging
import re

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None

from setup.settings import (
    OPENAI_API_KEY,
    OPENAI_MAX_TOKENS,
    OPENAI_MODEL,
    OPENAI_SUMMARY_MAX_TOKENS,
    OPENAI_SUMMARY_TEMPERATURE,
    OPENAI_USE_CONTENT,
)


logger = logging.getLogger("llm.openai_client")


client = OpenAI(api_key=OPENAI_API_KEY) if OpenAI and OPENAI_API_KEY else None

STRUCTURED_CLASSIFICATION_SCHEMA = {
    "type": "object",
    "required": [
        "sentimento",
        "impacto",
        "urgencia",
        "setor",
        "tipo_evento",
        "tickers_relacionados",
        "relevancia_llm",
    ],
    "properties": {
        "sentimento": {"type": "string", "enum": ["positivo", "neutro", "negativo"]},
        "impacto": {"type": "string", "enum": ["alto", "medio", "baixo"]},
        "urgencia": {"type": "string", "enum": ["alta", "media", "baixa"]},
        "setor": {"type": "string"},
        "tipo_evento": {
            "type": "string",
            "enum": ["resultado", "fato_relevante", "fusao_aquisicao", "regulatorio", "macro", "mercado", "analise", "outro"],
        },
        "tickers_relacionados": {"type": "array", "items": {"type": "string"}},
        "relevancia_llm": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

_SENTIMENTO_VALUES = {"positivo", "neutro", "negativo"}
_IMPACTO_VALUES = {"alto", "medio", "baixo"}
_URGENCIA_VALUES = {"alta", "media", "baixa"}
_TIPO_EVENTO_VALUES = {
    "resultado",
    "fato_relevante",
    "fusao_aquisicao",
    "regulatorio",
    "macro",
    "mercado",
    "analise",
    "outro",
}

_NEGATIVE_HINTS = {
    "queda",
    "prejuizo",
    "perda",
    "fraude",
    "investigacao",
    "processo",
    "rebaixamento",
    "downgrade",
    "suspensao",
    "multa",
}
_POSITIVE_HINTS = {
    "alta",
    "lucro",
    "recorde",
    "crescimento",
    "melhora",
    "upgrade",
    "recomendacao",
    "guidance",
    "expansao",
}
_HIGH_IMPACT_HINTS = {
    "fusao",
    "aquisição",
    "aquisicao",
    "oferta",
    "ipo",
    "resultado",
    "balanco",
    "regulatorio",
    "fato relevante",
    "fato_relevante",
}
_URGENT_HINTS = {
    "urgente",
    "imediato",
    "suspensao",
    "fraude",
    "alerta",
}

_SECTOR_HINTS = {
    "financeiro": ["banco", "financeir", "segur", "credito", "cartao", "corretora"],
    "energia": ["energia", "eletric", "petroleo", "oleo", "gas", "combustivel"],
    "mineracao": ["mineracao", "minera", "siderurgia", "aco", "ferro", "minerio"],
    "papel_e_celulose": ["celulose", "papel"],
    "varejo": ["varejo", "varej", "loja", "e-commerce", "shopping"],
    "agro": ["agro", "agr", "soja", "milho", "acucar", "etanol", "fertiliz"],
    "saude": ["saude", "hospital", "farmac", "medic", "clinica", "biotech"],
    "tecnologia": ["tecnologia", "software", "digital", "nuvem", "dados"],
    "telecom": ["telecom", "telefon", "5g", "fibra", "internet"],
    "construcao": ["construcao", "construtora", "incorporacao", "imobiliario", "imovel"],
    "transporte": ["logistica", "transporte", "aeroporto", "rodovia", "ferrovia", "porto"],
}


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


def _normalize_tickers(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        items = re.split(r"[\s,;]+", value)
    elif isinstance(value, list):
        items = value
    else:
        items = []
    tickers = []
    for item in items:
        if not item:
            continue
        if isinstance(item, dict):
            item = item.get("code") or item.get("ticker") or ""
        if not isinstance(item, str):
            item = str(item)
        cleaned = item.strip().upper()
        if cleaned and cleaned not in tickers:
            tickers.append(cleaned)
    return tickers


def _normalize_classification_payload(payload: dict | None) -> dict:
    payload = payload or {}
    sentimento = (payload.get("sentimento") or "").strip().lower()
    if sentimento not in _SENTIMENTO_VALUES:
        sentimento = "neutro"

    impacto = (payload.get("impacto") or "").strip().lower()
    if impacto not in _IMPACTO_VALUES:
        impacto = "medio"

    urgencia = (payload.get("urgencia") or "").strip().lower()
    if urgencia not in _URGENCIA_VALUES:
        urgencia = "media"

    setor = (payload.get("setor") or "").strip()
    tipo_evento = (payload.get("tipo_evento") or "").strip().lower()
    if tipo_evento not in _TIPO_EVENTO_VALUES:
        tipo_evento = "outro"

    tickers_relacionados = _normalize_tickers(payload.get("tickers_relacionados"))

    relevancia_llm = payload.get("relevancia_llm")
    try:
        relevancia_llm = float(relevancia_llm)
    except (TypeError, ValueError):
        relevancia_llm = 0.0
    relevancia_llm = max(0.0, min(1.0, relevancia_llm))

    return {
        "sentimento": sentimento,
        "impacto": impacto,
        "urgencia": urgencia,
        "setor": setor,
        "tipo_evento": tipo_evento,
        "tickers_relacionados": tickers_relacionados,
        "relevancia_llm": relevancia_llm,
    }


def _infer_setor(text: str) -> str:
    for setor, hints in _SECTOR_HINTS.items():
        if any(hint in text for hint in hints):
            return setor
    return ""


def _infer_tipo_evento(text: str) -> str:
    if re.search(r"\b(fato relevante|fato_relevante|fr)\b", text):
        return "fato_relevante"
    if re.search(r"\b(resultado|balanco|trimestre|trimestral|lucro|receita|ebitda|guidance)\b", text):
        return "resultado"
    if re.search(r"\b(fusao|aquisicao|aquisição|cisao|incorporacao|joint venture|opa)\b", text):
        return "fusao_aquisicao"
    if re.search(r"\b(cvm|cade|bacen|anac|anp|regulatorio|regulacao|licenca|multa)\b", text):
        return "regulatorio"
    if re.search(r"\b(ipca|selic|copom|inflacao|pib|dolar|cambio|macro)\b", text):
        return "macro"
    if re.search(r"\b(recomendacao|analise|rating|upgrade|downgrade|preco alvo|price target)\b", text):
        return "analise"
    if re.search(r"\b(ibovespa|bolsa|mercado|volume|liquidez)\b", text):
        return "mercado"
    return "outro"

def _build_token_kwargs(token_limit: int | None) -> dict:
    try:
        limit = int(token_limit) if token_limit is not None else None
    except Exception:
        limit = None
    if not limit:
        return {}
    if OPENAI_MODEL and "gpt-5" in OPENAI_MODEL:
        return {"max_completion_tokens": limit}
    return {"max_tokens": limit}

def _build_temperature_kwargs(temp_value: float | None) -> dict:
    try:
        t = float(temp_value) if temp_value is not None else None
    except Exception:
        return {}
    if t is None:
        return {}
    # Some gpt-5 family models currently reject non-default temperature (e.g. 0.0).
    # To avoid 400 errors, do not pass a non-default temperature for gpt-5 models.
    if OPENAI_MODEL and "gpt-5" in OPENAI_MODEL:
        # only pass temperature if it equals 1.0 (the allowed default); otherwise skip it
        if t == 1.0:
            return {"temperature": t}
        return {}
    return {"temperature": t}

def _extract_related_tickers(text: str, assets: list) -> list[str]:
    if not text:
        return []
    text_lower = text.lower()
    tickers = []
    for asset in assets or []:
        code = (asset.get("code") or "").strip().upper()
        name = (asset.get("name") or "").strip().lower()
        if not code:
            continue
        if re.search(r"(?<!\w)" + re.escape(code.lower()) + r"(?!\w)", text_lower):
            if code not in tickers:
                tickers.append(code)
            continue
        if name and name in text_lower and code not in tickers:
            tickers.append(code)
    return tickers


def _heuristic_classification(title: str, description: str, content: str, assets: list) -> dict:
    text = f"{title}\n{description}\n{content}".lower()
    sentimento = "neutro"
    if any(word in text for word in _NEGATIVE_HINTS):
        sentimento = "negativo"
    elif any(word in text for word in _POSITIVE_HINTS):
        sentimento = "positivo"

    impacto = "medio"
    if any(word in text for word in _HIGH_IMPACT_HINTS):
        impacto = "alto"

    urgencia = "media"
    if any(word in text for word in _URGENT_HINTS):
        urgencia = "alta"

    tipo_evento = _infer_tipo_evento(text)
    setor = _infer_setor(text)

    tickers_relacionados = _extract_related_tickers(text, assets)
    relevancia_llm = 0.7 if tickers_relacionados else 0.3

    result = {
        "sentimento": sentimento,
        "impacto": impacto,
        "urgencia": urgencia,
        "setor": setor,
        "tipo_evento": tipo_evento,
        "tickers_relacionados": tickers_relacionados,
        "relevancia_llm": relevancia_llm,
        "provider": "fallback",
        "status": "fallback",
    }
    return _heuristic_override_classification(title, description, content, result)


def classify_article_heuristic(title: str, description: str, content: str, assets: list | None = None) -> dict:
    assets = assets or []
    result = _heuristic_classification(title, description, content, assets)
    result["provider"] = "heuristic"
    result["status"] = "heuristic"
    return result


def _heuristic_relevance(title: str, description: str, content: str, assets: list) -> dict:
    text = f"{title}\n{description}\n{content}".lower()
    matched = []

    for asset in assets:
        code = (asset.get("code") or "").lower()
        name = (asset.get("name") or "").lower()
        if code and code in text:
            matched.append(asset.get("code"))
            continue
        if name and name in text:
            matched.append(asset.get("code"))

    matched = [code for code in matched if code]
    return {
        "relevant": bool(matched),
        "matched": matched,
        "reason": "Heuristic fallback: OpenAI unavailable",
    }


def _fallback_summary(title: str, description: str, content: str) -> str:
    text = (description or content or title or "").strip()
    if not text:
        return ""

    cleaned = re.sub(r"\s+", " ", text)
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    summary = " ".join(sentence for sentence in sentences[:2] if sentence).strip()
    if summary:
        return summary
    return cleaned[:280].strip()


def judge_article_relevance(title: str, description: str, content: str, assets: list) -> dict:
    logger.info(
        "Avaliando artigo com IA: title=%r assets=%d use_content=%s model=%s max_tokens=%d",
        title,
        len(assets),
        bool(OPENAI_USE_CONTENT and content),
        OPENAI_MODEL,
        OPENAI_MAX_TOKENS,
    )
    if not client or not OPENAI_API_KEY:
        logger.info(
            "Fallback heuristico sem chamada OpenAI: openai=%s api_key=%s",
            "presente" if OpenAI else "ausente",
            "presente" if OPENAI_API_KEY else "ausente",
        )
        return _heuristic_relevance(title, description, content, assets)

    asset_list = ", ".join([f"{asset.get('code')} ({asset.get('name')})" for asset in assets])
    use_content = OPENAI_USE_CONTENT and content
    text = f"Title: {title}\n\nDescription: {description}\n"
    if use_content:
        text += f"\nContent: {content}\n"

    system = (
        "You are a concise classifier. Decide whether the article (title/description/content) is relevant to any of the assets provided. "
        "Return a JSON object with keys: relevant (true/false), matched (list of asset codes), and reason (one short sentence)."
    )
    user = f"Assets: {asset_list}\n\nArticle:\n{text}\n\nAnswer only valid JSON."

    try:
        logger.info("Chamando OpenAI chat.completions")
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            n=1,
            **_build_token_kwargs(OPENAI_MAX_TOKENS),
            **_build_temperature_kwargs(0.0),
        )
        choice = response.choices[0]
        output = (choice.message.content or "").strip()
        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage")

        logger.info("Resposta bruta da IA: %s", output)
        if usage:
            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)
            total_tokens = getattr(usage, "total_tokens", None)
            if isinstance(usage, dict):
                prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
                completion_tokens = usage.get("completion_tokens", completion_tokens)
                total_tokens = usage.get("total_tokens", total_tokens)
            logger.info(
                "Uso da IA: prompt_tokens=%s completion_tokens=%s total_tokens=%s",
                prompt_tokens,
                completion_tokens,
                total_tokens,
            )
        finish_reason = getattr(choice, "finish_reason", None)
        logger.info("Finalização da IA: model=%s finish_reason=%s", OPENAI_MODEL, finish_reason)
        try:
            parsed = json.loads(output)
            return {"relevant": bool(parsed.get("relevant")), "matched": parsed.get("matched") or [], "reason": parsed.get("reason", "")}
        except Exception:
            matched = []
            lowered = output.lower()
            for asset in assets:
                code = asset.get("code", "")
                name = asset.get("name", "")
                if code.lower() in lowered or (name and name.lower() in lowered):
                    matched.append(code)
            logger.info("Resposta da IA nao era JSON; inferindo matched por texto bruto")
            return {"relevant": bool(matched), "matched": matched, "reason": output}
    except Exception as exc:
        fallback = _heuristic_relevance(title, description, content, assets)
        fallback["reason"] = f"Heuristic fallback after OpenAI error: {exc}"
        logger.exception("Erro ao chamar OpenAI; usando fallback heuristico")
        return fallback


def summarize_article(title: str, description: str, content: str) -> dict:
    text = (description or content or title or "").strip()
    if not text:
        return {"summary": "", "status": "vazio", "provider": "fallback"}

    if not client or not OPENAI_API_KEY:
        return {
            "summary": _fallback_summary(title, description, content),
            "status": "fallback",
            "provider": "fallback",
        }

    system = (
        "You are a concise assistant. Summarize the article in Portuguese using 2-3 sentences. "
        "Return only the summary text, no bullet points, no markdown."
    )
    user = f"Title: {title}\nDescription: {description}\nContent: {content}\n\nSummary:"

    try:
        logger.info("Chamando OpenAI para resumo de noticia")
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            **_build_token_kwargs(OPENAI_SUMMARY_MAX_TOKENS),
            **_build_temperature_kwargs(OPENAI_SUMMARY_TEMPERATURE),
        )
        summary = (response.choices[0].message.content or "").strip()
        if not summary:
            summary = _fallback_summary(title, description, content)
            return {"summary": summary, "status": "fallback", "provider": "fallback"}
        return {"summary": summary, "status": "ok", "provider": "openai"}
    except Exception:
        logger.exception("Erro ao gerar resumo; usando fallback")
        return {
            "summary": _fallback_summary(title, description, content),
            "status": "fallback",
            "provider": "fallback",
        }

def _heuristic_override_classification(title: str, description: str, content: str, normalized: dict) -> dict:
    text = f"{title}\n{description}\n{content}".lower()
    if not normalized.get("setor"):
        normalized["setor"] = _infer_setor(text)
    if normalized.get("tipo_evento") in {"", "outro"}:
        normalized["tipo_evento"] = _infer_tipo_evento(text)
    # explicit negative words
    if re.search(r'\b(preju[ií]zo|prejuizo|fraude|multa|suspens[ãa]o|rebaixamento|downgrade|perda)\b', text):
        normalized["sentimento"] = "negativo"
        normalized["impacto"] = normalized.get("impacto", "medio")
        return normalized

    # negative percent patterns: "queda ... 32%" or "redução de 32%"
    m = re.search(r'\b(queda|redu[cç][aã]o|reducao|perda)\b(?:.{0,60}?)(\d{1,3}(?:[.,]\d+)?)\s*%', text)
    if m:
        try:
            pct = float(m.group(2).replace(",", "."))
        except Exception:
            pct = None
        normalized["sentimento"] = "negativo"
        if pct is not None and pct >= 20:
            normalized["impacto"] = "alto"
        else:
            normalized["impacto"] = normalized.get("impacto", "medio")
        return normalized

    # 'lucro' mentioned together with 'queda' -> negative
    if "lucro" in text and re.search(r'\b(queda|redu[cç][aã]o|reducao|perda)\b', text):
        normalized["sentimento"] = "negativo"
        return normalized

    # positive percent patterns
    m2 = re.search(r'\b(aumentou|alta|subiu|crescimento|cresceu|aumento|recorde)\b(?:.{0,60}?)(\d{1,3}(?:[.,]\d+)?)?\s*%', text)
    if m2:
        normalized["sentimento"] = "positivo"
        if m2.group(2):
            try:
                pct = float(m2.group(2).replace(",", "."))
                if pct >= 20:
                    normalized["impacto"] = "alto"
            except Exception:
                pass
        return normalized

    return normalized

def classify_article(title: str, description: str, content: str, assets: list | None = None) -> dict:
    assets = assets or []
    text = f"Title: {title}\nDescription: {description}\nContent: {content}".strip()
    if not text:
        return {
            **_normalize_classification_payload({}),
            "provider": "fallback",
            "status": "error",
        }

    if not client or not OPENAI_API_KEY:
        return _heuristic_classification(title, description, content, assets)

    asset_list = ", ".join([f"{asset.get('code')} ({asset.get('name')})" for asset in assets if asset.get("code")])
    system = (
        "You are a financial news classifier. Output only valid JSON matching this schema: "
        "{sentimento: positivo|neutro|negativo, impacto: alto|medio|baixo, urgencia: alta|media|baixa, "
        "setor: string, tipo_evento: resultado|fato_relevante|fusao_aquisicao|regulatorio|macro|mercado|analise|outro, "
        "tickers_relacionados: string[], relevancia_llm: number (0-1)}."
    )
    user = f"Assets: {asset_list}\n\nArticle:\n{text}\n\nAnswer only JSON."

    try:
        logger.info("Chamando OpenAI para classificacao estruturada")
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            n=1,
            **_build_token_kwargs(OPENAI_MAX_TOKENS),
            **_build_temperature_kwargs(0.0),
        )
        output = (response.choices[0].message.content or "").strip()
        payload = _extract_json_object(output)
        normalized = _normalize_classification_payload(payload)
        normalized = _heuristic_override_classification(title, description, content, normalized)
        if assets:
            tickers = normalized.get("tickers_relacionados")
            if not tickers:
                tickers = _extract_related_tickers(text, assets)
            if not tickers:
                tickers = [asset.get("code") for asset in assets if asset.get("code")]
            normalized["tickers_relacionados"] = _normalize_tickers(tickers)
        normalized["provider"] = "openai"
        normalized["status"] = "ok"
        logger.info("Classificacao estruturada concluida: sentimento=%s impacto=%s urgencia=%s", normalized["sentimento"], normalized["impacto"], normalized["urgencia"])
        return normalized
    except Exception as exc:
        logger.exception("Erro ao classificar noticia; usando fallback")
        fallback = _heuristic_classification(title, description, content, assets)
        fallback["status"] = "fallback"
        fallback["provider"] = "fallback"
        fallback["relevancia_llm"] = fallback.get("relevancia_llm", 0.0)
        fallback["setor"] = fallback.get("setor", "")
        fallback["tipo_evento"] = fallback.get("tipo_evento", "outro")
        fallback["sentimento"] = fallback.get("sentimento", "neutro")
        fallback["impacto"] = fallback.get("impacto", "medio")
        fallback["urgencia"] = fallback.get("urgencia", "media")
        logger.info("Classificacao fallback aplicada: erro=%s", exc)
        return fallback