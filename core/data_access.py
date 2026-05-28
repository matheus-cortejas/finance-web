from __future__ import annotations

from datetime import datetime, timedelta, timezone

from django.contrib.auth.models import User

from core.models import Alerta, Ativo, Carteira, Noticia


DEFAULT_USERNAME = "default"


def _ensure_default_carteira() -> Carteira:
    user, _ = User.objects.get_or_create(username=DEFAULT_USERNAME)
    user.set_unusable_password()
    user.save(update_fields=["password"])
    carteira, _ = Carteira.objects.get_or_create(usuario=user)
    return carteira


def _asset_to_dict(asset: Ativo) -> dict:
    return {
        "id": asset.id,
        "source": asset.source,
        "code": asset.ticker,
        "name": asset.nome,
    }


def asset_exists(code: str | None = None, name: str | None = None):
    queryset = Ativo.objects.all()
    if code:
        asset = queryset.filter(ticker__iexact=code).first()
        return _asset_to_dict(asset) if asset else None
    if name:
        asset = queryset.filter(nome__iexact=name).first()
        return _asset_to_dict(asset) if asset else None
    return None


def insert_asset(source: str, code: str, name: str) -> None:
    Ativo.objects.get_or_create(
        ticker=code,
        defaults={"nome": name, "source": source},
    )


def list_assets() -> list[dict]:
    return [_asset_to_dict(asset) for asset in Ativo.objects.all()]


def find_assets_by_term(term: str) -> list[dict]:
    queryset = Ativo.objects.filter(ticker__icontains=term) | Ativo.objects.filter(nome__icontains=term)
    return [_asset_to_dict(asset) for asset in queryset.distinct()]


def add_to_watchlist(asset_id: int, tag: str | None = None) -> None:
    carteira = _ensure_default_carteira()
    asset = Ativo.objects.filter(id=asset_id).first()
    if asset:
        carteira.ativos.add(asset)


def get_watchlist_assets() -> list[dict]:
    return [_asset_to_dict(asset) for asset in Ativo.objects.filter(carteiras__isnull=False).distinct()]


def count_assets_by_source(source: str) -> int:
    return Ativo.objects.filter(source=source).count()


def seen_article(link: str) -> bool:
    return Noticia.objects.filter(link=link).exists()


def mark_article_seen(link: str, published_ts: int | None = None) -> None:
    published_at = None
    if published_ts is not None:
        published_at = datetime.fromtimestamp(published_ts, tz=timezone.utc)
    Noticia.objects.get_or_create(
        link=link,
        defaults={
            "titulo": "",
            "descricao": "",
            "publicado_em": published_at,
            "feed_url": "",
            "impacto": "pendente",
        },
    )


def save_article(
    link: str,
    title: str,
    description: str,
    published_ts: int | None = None,
    feed_url: str | None = None,
) -> int | None:
    published_at = None
    if published_ts is not None:
        published_at = datetime.fromtimestamp(published_ts, tz=timezone.utc)

    article, _ = Noticia.objects.update_or_create(
        link=link,
        defaults={
            "titulo": title,
            "descricao": description,
            "publicado_em": published_at,
            "feed_url": feed_url or "",
            "impacto": "pendente",
        },
    )
    return article.id


def link_article_match(article_id: int, asset_id: int) -> None:
    article = Noticia.objects.filter(id=article_id).first()
    asset = Ativo.objects.filter(id=asset_id).first()
    if not article or not asset:
        return

    user = _ensure_default_carteira().usuario
    Alerta.objects.get_or_create(usuario=user, noticia=article, ativo=asset)


def purge_articles_older_than(cutoff_ts: int) -> int:
    cutoff = datetime.fromtimestamp(cutoff_ts, tz=timezone.utc)
    queryset = Noticia.objects.filter(publicado_em__isnull=False, publicado_em__lt=cutoff)
    deleted_count = queryset.count()
    queryset.delete()
    return deleted_count


def purge_articles_older_than_days(days: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return purge_articles_older_than(int(cutoff.timestamp()))