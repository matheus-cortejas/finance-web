from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="noticia",
            name="resumo",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="noticia",
            name="resumo_status",
            field=models.CharField(blank=True, default="pendente", max_length=32),
        ),
        migrations.AddField(
            model_name="noticia",
            name="resumo_provider",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="noticia",
            name="resumo_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
