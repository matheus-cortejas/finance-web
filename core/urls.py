from __future__ import annotations

from django.urls import path

from core.views import home, dashboard, asset_suggestions, record_interaction


urlpatterns = [
    path("", home, name="home"),
    path("dashboard/", dashboard, name="dashboard"),
    path("dashboard/suggestions/", asset_suggestions, name="asset_suggestions"),
    path("dashboard/interactions/", record_interaction, name="record_interaction"),
]