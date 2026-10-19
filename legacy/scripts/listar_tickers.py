#!/usr/bin/env python
# scripts/listar_tickers.py
import os
import sys
import django

# Ajuste os caminhos conforme seu projeto
sys.path.append('C:/Users/matheusdossantos/finance-web')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from core.models import Ativo

def listar_tickers():
    tickers = list(Ativo.objects.values_list('ticker', flat=True).order_by('ticker'))
    # Formato Python
    print("CARTEIRA_PADRAO = [")
    for i, t in enumerate(tickers):
        # Quebra de linha a cada 8 itens (opcional)
        if i % 8 == 0:
            print("    ", end="")
        print(f'"{t}"', end="")
        if i < len(tickers)-1:
            print(", ", end="")
        if (i+1) % 8 == 0:
            print()
    print("\n]")
    print(f"\nTotal: {len(tickers)} tickers")

if __name__ == "__main__":
    listar_tickers()