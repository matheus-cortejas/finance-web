from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models


class Ativo(models.Model):
	ticker = models.CharField(max_length=32, unique=True)
	nome = models.CharField(max_length=255)
	source = models.CharField(max_length=32, blank=True, default="")

	class Meta:
		ordering = ["ticker"]

	def __str__(self) -> str:
		return f"{self.ticker} - {self.nome}"


class Carteira(models.Model):
	usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name="carteira")
	ativos = models.ManyToManyField(Ativo, related_name="carteiras", blank=True)
	nome = models.CharField(max_length=255, blank=True, default="")

	def __str__(self) -> str:
		return self.nome or f"Carteira de {self.usuario.username}"


class Noticia(models.Model):
	link = models.URLField(unique=True)
	titulo = models.CharField(max_length=500, blank=True, default="")
	descricao = models.TextField(blank=True, default="")
	resumo = models.TextField(blank=True, default="")
	resumo_status = models.CharField(max_length=32, blank=True, default="pendente")
	resumo_provider = models.CharField(max_length=32, blank=True, default="")
	resumo_em = models.DateTimeField(null=True, blank=True)
	publicado_em = models.DateTimeField(null=True, blank=True)
	feed_url = models.URLField(blank=True, default="")
	impacto = models.CharField(max_length=32, blank=True, default="pendente")
	raw_data = models.JSONField(blank=True, null=True)

	class Meta:
		ordering = ["-publicado_em", "-id"]

	def __str__(self) -> str:
		return self.titulo or self.link


class Alerta(models.Model):
	usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="alertas")
	noticia = models.ForeignKey(Noticia, on_delete=models.CASCADE, related_name="alertas")
	ativo = models.ForeignKey(Ativo, on_delete=models.CASCADE, related_name="alertas")
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["usuario", "noticia", "ativo"], name="unique_alerta_por_usuario_noticia_ativo"),
		]
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return f"{self.usuario.username}: {self.ativo.ticker} -> {self.noticia.link}"
