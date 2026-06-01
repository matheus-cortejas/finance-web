import os
import sys
import django

# Ajuste o caminho para o seu projeto (se necessário)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")
django.setup()

from core.parsers.rss_parser import RSSParser

url = "https://www.infomoney.com.br/feed/"
parser = RSSParser(url)
data = parser.fetch()

for entry in data["entries"][:5]:
    print("Título:", entry["title"])
    print("Descrição (limpa):", entry["description"][:300])
    print("Conteúdo (início):", entry["content"][:2000])
    print("-" * 50)