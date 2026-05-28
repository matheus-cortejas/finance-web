import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.acao_repo import asset_exists, add_to_watchlist, get_watchlist_assets
from database.connection import init_db
from services.noticia_service import check_feeds_and_report

def load_feeds(path):
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return []
    with open(path, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def main():
    init_db()
    # try to add PETR4 and ABEV3 to watchlist
    for code in ('PETR4','ABEV3'):
        a = asset_exists(code=code)
        if a:
            add_to_watchlist(a['id'])
            print('Added to watchlist:', a['code'], a['name'])
        else:
            print('Asset not found:', code)

    feeds = load_feeds(os.path.expanduser('~/Downloads/rss.txt'))
    print('Feeds:', feeds)
    watch = [{'id': a['id'], 'code': a['code'], 'name': a['name']} for a in get_watchlist_assets()]
    print('Watchlist:', watch)

    reports = check_feeds_and_report(feeds, watch, within_days=1)
    print('Reports found:', len(reports))
    for r in reports:
        print(r['published'], r['title'], r['link'], r['matches'])

if __name__ == '__main__':
    main()
