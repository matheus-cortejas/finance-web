from __future__ import annotations

from django.contrib import admin

from core.models import Alerta, Ativo, Carteira, Noticia


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


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
	list_display = ("usuario", "ativo", "noticia", "created_at")
	search_fields = ("usuario__username", "ativo__ticker", "noticia__titulo")
