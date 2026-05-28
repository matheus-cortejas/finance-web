from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import PerfilInvestidor


@receiver(post_save, sender=User)
def create_investor_profile(sender, instance: User, created: bool, **kwargs) -> None:
    if created:
        PerfilInvestidor.objects.get_or_create(usuario=instance)
