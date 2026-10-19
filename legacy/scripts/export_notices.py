#!/usr/bin/env python
#python export_notices.py caminho\absoluto\db.sqlite3 --incluir-conteudo -o noticias.json
# -*- coding: utf-8 -*-
"""
Script para extrair dados da tabela core_noticia de um banco SQLite3
e exportar para JSON estruturado.
"""

import sqlite3
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


def conectar_banco(caminho_banco: str) -> sqlite3.Connection:
    """
    Estabelece conexão com o banco SQLite3.
    
    Args:
        caminho_banco: Caminho para o arquivo .db ou .sqlite3
        
    Returns:
        Conexão com o banco de dados
    """
    if not Path(caminho_banco).exists():
        raise FileNotFoundError(f"Banco de dados não encontrado: {caminho_banco}")
    
    conn = sqlite3.connect(caminho_banco)
    conn.row_factory = sqlite3.Row  # Permite acessar colunas por nome
    return conn


def extrair_noticias(conn: sqlite3.Connection, 
                     limit: int = None, 
                     offset: int = None,
                     incluir_conteudo: bool = False) -> List[Dict[str, Any]]:
    """
    Extrai notícias da tabela core_noticia.
    
    Args:
        conn: Conexão com o banco de dados
        limit: Número máximo de registros (opcional)
        offset: Deslocamento inicial (opcional)
        incluir_conteudo: Se True, inclui a coluna 'conteudo'
        
    Returns:
        Lista de dicionários com os dados das notícias
    """
    # Colunas básicas a serem selecionadas
    colunas = ["id", "link", "titulo", "descricao"]
    
    if incluir_conteudo:
        colunas.append("conteudo")
    
    # Monta a query
    query = f"SELECT {', '.join(colunas)} FROM core_noticia"
    params = []
    
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)
    
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    
    # Converte cada linha para dicionário
    noticias = []
    for row in rows:
        noticia = dict(row)
        # Remove valores None para economizar espaço no JSON
        noticia = {k: v for k, v in noticia.items() if v is not None}
        noticias.append(noticia)
    
    return noticias


def obter_contagem_total(conn: sqlite3.Connection) -> int:
    """
    Obtém o número total de registros na tabela core_noticia.
    
    Args:
        conn: Conexão com o banco de dados
        
    Returns:
        Número total de registros
    """
    cursor = conn.execute("SELECT COUNT(*) as total FROM core_noticia")
    return cursor.fetchone()["total"]


def exportar_para_json(noticias: List[Dict[str, Any]], 
                       arquivo_saida: str,
                       meta: Dict[str, Any] = None) -> None:
    """
    Exporta a lista de notícias para um arquivo JSON.
    
    Args:
        noticias: Lista de dicionários com as notícias
        arquivo_saida: Caminho do arquivo de saída
        meta: Metadados adicionais (opcional)
    """
    if meta is None:
        meta = {}
    
    # Estrutura final do JSON
    estrutura = {
        "exportado_em": datetime.now().isoformat(),
        **meta,
        "total_registros": len(noticias),
        "noticias": noticias
    }
    
    with open(arquivo_saida, "w", encoding="utf-8") as f:
        json.dump(estrutura, f, ensure_ascii=False, indent=2)
    
    print(f"Arquivo exportado com sucesso: {arquivo_saida}")
    print(f"Total de registros exportados: {len(noticias)}")


def listar_tabelas(conn: sqlite3.Connection) -> List[str]:
    """
    Lista todas as tabelas do banco de dados (útil para debug).
    """
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [row["name"] for row in cursor.fetchall()]


def main():
    parser = argparse.ArgumentParser(
        description="Extrai dados da tabela core_noticia de um banco SQLite3 para JSON"
    )
    parser.add_argument(
        "banco",
        help="Caminho para o arquivo do banco SQLite3 (ex: db.sqlite3)"
    )
    parser.add_argument(
        "-o", "--output",
        default="noticias_exportadas.json",
        help="Arquivo de saída JSON (padrão: noticias_exportadas.json)"
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        help="Limite de registros a serem extraídos"
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Offset para paginação (padrão: 0)"
    )
    parser.add_argument(
        "--incluir-conteudo",
        action="store_true",
        help="Inclui a coluna 'conteudo' no JSON"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Formata o JSON com indentação (padrão: True, use --no-pretty para desabilitar)"
    )
    parser.add_argument(
        "--list-tables",
        action="store_true",
        help="Lista todas as tabelas do banco e sai"
    )
    
    args = parser.parse_args()
    
    try:
        # Conecta ao banco
        conn = conectar_banco(args.banco)
        
        # Se solicitado, lista as tabelas e sai
        if args.list_tables:
            print("Tabelas encontradas no banco:")
            for tabela in listar_tabelas(conn):
                print(f"  - {tabela}")
            conn.close()
            return
        
        # Obtém contagem total (opcional)
        total = obter_contagem_total(conn)
        print(f"Total de registros na tabela core_noticia: {total}")
        
        # Extrai as notícias
        noticias = extrair_noticias(
            conn, 
            limit=args.limit, 
            offset=args.offset,
            incluir_conteudo=args.incluir_conteudo
        )
        
        # Prepara metadados
        meta = {
            "banco_origem": str(Path(args.banco).absolute()),
            "offset": args.offset,
            "limit": args.limit if args.limit else "todos",
            "inclui_conteudo": args.incluir_conteudo,
            "colunas_extraidas": ["id", "link", "titulo", "descricao"] + (["conteudo"] if args.incluir_conteudo else [])
        }
        
        # Exporta para JSON
        exportar_para_json(noticias, args.output, meta)
        
        conn.close()
        
    except sqlite3.OperationalError as e:
        print(f"Erro no banco de dados: {e}")
        print("Verifique se a tabela 'core_noticia' existe e as colunas estão corretas.")
        exit(1)
    except FileNotFoundError as e:
        print(f"Erro: {e}")
        exit(1)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        exit(1)


if __name__ == "__main__":
    main()