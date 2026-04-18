from django.urls import path

from . import views

app_name = "ingestion"
urlpatterns = [
    path("ingest/doi/", views.ingest_doi, name="ingest_doi"),
    path("search/<str:keyword>/", views.search, name="search"),
]
