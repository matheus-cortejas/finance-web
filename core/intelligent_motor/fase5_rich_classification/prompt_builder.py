import json


def _truncate_text(text: str, max_chars: int) -> str:
    if not text:
        return ""

    text = text.strip()

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "..."


def build_prompt(noticia: dict, config: dict) -> str:
    """
    Constrói o prompt da Fase 5 utilizando
    contexto das fases anteriores.
    """
    prompt_cfg = config.get("prompt", {})  

    titulo = noticia.get("titulo", "")
    descricao = noticia.get("descricao", "")
    conteudo = noticia.get("conteudo", "")

    tickers = noticia.get("tickers_relacionados", [])
    score_heuristico = noticia.get("score_heuristico")
    criterios = noticia.get("criterios_ativados", [])
    relevancia_global = noticia.get("relevancia_global")

    max_chars = prompt_cfg.get("max_content_chars", 800)

    conteudo = _truncate_text(conteudo, max_chars)

    categorias = prompt_cfg.get("allowed_categorias", [])

    prompt = f"""
Você é um analista financeiro especializado.

Sua tarefa é classificar a notícia abaixo.

Retorne APENAS um JSON válido.

Formato obrigatório:

{{
  "sentimento": "positivo|neutro|negativo",
  "impacto": "baixo|medio|alto",
  "urgencia": 0,
  "categoria": "uma das categorias permitidas",
  "explicacao": "uma frase curta"
}}

Regras:

- sentimento:
  positivo = favorece ativos ou mercado
  negativo = prejudica ativos ou mercado
  neutro = impacto indefinido

- impacto:
  baixo = efeito limitado
  medio = efeito relevante
  alto = efeito significativo

- urgencia:
  inteiro entre 0 e 10

- categoria:
  escolha apenas uma categoria dentre:
  {", ".join(categorias)}

- explicacao:
  máximo de uma frase curta
  máximo de 200 caracteres

Não adicione markdown.
Não adicione comentários.
Não explique o raciocínio.
Retorne apenas JSON.

CONTEXTO:

relevancia_global: {relevancia_global}

score_heuristico: {score_heuristico}

tickers_relacionados:
{json.dumps(tickers, ensure_ascii=False)}

criterios_ativados:
{json.dumps(criterios, ensure_ascii=False)}

NOTÍCIA:

Título:
{titulo}

Descrição:
{descricao}

Conteúdo:
{conteudo}
"""

    return prompt.strip()