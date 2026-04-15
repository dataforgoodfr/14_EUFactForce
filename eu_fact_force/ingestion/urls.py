from django.urls import path

from . import views

app_name = "ingestion"
urlpatterns = [
    path("ingest/", views.ingest, name="ingest"),
    path("search/<str:keyword>/", views.search, name="search"),
]
