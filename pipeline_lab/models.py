from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import Noticia


class ExperimentRun(models.Model):
    """Uma execução do pipeline com um modelo de embeddings específico."""

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_RUNNING, "Executando"),
        (STATUS_DONE, "Concluída"),
        (STATUS_FAILED, "Falhou"),
        (STATUS_CANCELLED, "Cancelada"),
    ]

    nome = models.CharField(max_length=255, blank=True, default="")
    modelo = models.CharField(max_length=255)
    modelo_revision = models.CharField(max_length=128, blank=True, default="")
    embedding_dim = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    config = models.JSONField(default=dict, blank=True)
    metricas = models.JSONField(default=dict, blank=True)
    total_noticias = models.PositiveIntegerField(default=0)
    processadas = models.PositiveIntegerField(default=0)
    erros = models.PositiveIntegerField(default=0)
    erro = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    iniciado_em = models.DateTimeField(null=True, blank=True)
    finalizado_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="experiment_runs",
    )

    class Meta:
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["status", "criado_em"])]

    def __str__(self) -> str:
        return self.nome or f"Run {self.pk} — {self.modelo}"

    @property
    def progresso_pct(self) -> int:
        if not self.total_noticias:
            return 0
        return min(100, int(self.processadas * 100 / self.total_noticias))


class RunClassification(models.Model):
    """Resultado de uma notícia em uma execução (Fases 1 a 5)."""

    run = models.ForeignKey(
        ExperimentRun, on_delete=models.CASCADE, related_name="classifications"
    )
    noticia = models.ForeignKey(
        Noticia, on_delete=models.CASCADE, related_name="run_classifications"
    )

    fase1_aprovada = models.BooleanField(null=True, blank=True)
    relevancia_global = models.FloatField(null=True, blank=True)

    tickers_relacionados = models.JSONField(default=list, blank=True)
    tickers_encontrados = models.JSONField(default=list, blank=True)

    score_heuristico = models.IntegerField(null=True, blank=True)
    criterios_ativados = models.JSONField(default=list, blank=True)

    relevancia_binaria = models.BooleanField(null=True, blank=True)
    confianca_fase4 = models.FloatField(null=True, blank=True)
    provider_fase4 = models.CharField(max_length=32, blank=True, default="")

    sentimento = models.CharField(max_length=16, blank=True, default="")
    impacto = models.CharField(max_length=16, blank=True, default="")
    urgencia = models.IntegerField(null=True, blank=True)
    categoria = models.CharField(max_length=64, blank=True, default="")
    explicacao = models.TextField(blank=True, default="")

    tempos = models.JSONField(default=dict, blank=True)
    erro = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["noticia_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "noticia"], name="unique_run_noticia"
            )
        ]
        indexes = [
            models.Index(fields=["run", "fase1_aprovada"]),
            models.Index(fields=["run", "relevancia_binaria"]),
        ]

    def __str__(self) -> str:
        return f"Run {self.run_id} / notícia {self.noticia_id}"


class AssetEmbedding(models.Model):
    """Embedding de um ativo para um modelo de embeddings específico."""

    modelo = models.CharField(max_length=255, db_index=True)
    ticker = models.CharField(max_length=32)
    descricao = models.TextField(blank=True, default="")
    embedding = models.JSONField()
    dimensao = models.PositiveIntegerField(default=0)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["modelo", "ticker"], name="unique_asset_modelo_ticker"
            )
        ]
        indexes = [models.Index(fields=["modelo", "ticker"])]
        ordering = ["ticker"]

    def __str__(self) -> str:
        return f"{self.ticker} @ {self.modelo}"


class NewsLabel(models.Model):
    """Gabarito manual usado para calcular precisão/recall."""

    noticia = models.OneToOneField(
        Noticia, on_delete=models.CASCADE, related_name="label"
    )
    relevancia = models.BooleanField(null=True, blank=True)
    sentimento = models.CharField(max_length=16, blank=True, default="")
    impacto = models.CharField(max_length=16, blank=True, default="")
    categoria = models.CharField(max_length=64, blank=True, default="")
    observacao = models.TextField(blank=True, default="")
    anotador = models.CharField(max_length=150, blank=True, default="")
    anotado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["noticia_id"]

    def __str__(self) -> str:
        return f"Label notícia {self.noticia_id}"
