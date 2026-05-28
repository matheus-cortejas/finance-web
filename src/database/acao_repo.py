from __future__ import annotations

from typing import List

from database.connection import get_connection, init_db


def asset_exists(code: str | None = None, name: str | None = None):
    connection = get_connection()
    cursor = connection.cursor()
    if code:
        cursor.execute("SELECT * FROM assets WHERE LOWER(code)=LOWER(?) LIMIT 1", (code,))
        row = cursor.fetchone()
        connection.close()
        return row
    if name:
        cursor.execute("SELECT * FROM assets WHERE LOWER(name)=LOWER(?) LIMIT 1", (name,))
        row = cursor.fetchone()
        connection.close()
        return row
    connection.close()
    return None


def insert_asset(source: str, code: str, name: str) -> None:
    init_db()
    if asset_exists(code=code):
        return
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("INSERT INTO assets (source, code, name) VALUES (?,?,?)", (source, code, name))
    connection.commit()
    connection.close()


def list_assets() -> List[object]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM assets")
    rows = cursor.fetchall()
    connection.close()
    return rows


def find_assets_by_term(term: str) -> List[object]:
    connection = get_connection()
    cursor = connection.cursor()
    query = f"%{term}%"
    cursor.execute(
        "SELECT * FROM assets WHERE LOWER(code) LIKE LOWER(?) OR LOWER(name) LIKE LOWER(?)",
        (query, query),
    )
    rows = cursor.fetchall()
    connection.close()
    return rows


def add_to_watchlist(asset_id: int, tag: str | None = None) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("INSERT INTO watchlist (asset_id, tag) VALUES (?,?)", (asset_id, tag))
    connection.commit()
    connection.close()


def get_watchlist_assets() -> List[object]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT a.* FROM assets a JOIN watchlist w ON w.asset_id=a.id")
    rows = cursor.fetchall()
    connection.close()
    return rows


def count_assets_by_source(source: str) -> int:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(1) as c FROM assets WHERE source=?", (source,))
    row = cursor.fetchone()
    connection.close()
    return int(row["c"]) if row else 0
