from django.urls import path

from pipeline_lab import views

urlpatterns = [
    path("", views.pipeline_lab_home, name="pipeline_lab_home"),
]
