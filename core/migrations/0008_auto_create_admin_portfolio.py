# core/migrations/0008_auto_create_admin_portfolio.py
from django.db import migrations
from django.contrib.auth.hashers import make_password


def create_admin_portfolio(apps, schema_editor):
    Ativo = apps.get_model('core', 'Ativo')
    Carteira = apps.get_model('core', 'Carteira')
    PerfilInvestidor = apps.get_model('core', 'PerfilInvestidor')
    User = apps.get_model('auth', 'User')   # ← fundamental

    admin_username = 'admin'
    admin_email = 'admin@example.com'
    admin_password = 'admin123'  # Altere após o deploy

    user, created = User.objects.get_or_create(
        username=admin_username,
        defaults={
            'email': admin_email,
            'is_staff': True,
            'is_superuser': True,
            'password': make_password(admin_password),
        }
    )
    if created:
        print(f"Usuário admin criado com senha '{admin_password}'. ALTERE IMEDIATAMENTE!")

    # Cria perfil de investidor (usando o mesmo tipo de User)
    PerfilInvestidor.objects.get_or_create(usuario=user)

    # Cria carteira
    carteira, _ = Carteira.objects.get_or_create(usuario=user)

    # Adiciona todos os ativos existentes
    all_assets = Ativo.objects.all()
    if all_assets.exists():
        carteira.ativos.add(*all_assets)
        print(f"Adicionados {all_assets.count()} ativos à carteira do admin.")
    else:
        print("Nenhum ativo encontrado para adicionar.")


def reverse_admin_portfolio(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Carteira = apps.get_model('core', 'Carteira')
    try:
        user = User.objects.get(username='admin')
        carteira = Carteira.objects.get(usuario=user)
        carteira.ativos.clear()
        user.delete()
        print("Usuário admin removido.")
    except User.DoesNotExist:
        pass

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_remove_noticia_confianca_fase4_and_more'),  # Substitua pelo número da última migração
    ]

    operations = [
        migrations.RunPython(create_admin_portfolio, reverse_admin_portfolio),
    ]