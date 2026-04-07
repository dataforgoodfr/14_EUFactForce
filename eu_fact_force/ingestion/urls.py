from django.urls import path
from . import views, api

app_name = "ingestion"
urlpatterns = [
    path("ingest/", views.ingest, name="ingest"),
    path("api/upload/", api.upload_pdf, name="api-upload"),
]
