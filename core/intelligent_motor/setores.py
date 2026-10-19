"""Taxonomia de setores e classificador heurístico por palavras-chave.

Este módulo tem dois usos:

* **Anotação / avaliação**: fornece a lista canônica de setores usada na
  amostra de anotação e no cálculo da acurácia de setorização.
* **Fase 2 (gating por setor)**: permite restringir os candidatos de tickers
  a um subconjunto coerente com o tema da notícia, atacando as associações
  espúrias descritas na Seção 4 do artigo (ex.: notícia da PETR4 ligada a
  BRKM5/PRIO3/DOW/AVY).

O classificador é propositalmente simples, determinístico e explicável
(contagem de palavras-chave normalizadas). Os rótulos produzidos para os
ativos podem ser sobrescritos manualmente (ver `seed_setores`).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List

# Setores aplicáveis a *empresas* (ativos). Mais específicos primeiro: em
# caso de empate na contagem, o setor que aparece antes vence.
SETORES: List[str] = [
    "Petróleo e Gás",
    "Mineração e Siderurgia",
    "Químicos e Petroquímica",
    "Energia Elétrica",
    "Saneamento",
    "Bancos",
    "Serviços Financeiros",
    "Construção e Materiais",
    "Bens de Capital",
    "Transporte e Logística",
    "Consumo Cíclico",
    "Alimentos e Bebidas",
    "Comércio e Varejo",
    "Saúde e Farmacêutico",
    "Tecnologia e Software",
    "Telecomunicações",
    "Papel e Celulose",
    "Agropecuária",
    "Imobiliário",
    "Educação",
    "Outros",
]

# Rótulos especiais, usados sobretudo na anotação de *notícias*.
SETOR_MACRO = "Macro/Mercado"
SETOR_NAO_APLICA = "Não se aplica"

# Lista completa exposta na amostra de anotação.
SETORES_ANOTACAO: List[str] = SETORES + [SETOR_MACRO, SETOR_NAO_APLICA]

# Palavras-chave (sem acento, minúsculas) por setor. A busca usa fronteira de
# palavra, então "banco" NÃO casa com "bancos" — por isso as variantes são
# listadas explicitamente.
_KEYWORDS: Dict[str, List[str]] = {
    "Petróleo e Gás": [
        "petroleo", "petroleira", "petrobras", "petrorio", "gas", "gases",
        "combustivel", "combustiveis", "refino", "refinaria", "offshore",
        "exploracao", "producao de petroleo", "diesel", "gasolina", "etanol",
        "biocombustivel", "biocombustiveis", "distribuicao de combustiveis",
        "postos",
    ],
    "Mineração e Siderurgia": [
        "mineracao", "mineradora", "minerio", "siderurgia", "siderurgica",
        "aco", "ferro", "metalurgia", "pelotizacao", "bauxita",
    ],
    "Químicos e Petroquímica": [
        "quimica", "quimico", "petroquimica", "braskem", "resinas",
        "plastico", "plasticos", "fertilizantes", "cloro", "soda",
    ],
    "Energia Elétrica": [
        "energia eletrica", "eletrica", "transmissao", "geracao de energia",
        "hidreletrica", "eolica", "solar", "concessoes de energia",
        "distribuidora de energia", "energia renovavel", "usina",
    ],
    "Saneamento": [
        "saneamento", "agua", "esgoto", "tratamento de agua", "sabesp",
    ],
    "Bancos": [
        "banco", "bancos", "bancario", "bancaria", "itau", "bradesco",
        "santander", "banrisul", "btg", "inter", "nubank", "caixa economica",
        "credito", "financiamento",
    ],
    "Serviços Financeiros": [
        "servicos financeiros", "seguradora", "seguros", "cartoes",
        "bandeira de cartoes", "investimentos", "gestao de ativos", "bolsa",
        "fintech", "pagamentos", "corretora", "capitalizacao", "previdencia",
        "holding financeira",
    ],
    "Construção e Materiais": [
        "construcao", "construcao civil", "cimento", "materiais de construcao",
        "incorporacoes", "engenharia civil", "pedreira",
    ],
    "Bens de Capital": [
        "equipamentos", "motores", "automacao industrial", "maquinas",
        "engenharia eletrica", "bens de capital", "compressor", "turbina",
        "implementos",
    ],
    "Transporte e Logística": [
        "logistica", "transporte", "ferrovia", "ferroviaria", "rodovia",
        "porto", "portuario", "armazens", "armazens gerais", "caminhoes",
        "hidrovia", "hidroviario", "frotas", "aluguel de frota", "navegacao",
        "companhia aerea", "aeroportos",
    ],
    "Consumo Cíclico": [
        "veiculos", "automoveis", "autopecas", "moda", "joias", "bijuterias",
        "eletrodomesticos", "eletronicos de consumo", "viagens", "turismo",
        "academias", "fitness", "brinquedos", "moveis", "tecidos",
    ],
    "Alimentos e Bebidas": [
        "alimentos", "bebidas", "cerveja", "refrigerantes", "carnes",
        "frigorifico", "arroz", "feijao", "pescados", "lacteos", "sucos",
        "cafe", "acucar", "derivados de carne",
    ],
    "Comércio e Varejo": [
        "varejo", "supermercados", "e-commerce", "comercio", "lojas",
        "magazine", "farmacias", "drogarias", "distribuicao de medicamentos",
        "atacado", "atacarejo",
    ],
    "Saúde e Farmacêutico": [
        "saude", "hospital", "hospitais", "medicina", "laboratorios",
        "laboratorios de analises", "medicamentos", "farmaceutico",
        "diagnostico", "oncologia", "clinicas", "radioterapia", "vacinas",
    ],
    "Tecnologia e Software": [
        "tecnologia", "software", "cloud", "computacao", "hardware",
        "semicondutores", "internet", "dados", "inteligencia artificial",
        "saas", "erp", "plataforma digital", "redes sociais",
    ],
    "Telecomunicações": [
        "telecomunicacoes", "telecom", "telefonia", "movel", "5g",
        "banda larga", "operadora de telefonia",
    ],
    "Papel e Celulose": [
        "celulose", "papel", "florestal", "eucalipto", "silvicultura",
    ],
    "Agropecuária": [
        "agricultura", "agricola", "agronegocio", "agro", "soja", "algodao",
        "pecuaria", "credito rural", "cana-de-acucar",
    ],
    "Imobiliário": [
        "imobiliario", "imobiliaria", "shoppings", "shopping centers",
        "incorporadora", "loteamento", "galpoes", "aluguel imobiliario",
        "fundos imobiliarios", "empreendimentos imobiliarios",
    ],
    "Educação": [
        "educacao", "ensino", "faculdades", "universidade", "ensino superior",
        "escolas",
    ],
}


def normalize(texto: str | None) -> str:
    """Minúsculas + remoção de acentos, para comparação robusta."""
    if not texto:
        return ""
    base = unicodedata.normalize("NFKD", str(texto))
    base = "".join(ch for ch in base if not unicodedata.combining(ch))
    return base.lower()


def _compile(keywords: List[str]) -> List[re.Pattern]:
    return [re.compile(rf"\b{re.escape(kw)}\b") for kw in keywords]


_COMPILED: Dict[str, List[re.Pattern]] = {
    setor: _compile(kws) for setor, kws in _KEYWORDS.items()
}


def pontuar_setores(texto: str | None) -> Dict[str, int]:
    """Retorna {setor: nº de palavras-chave distintas encontradas}."""
    normalizado = normalize(texto)
    if not normalizado:
        return {}
    scores: Dict[str, int] = {}
    for setor, patterns in _COMPILED.items():
        hits = sum(1 for pat in patterns if pat.search(normalizado))
        if hits:
            scores[setor] = hits
    return scores


def classificar_setor(texto: str | None, default: str = "Outros") -> str:
    """Setor mais provável do texto; ``default`` quando nada casa.

    Desempate: maior contagem e, em empate, a ordem de :data:`SETORES`
    (mais específico primeiro).
    """
    scores = pontuar_setores(texto)
    if not scores:
        return default
    ordem = {setor: i for i, setor in enumerate(SETORES)}
    melhor = max(
        scores.items(),
        key=lambda item: (item[1], -ordem.get(item[0], len(SETORES))),
    )
    return melhor[0]


def setor_do_ativo(nome: str | None, descricao: str | None = None) -> str:
    """Classifica um ativo a partir do nome e da descrição enriquecida."""
    texto = f"{nome or ''} {descricao or ''}".strip()
    return classificar_setor(texto, default="Outros")


__all__ = [
    "SETORES",
    "SETORES_ANOTACAO",
    "SETOR_MACRO",
    "SETOR_NAO_APLICA",
    "normalize",
    "pontuar_setores",
    "classificar_setor",
    "setor_do_ativo",
]
