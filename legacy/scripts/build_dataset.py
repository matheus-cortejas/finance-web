from __future__ import annotations

import argparse
import html
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone


def _ensure_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")
    try:
        import django
    except Exception as exc:
        raise RuntimeError("Django is required to run this script") from exc
    django.setup()


_TAG_RE = re.compile(r"<[^>]+>")
_CODE_LETTERS_RE = re.compile(r"\d+")


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    cleaned = html.unescape(text)
    cleaned = _TAG_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _code_aliases(code: str) -> list[str]:
    if not code:
        return []
    letters_only = _CODE_LETTERS_RE.sub("", code).strip()
    if len(letters_only) >= 4 and letters_only.upper() != code.upper():
        return [letters_only]
    return []


def _find_matches_in_text(text: str, assets: list[dict]) -> list[dict]:
    """
    Stricter matching:
    - Prefer exact ticker token matches (case-sensitive / uppercase).
    - Allow patterns like $TICKER or (TICKER).
    - Match by company name only as fallback (name length >= 4).
    - Skip tickers that are single letters or common stopwords.
    """
    if not text:
        return []
    raw = text
    lower = text.lower()
    STOPWORDS = {
        "a", "o", "e", "de", "do", "da", "dos", "das", "em", "um", "uma", "que",
        "se", "os", "as", "mas", "por", "para", "com", "no", "na", "nos", "nas",
        "ao", "à", "às", "ou", "um", "uma", "sou", "foi", "ser", "são",
    }
    matches = []
    for asset in assets:
        code = (asset.get("ticker") or "").strip()
        name = (asset.get("nome") or "").strip()
        if not code:
            continue
        if len(code) <= 1:
            continue
        if code.lower() in STOPWORDS:
            continue
        matched = False
        try:
            # exact token match (case-sensitive)
            if re.search(r"(?<!\w)" + re.escape(code) + r"(?!\w)", raw):
                matched = True
            # patterns like $TICKER or (TICKER)
            elif re.search(r"[\$\(\[]\s*" + re.escape(code) + r"(?!\w)", raw):
                matched = True
            # uppercase variant present
            elif re.search(r"(?<!\w)" + re.escape(code.upper()) + r"(?!\w)", raw):
                matched = True
            else:
                # letters-only alias (e.g. SUZB from SUZB3) if long enough and uppercase in text
                letters_only = re.sub(r"\d+", "", code)
                if letters_only and len(letters_only) >= 2 and re.search(
                    r"(?<!\w)" + re.escape(letters_only.upper()) + r"(?!\w)", raw
                ):
                    matched = True
                # fallback: match by company name only if descriptive
                elif name and len(name) >= 4 and name.lower() in lower:
                    matched = True
        except re.error:
            continue

        if matched:
            matches.append(asset)
    return matches


def _unique_matches(*groups: list[dict]) -> list[dict]:
    unique = []
    seen_ids = set()
    for group in groups:
        for asset in group:
            asset_id = asset.get("id")
            if asset_id in seen_ids:
                continue
            seen_ids.add(asset_id)
            unique.append(asset)
    return unique


def _extract_raw_content(raw_data) -> str:
    if not raw_data:
        return ""
    if isinstance(raw_data, str):
        return raw_data
    if not isinstance(raw_data, dict):
        try:
            return str(raw_data)
        except Exception:
            return ""

    content_value = raw_data.get("content")
    if isinstance(content_value, list):
        parts = []
        for item in content_value:
            if isinstance(item, dict):
                parts.append(item.get("value", ""))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    if isinstance(content_value, dict):
        return content_value.get("value", "") or ""
    if isinstance(content_value, str):
        return content_value

    for key in ("summary", "description", "title"):
        value = raw_data.get(key)
        if isinstance(value, str) and value.strip():
            return value

    return ""


