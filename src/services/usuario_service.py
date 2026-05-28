from __future__ import annotations

from database.acao_repo import add_to_watchlist, find_assets_by_term, get_watchlist_assets


def register_assets_by_terms(terms: list[str]) -> list[dict]:
    added = []
    for term in terms:
        matches = find_assets_by_term(term)
        if len(matches) == 1:
            asset = matches[0]
            add_to_watchlist(asset["id"])
            added.append(dict(asset))
    return added


def list_watchlist_assets() -> list[dict]:
    return [dict(asset) for asset in get_watchlist_assets()]
