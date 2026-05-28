from __future__ import annotations

import sqlite3
import threading

from config.settings import DB_PATH


_lock = threading.Lock()


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _lock:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY,
                source TEXT,
                code TEXT,
                name TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY,
                asset_id INTEGER,
                tag TEXT,
                FOREIGN KEY(asset_id) REFERENCES assets(id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_articles (
                id INTEGER PRIMARY KEY,
                link TEXT UNIQUE,
                published_ts INTEGER
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                link TEXT UNIQUE,
                title TEXT,
                description TEXT,
                published_ts INTEGER,
                feed_url TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS article_matches (
                id INTEGER PRIMARY KEY,
                article_id INTEGER,
                asset_id INTEGER,
                FOREIGN KEY(article_id) REFERENCES articles(id),
                FOREIGN KEY(asset_id) REFERENCES assets(id)
            )
            """
        )
        connection.commit()
        connection.close()
