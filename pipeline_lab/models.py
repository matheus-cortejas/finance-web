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
    """Gabarito manual usado para calcular precisão/recall.

    Cobre todas as fases avaliadas no TCC em um único registro por notícia:

    * ``relevancia_financeira`` -> alvo da **Fase 1** (notícia é do mercado
      financeiro?). Se vazio, cai para ``relevancia`` (compatibilidade).
    * ``relevancia`` -> alvo da **Fase 4** (notícia é relevante/acionável?).
    * ``setor`` / ``setor_secundario`` -> alvo da setorização.
    * ``tickers_corretos`` / ``tickers_faltantes`` -> alvo da **Fase 2**
      (avaliação por par notícia–ticker).
    * ``sentimento`` / ``impacto`` / ``urgencia`` / ``categoria`` -> alvo da
      **Fase 5**.
    """

    noticia = models.OneToOneField(
        Noticia, on_delete=models.CASCADE, related_name="label"
    )
    relevancia = models.BooleanField(null=True, blank=True)
    relevancia_financeira = models.BooleanField(null=True, blank=True)
    sentimento = models.CharField(max_length=16, blank=True, default="")
    impacto = models.CharField(max_length=16, blank=True, default="")
    categoria = models.CharField(max_length=64, blank=True, default="")
    setor = models.CharField(max_length=64, blank=True, default="")
    setor_secundario = models.CharField(max_length=64, blank=True, default="")
    urgencia = models.CharField(max_length=16, blank=True, default="")
    tickers_corretos = models.JSONField(default=list, blank=True)
    tickers_faltantes = models.JSONField(default=list, blank=True)
    # True quando o anotador revisou a lista de candidatos da Fase 2 (mesmo
    # que não haja nenhum ticker correto). Sem isso não dá para distinguir
    # "não anotado" de "anotado: nenhum correto".
    tickers_anotados = models.BooleanField(null=True, blank=True)
    confianca = models.PositiveSmallIntegerField(null=True, blank=True)
    observacao = models.TextField(blank=True, default="")
    anotador = models.CharField(max_length=150, blank=True, default="")
    anotado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["noticia_id"]

    def __str__(self) -> str:
        return f"Label notícia {self.noticia_id}"


class LabModel(models.Model):
    """Catálogo de modelos de embeddings disponíveis no laboratório."""

    ORIGEM_UPLOAD = "upload"
    ORIGEM_LOCAL = "local"
    ORIGEM_HUGGINGFACE = "huggingface"
    ORIGEM_CHOICES = [
        (ORIGEM_UPLOAD, "Enviado pela interface"),
        (ORIGEM_LOCAL, "Pasta local do projeto"),
        (ORIGEM_HUGGINGFACE, "Hugging Face"),
    ]

    # Valor usado como `modelo` nas execuções: nome da pasta local ou ID do HF.
    nome = models.CharField(max_length=255, unique=True)
    origem = models.CharField(
        max_length=16, choices=ORIGEM_CHOICES, default=ORIGEM_LOCAL
    )
    descricao = models.TextField(blank=True, default="")
    dimensao = models.PositiveIntegerField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    erro_teste = models.TextField(blank=True, default="")
    testado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_models",
    )

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome

    @property
    def e_local(self) -> bool:
        return self.origem in {self.ORIGEM_UPLOAD, self.ORIGEM_LOCAL}
