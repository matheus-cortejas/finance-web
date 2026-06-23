from __future__ import annotations

from typing import Dict, List


def build_prompt(title: str, description: str, content: str | None, criterios_ativados: List[str] | None) -> str:
    criterios_ativados = criterios_ativados or []
    content_part = f"\n\nConteúdo:\n{content}" if content else ""
    criterios_part = "\n\nCritérios ativados:\n" + "\n".join(f"- {c}" for c in criterios_ativados) if criterios_ativados else "\n\nCritérios ativados:\n- nenhum"

    prompt = (
        "Você é um classificador de notícias financeiras.\n\n"
        "Determine se esta notícia possui potencial relevância para investidores.\n\n"
        "Responda apenas no formato:\n"
        "1|0.90\n"
        "ou\n"
        "0|0.90\n\n"
        "Onde:\n"
        "1 = relevante\n"
        "0 = irrelevante\n\n"
        "O segundo valor representa sua confiança entre 0.00 e 1.00.\n\n"
        "Use apenas intervalos de 0.05\n"
        "Não forneça explicações.\n"
        "Não forneça JSON.\n"
        "Não escreva nenhum texto adicional.\n\n"
        f"Título:\n{title}\n\n"
        f"Descrição:\n{description}{content_part}"
        f"{criterios_part}\n\n"
        "Retorne apenas no formato 'classe|confianca'."
    )
    return prompt


def _example() -> None:
    title = "Empresa X anuncia aquisição estratégica"
    description = "Empresa X comprou 100% da Empresa Y para ampliar atuação em energia renovável."
    content = "Detalhes: transação avaliada em R$ 2 bilhões; integração prevista para 2027."
    criterios = ["ticker_explicito", "fusao_aquisicao", "impacto"]
    print(build_prompt(title, description, content, criterios))


if __name__ == "__main__":
    _example()
