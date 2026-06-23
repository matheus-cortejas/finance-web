from __future__ import annotations

from django.urls import path

from core.views import home, dashboard, asset_suggestions, record_interaction, lista_noticias, detalhe_noticia, meus_alertas, register


urlpatterns = [
    path("", home, name="home"),
    path("dashboard/", dashboard, name="dashboard"),
    path("dashboard/suggestions/", asset_suggestions, name="asset_suggestions"),
    path("dashboard/interactions/", record_interaction, name="record_interaction"),
    path('noticias/', lista_noticias, name='lista_noticias'),
    path('noticia/<int:noticia_id>/', detalhe_noticia, name='detalhe_noticia'),
    path('meus-alertas/', meus_alertas, name='meus_alertas'),    
    path('register/', register, name='register'),
]