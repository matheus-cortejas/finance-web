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
		indexes = [
			models.Index(fields=["publicado_em"]),
			models.Index(fields=["impacto"]),
		]

	def __str__(self) -> str:
		return self.titulo or self.link


class PerfilInvestidor(models.Model):
	RISCO_CHOICES = [
		("conservador", "Conservador"),
		("moderado", "Moderado"),
		("agressivo", "Agressivo"),
	]
	HORIZONTE_CHOICES = [
		("curto", "Curto"),
		("medio", "Medio"),
		("longo", "Longo"),
	]
	FREQUENCIA_ALERTAS_CHOICES = [
		("imediato", "Imediato"),
		("diario", "Diario"),
		("semanal", "Semanal"),
	]
	ALERTA_PRIORIDADE_CHOICES = [
		("critica", "Critica"),
		("alta", "Alta"),
		("media", "Media"),
		("baixa", "Baixa"),
	]

	usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil_investidor")
	perfil_risco = models.CharField(max_length=32, choices=RISCO_CHOICES, default="moderado")
	horizonte = models.CharField(max_length=32, choices=HORIZONTE_CHOICES, default="medio")
	setores_preferidos = models.JSONField(blank=True, default=list)
	sensibilidade_negativo = models.FloatField(default=0.5)
	frequencia_alertas = models.CharField(max_length=32, choices=FREQUENCIA_ALERTAS_CHOICES, default="imediato")
	alerta_min_prioridade = models.CharField(max_length=16, choices=ALERTA_PRIORIDADE_CHOICES, default="media")

	class Meta:
		ordering = ["usuario_id"]

	def __str__(self) -> str:
		return f"Perfil de {self.usuario.username}"


class NoticiaClassificacao(models.Model):
	STATUS_CHOICES = [
		("ok", "Ok"),
		("fallback", "Fallback"),
		("error", "Error"),
	]
	SENTIMENTO_CHOICES = [
		("positivo", "Positivo"),
		("neutro", "Neutro"),
		("negativo", "Negativo"),
	]
	IMPACTO_CHOICES = [
		("alto", "Alto"),
		("medio", "Medio"),
		("baixo", "Baixo"),
		("indefinido", "Indefinido"),
	]
	URGENCIA_CHOICES = [
		("alta", "Alta"),
		("media", "Media"),
		("baixa", "Baixa"),
		("indefinida", "Indefinida"),
	]

	noticia = models.OneToOneField(Noticia, on_delete=models.CASCADE, related_name="classificacao")
	sentimento = models.CharField(max_length=16, choices=SENTIMENTO_CHOICES, default="neutro")
	impacto = models.CharField(max_length=16, choices=IMPACTO_CHOICES, default="indefinido")
	urgencia = models.CharField(max_length=16, choices=URGENCIA_CHOICES, default="indefinida")
	setor = models.CharField(max_length=64, blank=True, default="")
	tipo_evento = models.CharField(max_length=64, blank=True, default="")
	tickers_relacionados = models.JSONField(blank=True, default=list)
	relevancia_llm = models.FloatField(default=0.0)
	provider = models.CharField(max_length=32, blank=True, default="")
	status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="ok")

	class Meta:
		ordering = ["-id"]

	def __str__(self) -> str:
		return f"Classificacao: {self.noticia_id} ({self.status})"


class NoticiaScore(models.Model):
	PRIORIDADE_CHOICES = [
		("critica", "Critica"),
		("alta", "Alta"),
		("media", "Media"),
		("baixa", "Baixa"),
	]

	noticia = models.ForeignKey(Noticia, on_delete=models.CASCADE, related_name="scores")
	usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="noticia_scores")
	score_final = models.FloatField(default=0.0)
	prioridade = models.CharField(max_length=16, choices=PRIORIDADE_CHOICES, default="media")
	motivos = models.JSONField(blank=True, default=dict)
	calculado_em = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["noticia", "usuario"], name="unique_score_por_usuario_noticia"),
		]
		indexes = [
			models.Index(fields=["prioridade"]),
			models.Index(fields=["score_final"]),
		]
		ordering = ["-calculado_em"]

	def __str__(self) -> str:
		return f"Score: {self.usuario.username} -> {self.noticia_id}"


class InteracaoNoticia(models.Model):
	usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="interacoes_noticia")
	noticia = models.ForeignKey(Noticia, on_delete=models.CASCADE, related_name="interacoes")
	abriu = models.BooleanField(default=False)
	ignorou = models.BooleanField(default=False)
	tempo_leitura = models.PositiveIntegerField(default=0)
	origem = models.CharField(max_length=64, blank=True, default="")
	criado_em = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-criado_em"]

	def __str__(self) -> str:
		return f"Interacao: {self.usuario.username} -> {self.noticia_id}"


class FonteRSS(models.Model):
	url = models.URLField(unique=True)
	nome = models.CharField(max_length=255, blank=True, default="")
	confiabilidade = models.FloatField(default=0.5)
	ativo = models.BooleanField(default=True)

	class Meta:
		ordering = ["nome", "id"]

	def __str__(self) -> str:
		return self.nome or self.url


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
