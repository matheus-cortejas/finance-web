from django.urls import path

from pipeline_lab import views

urlpatterns = [
    path("", views.pipeline_lab_home, name="pipeline_lab_home"),
    path("runs/create/", views.create_run_view, name="pipeline_lab_create_run"),
    path("runs/<int:run_id>/", views.run_detail, name="pipeline_lab_run_detail"),
    path("runs/<int:run_id>/cancel/", views.cancel_run, name="pipeline_lab_cancel_run"),
    path("compare/", views.compare_runs, name="pipeline_lab_compare"),
]
