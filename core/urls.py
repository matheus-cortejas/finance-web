from __future__ import annotations

from django.urls import path

from core.views import dashboard


urlpatterns = [
    path("", dashboard, name="home"),
]