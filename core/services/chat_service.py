from __future__ import annotations

import logging

from setup.settings import OPENAI_API_KEY, OPENAI_CHAT_MAX_TOKENS, OPENAI_CHAT_TEMPERATURE, OPENAI_MODEL
from core.llm.openai_client import client


logger = logging.getLogger("services.chat_service")

CHAT_SYSTEM_PROMPT = (
    "Você é o assistente do Monitor Financeiro. Responda em português, com tom objetivo,"
    " amigável e técnico. Ajude o usuário a entender carteira, alertas, scheduler, notícias"
    " e o fluxo do aplicativo."
)


def _fallback_reply(user_message: str) -> str:
    lowered = user_message.lower()
    if any(keyword in lowered for keyword in ["carteira", "ativo", "ação", "acoes", "ações"]):
        return (
            "Você pode adicionar ativos pela dashboard, acompanhar os alertas recentes e usar a home"
            " como ponto de entrada rápido."
        )
    if any(keyword in lowered for keyword in ["alerta", "notícia", "noticia", "feed", "rss"]):
        return (
            "Os alertas surgem quando o scheduler encontra notícias relevantes para os ativos da sua carteira."
        )
    if any(keyword in lowered for keyword in ["scheduler", "monitor", "runserver"]):
        return (
            "O monitor faz a coleta inicial e o scheduler mantém a varredura recorrente dos feeds."
        )
    return (
        "A integração com OpenAI não está disponível agora, mas posso explicar carteira, alertas,"
        " scheduler, autenticação e o fluxo da aplicação."
    )


def generate_chat_reply(history: list[dict[str, str]], user_message: str) -> dict[str, str]:
    if not user_message.strip():
        return {"reply": "Digite uma mensagem para continuar.", "provider": "validation"}

    if not client or not OPENAI_API_KEY:
        logger.info("Chat usando fallback local: openai=%s api_key=%s", "presente" if client else "ausente", "presente" if OPENAI_API_KEY else "ausente")
        return {"reply": _fallback_reply(user_message), "provider": "fallback"}

    conversation = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    for item in history[-12:]:
        role = item.get("role")
        content = item.get("content", "").strip()
        if role in {"user", "assistant"} and content:
            conversation.append({"role": role, "content": content})
    conversation.append({"role": "user", "content": user_message.strip()})

    try:
        logger.info("Chamando OpenAI para chat: mensagens=%d modelo=%s", len(conversation), OPENAI_MODEL)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=conversation,
            temperature=OPENAI_CHAT_TEMPERATURE,
            max_tokens=OPENAI_CHAT_MAX_TOKENS,
        )
        reply = (response.choices[0].message.content or "").strip()
        if not reply:
            reply = _fallback_reply(user_message)
        return {"reply": reply, "provider": "openai"}
    except Exception:
        logger.exception("Falha ao gerar resposta de chat; usando fallback local")
        return {"reply": _fallback_reply(user_message), "provider": "fallback"}