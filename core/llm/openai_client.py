from __future__ import annotations

import json
import logging

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None

from setup.settings import OPENAI_API_KEY, OPENAI_MAX_TOKENS, OPENAI_MODEL, OPENAI_USE_CONTENT


logger = logging.getLogger("llm.openai_client")


client = OpenAI(api_key=OPENAI_API_KEY) if OpenAI and OPENAI_API_KEY else None


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
            temperature=0.0,
            max_tokens=OPENAI_MAX_TOKENS,
            n=1,
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