from __future__ import annotations

from datetime import datetime, timezone

from database.connection import get_connection


def seen_article(link: str) -> bool:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT 1 FROM seen_articles WHERE link=? LIMIT 1", (link,))
    found = cursor.fetchone() is not None
    connection.close()
    return found


def mark_article_seen(link: str, published_ts: int | None = None) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO seen_articles (link, published_ts) VALUES (?,?)", (link, published_ts))
        connection.commit()
    finally:
        connection.close()


def save_article(link: str, title: str, description: str, published_ts: int | None = None, feed_url: str | None = None) -> int | None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO articles (link, title, description, published_ts, feed_url) VALUES (?,?,?,?,?)",
        (link, title, description, published_ts, feed_url),
    )
    connection.commit()
    cursor.execute("SELECT id FROM articles WHERE link=?", (link,))
    row = cursor.fetchone()
    article_id = row["id"] if row else None
    connection.close()
    return article_id


def link_article_match(article_id: int, asset_id: int) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("INSERT INTO article_matches (article_id, asset_id) VALUES (?,?)", (article_id, asset_id))
    connection.commit()
    connection.close()


def purge_articles_older_than(cutoff_ts: int) -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT id, link FROM articles WHERE published_ts IS NOT NULL AND published_ts < ?", (cutoff_ts,))
    rows = cursor.fetchall()
    if not rows:
        connection.close()
        return 0

    article_ids = [row["id"] for row in rows]
    links = [row["link"] for row in rows if row["link"]]
    placeholders = ",".join("?" for _ in article_ids)

    cursor.execute(f"DELETE FROM article_matches WHERE article_id IN ({placeholders})", article_ids)
    cursor.execute(f"DELETE FROM articles WHERE id IN ({placeholders})", article_ids)
    if links:
        link_placeholders = ",".join("?" for _ in links)
        cursor.execute(f"DELETE FROM seen_articles WHERE link IN ({link_placeholders})", links)

    connection.commit()
    connection.close()
    return len(article_ids)


def purge_articles_older_than_days(days: int) -> int:
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
    return purge_articles_older_than(int(cutoff))
