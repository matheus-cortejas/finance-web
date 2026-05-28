from __future__ import annotations

from django.urls import path

from core.views import home, dashboard


urlpatterns = [
    path("", home, name="home"),
    path("dashboard/", dashboard, name="dashboard"),
]