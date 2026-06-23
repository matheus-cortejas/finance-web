import re
from typing import Dict

def preprocessar_texto(noticia: Dict) -> str:
    titulo = noticia.get("titulo") or ""
    descricao = noticia.get("descricao") or ""
    conteudo = noticia.get("conteudo") or ""

    texto = " ".join([titulo, descricao, conteudo])

    # Remover caracteres de controle
    texto = re.sub(r"[\x00-\x1F\x7F]+", " ", texto)

    # Normalizar espaços e quebras de linha
    texto = re.sub(r"\s+", " ", texto).strip()

    # Truncamento para 350 palavras
    palavras = texto.split()
    if len(palavras) > 350:
        texto = " ".join(palavras[:350])

    return texto

__all__ = ["preprocessar_texto"]
