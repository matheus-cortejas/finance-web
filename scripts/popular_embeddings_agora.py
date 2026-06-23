import os
import sys
import django

# Ajuste os caminhos conforme sua estrutura
sys.path.append('C:/Users/matheusdossantos/finance-web')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from core.intelligent_motor.fase2_tickers.asset_embedding_store import AssetEmbeddingStore

def main():
    store = AssetEmbeddingStore()
    # O método já carrega o mapeamento do JSON padrão (ativos_mapeamento.json)
    # e gera/salva embeddings para todos os tickers.
    store.generate_and_persist_all()
    print("✅ Todos os embeddings foram gerados e persistidos.")

if __name__ == "__main__":
    main()