from database.acao_repo import (
    add_to_watchlist,
    asset_exists,
    count_assets_by_source,
    find_assets_by_term,
    get_watchlist_assets,
    insert_asset,
    list_assets,
)
from database.connection import get_connection as get_conn, init_db
from database.noticia_repo import link_article_match, mark_article_seen, save_article, seen_article