def _open_dataset_db(path: str, reset: bool) -> sqlite3.Connection:
    if reset and os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS dataset_news (
            noticia_id INTEGER PRIMARY KEY,
            link TEXT,
            titulo TEXT,
            descricao TEXT,
            resumo TEXT,
            publicado_em TEXT,
            feed_url TEXT,
            raw_data TEXT
        );
        CREATE TABLE IF NOT EXISTS dataset_assets (
            asset_id INTEGER PRIMARY KEY,
            ticker TEXT,
            nome TEXT,
            source TEXT
        );
        CREATE TABLE IF NOT EXISTS dataset_matches (
            noticia_id INTEGER,
            asset_id INTEGER,
            ticker TEXT,
            nome TEXT,
            PRIMARY KEY (noticia_id, asset_id)
        );
        CREATE TABLE IF NOT EXISTS dataset_classificacao (
            noticia_id INTEGER PRIMARY KEY,
            sentimento TEXT,
            impacto TEXT,
            urgencia TEXT,
            setor TEXT,
            tipo_evento TEXT,
            tickers_relacionados TEXT,
            relevancia_llm REAL,
            provider TEXT,
            status TEXT,
            classified_at TEXT
        );
        """
    )
    conn.commit()


def _write_assets(conn: sqlite3.Connection, assets: list[dict]) -> None:
    rows = [(a["id"], a["ticker"], a["nome"], a.get("source", "")) for a in assets]
    conn.executemany(
        "INSERT OR REPLACE INTO dataset_assets (asset_id, ticker, nome, source) VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()


def build_dataset(source_db: str, dataset_db: str, limit: int | None, reset: bool, include_unmatched: bool) -> int:
    _ensure_django()

    from django.conf import settings
    from core.llm.openai_client import classify_article, classify_article_heuristic
    from core.models import Ativo, Noticia

    assets = list(Ativo.objects.values("id", "ticker", "nome", "source").order_by("ticker"))
    if not assets:
        print("No assets found. Add assets before running the dataset build.")
        return 1

    conn = _open_dataset_db(dataset_db, reset=reset)
    _init_schema(conn)
    _write_assets(conn, assets)

    queryset = Noticia.objects.all().order_by("id")
    if limit:
        queryset = queryset[:limit]

    processed = 0
    matched_total = 0
    classified_total = 0

    for noticia in queryset:
        processed += 1
        title = _normalize_text(noticia.titulo or "")
        description = _normalize_text(noticia.descricao or "")
        raw_content = _normalize_text(_extract_raw_content(noticia.raw_data))
        content_for_match = raw_content
        content_for_llm = raw_content if settings.OPENAI_USE_CONTENT else ""

        title_matches = _find_matches_in_text(title, assets)
        description_matches = _find_matches_in_text(description, assets) if description else []
        content_matches = _find_matches_in_text(content_for_match, assets) if content_for_match else []
        matches = _unique_matches(title_matches, description_matches, content_matches)
        title_ids = {asset.get("id") for asset in title_matches}
        description_ids = {asset.get("id") for asset in description_matches}
        content_ids = {asset.get("id") for asset in content_matches}
        has_strong_match = bool(title_ids)
        has_medium_match = bool(description_ids)

        if not matches and not include_unmatched:
            continue

        matched_total += 1 if matches else 0

        conn.execute(
            "INSERT OR REPLACE INTO dataset_news (noticia_id, link, titulo, descricao, resumo, publicado_em, feed_url, raw_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                noticia.id,
                noticia.link,
                title,
                description,
                noticia.resumo or "",
                noticia.publicado_em.isoformat() if noticia.publicado_em else "",
                noticia.feed_url or "",
                json.dumps(noticia.raw_data, ensure_ascii=True) if noticia.raw_data is not None else "",
            ),
        )

        if matches:
            match_rows = [
                (noticia.id, asset["id"], asset.get("ticker", ""), asset.get("nome", ""))
                for asset in matches
            ]
            conn.executemany(
                "INSERT OR REPLACE INTO dataset_matches (noticia_id, asset_id, ticker, nome) VALUES (?, ?, ?, ?)",
                match_rows,
            )

            assets_for_llm = [
                {"id": asset["id"], "code": asset.get("ticker", ""), "name": asset.get("nome", "")}
                for asset in matches
            ]

            is_relevant = has_strong_match or has_medium_match
            if is_relevant:
                classification = classify_article(title, description, content_for_llm, assets_for_llm)
                classified_total += 1
            else:
                classification = classify_article_heuristic(title, description, content_for_llm, assets_for_llm)

            matched_tickers = [asset.get("ticker", "") for asset in matches if asset.get("ticker")]
            if not classification.get("tickers_relacionados") and matched_tickers:
                classification["tickers_relacionados"] = matched_tickers

            conn.execute(
                "INSERT OR REPLACE INTO dataset_classificacao (noticia_id, sentimento, impacto, urgencia, setor, tipo_evento, tickers_relacionados, relevancia_llm, provider, status, classified_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    noticia.id,
                    classification.get("sentimento", ""),
                    classification.get("impacto", ""),
                    classification.get("urgencia", ""),
                    classification.get("setor", ""),
                    classification.get("tipo_evento", ""),
                    json.dumps(classification.get("tickers_relacionados", []), ensure_ascii=True),
                    float(classification.get("relevancia_llm", 0.0)),
                    classification.get("provider", ""),
                    classification.get("status", ""),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        if processed % 25 == 0:
            print(f"Processed {processed} | matched {matched_total} | classified {classified_total}")
            conn.commit()

    conn.commit()
    conn.close()

    print(f"Done. processed={processed} matched={matched_total} classified={classified_total}")
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a dataset sqlite database from existing news.")
    parser.add_argument("--source-db", default="", help="Unused (kept for compatibility).")
    parser.add_argument("--dataset-db", default="dataset.sqlite3", help="Output dataset sqlite path.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of news items.")
    parser.add_argument("--reset", action="store_true", help="Delete dataset db if it exists.")
    parser.add_argument(
        "--include-unmatched",
        action="store_true",
        help="Include news with no asset match (no classification performed).",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    dataset_path = os.fspath(args.dataset_db)
    return build_dataset(
        source_db=os.fspath(args.source_db) if args.source_db else "",
        dataset_db=dataset_path,
        limit=args.limit,
        reset=args.reset,
        include_unmatched=args.include_unmatched,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))