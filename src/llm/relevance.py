from __future__ import annotations

from llm.openai_client import judge_article_relevance


_CACHE: dict[str, dict] = {}


def _cache_key(title: str, description: str, content: str, assets: list) -> str:
    asset_key = ";".join(sorted(f"{asset.get('code')}:{asset.get('name')}" for asset in assets))
    return f"{title}\n{description}\n{content}\n{asset_key}".lower().strip()


def is_relevant(title: str, description: str = "", content: str = "", assets: list | None = None) -> dict:
    assets = assets or []
    key = _cache_key(title, description, content, assets)
    if key in _CACHE:
        return _CACHE[key]

    result = judge_article_relevance(title, description, content, assets)
    _CACHE[key] = result
    return result
