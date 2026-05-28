import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.acao_repo import find_assets_by_term
from database.connection import init_db
from database.noticia_repo import link_article_match, save_article
from time import time
import sqlite3

def make_fake_articles():
    now = int(time())
    return [
        {
            'title': 'Petrobras anuncia novo investimento em refino',
            'description': 'A PETROBRAS (PETR4) confirmou aporte de R$ 2 bi em nova planta.',
            'link': 'https://example.test/petrobras-refino',
            'published_ts': now - 3600,
        },
        {
            'title': 'Ambev reporta crescimento de vendas',
            'description': 'AMBEV S/A (ABEV3) atingiu crescimento de 5% no trimestre.',
            'link': 'https://example.test/ambev-vendas',
            'published_ts': now - 7200,
        },
        {
            'title': 'Notícia irrelevante',
            'description': 'Conteúdo que não menciona ativos da carteira.',
            'link': 'https://example.test/irrelevante',
            'published_ts': now - 1800,
        },
    ]

def main():
    init_db()
    articles = make_fake_articles()
    for art in articles:
        aid = save_article(art['link'], art['title'], art['description'], art['published_ts'], feed_url='https://example.test/feed')
        print('Saved article id=', aid, 'title=', art['title'])
        for term in ['PETR4','ABEV3','PETROBRAS','AMBEV']:
            rows = find_assets_by_term(term)
            for r in rows:
                try:
                    link_article_match(aid, r['id'])
                    print('Linked article', aid, 'to asset', r['code'])
                except Exception:
                    pass

    conn = sqlite3.connect('data.db')
    cur = conn.cursor()
    cur.execute('SELECT id, title, link FROM articles ORDER BY published_ts DESC')
    print('\nArticles in DB:')
    for row in cur.fetchall():
        print(row)
    cur.execute('SELECT a.id, a.title, am.asset_id, ap.code FROM articles a JOIN article_matches am ON am.article_id=a.id JOIN assets ap ON ap.id=am.asset_id')
    print('\nArticle matches:')
    for row in cur.fetchall():
        print(row)
    conn.close()

if __name__ == '__main__':
    main()
