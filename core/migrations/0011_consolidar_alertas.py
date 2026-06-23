# core/migrations/000X_consolidar_alertas.py
from django.db import migrations, models

def consolidar(apps, schema_editor):
    Alerta = apps.get_model('core', 'Alerta')

    # Encontra pares (usuario_id, noticia_id) que têm mais de um alerta
    from django.db.models import Count
    duplicados = (
        Alerta.objects.values('usuario_id', 'noticia_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
    )

    for dup in duplicados:
        # Alerta mais antigo (menor id) é mantido
        alerts = Alerta.objects.filter(
            usuario_id=dup['usuario_id'],
            noticia_id=dup['noticia_id']
        ).order_by('id')

        primeiro = alerts.first()
        if primeiro:
            # Remove todos os outros
            alerts.exclude(pk=primeiro.pk).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0010_noticia_relevancia_binaria'),  # dependência da migração do modelo
    ]
    operations = [
        migrations.RunPython(consolidar),
    ]