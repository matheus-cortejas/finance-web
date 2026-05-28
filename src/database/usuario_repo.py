from __future__ import annotations

from database.acao_repo import add_to_watchlist, get_watchlist_assets


def add_asset_to_watchlist(asset_id: int, tag: str | None = None) -> None:
    add_to_watchlist(asset_id, tag)


def list_watchlist_assets():
    return get_watchlist_assets()
