from __future__ import annotations

from django.urls import path

from core.views import chat, chat_api, dashboard, home


urlpatterns = [
    path("", home, name="home"),
    path("dashboard/", dashboard, name="dashboard"),
    path("chat/", chat, name="chat"),
    path("chat/api/", chat_api, name="chat_api"),
]