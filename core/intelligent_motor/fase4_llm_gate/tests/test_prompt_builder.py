from core.intelligent_motor.fase4_llm_gate.prompt_builder import build_prompt
import re


def test_build_prompt_contains_fields():
    title = "Empresa X anuncia"
    description = "Aquisição importante"
    content = "Detalhes da transação"
    criterios = ["ticker_explicito", "impacto"]
    prompt = build_prompt(title, description, content, criterios)
    assert "Título:" in prompt
    assert "Descrição:" in prompt
    assert "Conteúdo:" in prompt
    assert "Critérios ativados:" in prompt
    assert "- ticker_explicito" in prompt
    assert "- impacto" in prompt
    assert re.search(r"Responda apenas '1' ou '0'", prompt)
