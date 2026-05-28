from __future__ import annotations

from core.models import InteracaoNoticia, PerfilInvestidor


def update_profile_from_interactions(usuario, limit: int = 50) -> PerfilInvestidor | None:
    perfil = PerfilInvestidor.objects.filter(usuario=usuario).first()
    if not perfil:
        return None

    interactions = (
        InteracaoNoticia.objects.filter(usuario=usuario)
        .select_related("noticia", "noticia__classificacao")
        .order_by("-criado_em")[:limit]
    )
    if not interactions:
        return perfil

    neg_opened = 0
    neg_ignored = 0
    setor_counts: dict[str, int] = {}

    for interaction in interactions:
        classificacao = getattr(interaction.noticia, "classificacao", None)
        if not classificacao:
            continue

        sentimento = (classificacao.sentimento or "").lower()
        if sentimento == "negativo":
            if interaction.abriu:
                neg_opened += 1
            if interaction.ignorou:
                neg_ignored += 1

        if interaction.abriu:
            setor = (classificacao.setor or "").strip()
            if setor:
                setor_counts[setor] = setor_counts.get(setor, 0) + 1

    update_fields = []
    total_neg = neg_opened + neg_ignored
    if total_neg:
        ratio = neg_opened / total_neg
        new_sensibilidade = round(0.2 + (0.7 * ratio), 2)
        if abs(perfil.sensibilidade_negativo - new_sensibilidade) >= 0.05:
            perfil.sensibilidade_negativo = new_sensibilidade
            update_fields.append("sensibilidade_negativo")

    if not perfil.setores_preferidos and setor_counts:
        top_setores = sorted(setor_counts.items(), key=lambda item: item[1], reverse=True)[:3]
        perfil.setores_preferidos = [setor for setor, _ in top_setores]
        update_fields.append("setores_preferidos")

    if update_fields:
        perfil.save(update_fields=update_fields)

    return perfil
