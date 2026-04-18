from django.urls import path

from . import views

app_name = "ingestion"
urlpatterns = [
    path("ingest/", views.ingest, name="ingest"),
    path("search/<str:keyword>/", views.search, name="search"),
    # API
    path("api/ingest/", views.api_ingest, name="api_ingest"),
    path("api/ingest/<int:pk>/pdf/", views.api_attach_pdf, name="api_attach_pdf"),
]
