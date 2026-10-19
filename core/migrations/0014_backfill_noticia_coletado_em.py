from django.db import migrations
from django.db.models import F
from django.utils import timezone


def backfill_coletado_em(apps, schema_editor):
    Noticia = apps.get_model("core", "Noticia")
    # Notícias antigas não tinham o campo; usamos a data de publicação
    # como melhor aproximação e, quando ausente, o momento da migração.
    Noticia.objects.filter(
        coletado_em__isnull=True, publicado_em__isnull=False
    ).update(coletado_em=F("publicado_em"))
    Noticia.objects.filter(coletado_em__isnull=True).update(
        coletado_em=timezone.now()
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0013_ativo_descricao_embedding_noticia_coletado_em_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_coletado_em, migrations.RunPython.noop),
    ]
