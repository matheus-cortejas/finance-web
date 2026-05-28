from __future__ import annotations

from django.contrib import admin

from core.models import (
	Alerta,
	Ativo,
	Carteira,
	FonteRSS,
	InteracaoNoticia,
	Noticia,
	NoticiaClassificacao,
	NoticiaScore,
	PerfilInvestidor,
)


@admin.register(Ativo)
class AtivoAdmin(admin.ModelAdmin):
	list_display = ("ticker", "nome", "source")
	search_fields = ("ticker", "nome", "source")


@admin.register(Carteira)
class CarteiraAdmin(admin.ModelAdmin):
	list_display = ("usuario", "nome")
	search_fields = ("usuario__username", "nome")
	filter_horizontal = ("ativos",)


@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
	list_display = ("titulo", "link", "publicado_em", "impacto")
	search_fields = ("titulo", "descricao", "link")
	list_filter = ("impacto",)
	readonly_fields = ("resumo_em",)


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
	list_display = ("usuario", "ativo", "noticia", "created_at")
	search_fields = ("usuario__username", "ativo__ticker", "noticia__titulo")


@admin.register(PerfilInvestidor)
class PerfilInvestidorAdmin(admin.ModelAdmin):
	list_display = ("usuario", "perfil_risco", "horizonte", "frequencia_alertas", "alerta_min_prioridade")
	search_fields = ("usuario__username",)
	list_filter = ("perfil_risco", "horizonte", "frequencia_alertas", "alerta_min_prioridade")


@admin.register(NoticiaClassificacao)
class NoticiaClassificacaoAdmin(admin.ModelAdmin):
	list_display = ("noticia", "sentimento", "impacto", "urgencia", "status", "provider")
	search_fields = ("noticia__titulo", "setor", "tipo_evento")
	list_filter = ("sentimento", "impacto", "urgencia", "status", "provider")


@admin.register(NoticiaScore)
class NoticiaScoreAdmin(admin.ModelAdmin):
	list_display = ("usuario", "noticia", "prioridade", "score_final", "calculado_em")
	search_fields = ("usuario__username", "noticia__titulo")
	list_filter = ("prioridade",)


@admin.register(InteracaoNoticia)
class InteracaoNoticiaAdmin(admin.ModelAdmin):
	list_display = ("usuario", "noticia", "abriu", "ignorou", "tempo_leitura", "criado_em")
	search_fields = ("usuario__username", "noticia__titulo", "origem")
	list_filter = ("abriu", "ignorou")


@admin.register(FonteRSS)
class FonteRSSAdmin(admin.ModelAdmin):
	list_display = ("nome", "url", "confiabilidade", "ativo")
	search_fields = ("nome", "url")
	list_filter = ("ativo",)
