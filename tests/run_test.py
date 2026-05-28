import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.acao_repo import list_assets, get_watchlist_assets
from database.connection import init_db
from services.acao_service import fetch_sp500_and_store, parse_b3_csv
from services.noticia_service import check_feeds_and_report

def load_feeds(path):
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return []
    with open(path, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def main():
    init_db()
    print('Fetching S&P500 (wiki)...')
    try:
        n = fetch_sp500_and_store()
        print('S&P500 inserted:', n)
    except Exception as e:
        print('Error fetching S&P500:', e)

    csv_path = os.path.expanduser('~/Downloads/IBOVDia_24-03-26.csv')
    print('Parsing B3 CSV (if exists)...', csv_path)
    try:
        m = parse_b3_csv(csv_path)
        print('B3 inserted:', m)
    except Exception as e:
        print('Error parsing B3 CSV:', e)

    print('Total assets in DB:', len(list_assets()))
    watch = get_watchlist_assets()
    print('Watchlist assets:', [{'code':a['code'],'name':a['name']} for a in watch])

    feeds = load_feeds(os.path.expanduser('~/Downloads/rss.txt'))
    print('Feeds loaded:', feeds)
    if not feeds:
        print('No feeds to check; create ~/Downloads/rss.txt with one URL per line.')
        return

    reports = check_feeds_and_report(feeds, [{'id':a['id'],'code':a['code'],'name':a['name']} for a in watch], within_days=1)
    print('Initial reports (within 1 day):')
    for r in reports:
        print(r)

if __name__ == '__main__':
    main()
