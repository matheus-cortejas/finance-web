from __future__ import annotations

import csv
import os

from config.settings import DEFAULT_B3_CSV
from database.acao_repo import count_assets_by_source, insert_asset


WIKI_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies#S&P_500_component_stocks"


def fetch_sp500_and_store() -> int:
    if count_assets_by_source("sp500") > 0:
        return 0

    try:
        import requests
        from bs4 import BeautifulSoup
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("requests/beautifulsoup4 are required to fetch S&P500 data") from exc

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
    }
    response = requests.get(WIKI_SP500_URL, timeout=15, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    table = soup.find("table", {"id": "constituents"}) or soup.find("table", class_="wikitable sortable")
    if not table:
        return 0

    count = 0
    for row in table.find_all("tr")[1:]:
        columns = row.find_all(["td", "th"])
        if len(columns) < 2:
            continue
        code = columns[0].get_text(strip=True)
        name = columns[1].get_text(strip=True)
        if not code or not name:
            continue
        try:
            insert_asset("sp500", code, name)
            count += 1
        except Exception:
            pass
    return count


def parse_b3_csv(path: str | os.PathLike[str] | None = None) -> int:
    csv_path = os.fspath(path or DEFAULT_B3_CSV)
    if not os.path.exists(csv_path):
        return 0

    if count_assets_by_source("b3") > 0:
        return 0

    count = 0
    with open(csv_path, newline="", encoding="latin-1") as handle:
        reader = csv.reader(handle, delimiter=";")
        for row in reader:
            if not row:
                continue
            code = row[0].strip() if len(row) > 0 else ""
            name = row[1].strip() if len(row) > 1 else ""
            if code and name and code.upper() != "CÓDIGO" and "Quantidade" not in code:
                try:
                    insert_asset("b3", code, name)
                    count += 1
                except Exception:
                    pass
    return count
