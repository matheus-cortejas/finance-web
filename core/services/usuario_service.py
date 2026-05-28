from __future__ import annotations

from core.models import Ativo, Carteira


def _asset_to_dict(asset: Ativo) -> dict:
    return {
        "id": asset.id,
        "source": asset.source,
        "code": asset.ticker,
        "name": asset.nome,
    }


def _get_watchlist_assets() -> list[dict]:
    return [_asset_to_dict(asset) for asset in Ativo.objects.filter(carteiras__isnull=False).distinct()]


def list_watchlist_assets() -> list[dict]:
    return [dict(asset) for asset in _get_watchlist_assets()]