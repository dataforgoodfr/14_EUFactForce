import json
from pathlib import Path

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from eu_fact_force.app.settings import FLAG_RETRIEVE_DEFAULT_JSON
from eu_fact_force.ingestion.search import (
    NarrativeNotFoundError,
    chunks_context,
    list_prompt_keywords,
    search_narrative,
)

from eu_fact_force.ingestion.models import Author, Document, DocumentChunk

from eu_fact_force.ingestion.data_collection.collector import fetch_all

from .forms import IngestForm
from .services import DuplicateDOIError, attach_pdf_to_document, ingest_by_doi, _download_pdf

_DEFAULT_SEARCH_PATH = (
    Path(__file__).resolve().parent / "data_collection" / "default_search.json"
)


def ingest(request):
    """Accept a DOI via form, run the pipeline, display success and count."""
    context = {"form": IngestForm()}
    if request.method == "POST":
        form = IngestForm(request.POST)
        if form.is_valid():
            doi = form.cleaned_data["doi"]
            try:
                run = ingest_by_doi(doi)
                context.update(
                    {
                        "success": True,
                        "doi": doi,
                        "source_file": run.document.source_file,
                        "elements_count": DocumentChunk.objects.filter(document=run.document).count(),
                    }
                )
            except DuplicateDOIError as e:
                context.update({"success": False, "error": str(e)})
            except Exception as e:
                context.update({"success": False, "error": str(e)})
        else:
            context["form"] = form
    return render(request, "ingestion/ingest.html", context)


@csrf_exempt
@require_POST
def api_ingest(request):
    """Ingest a document by DOI: fetch metadata, upload PDF to S3, parse and embed chunks.

    Example:
        import requests
        response = requests.post(
            "http://localhost:8000/ingestion/api/ingest/",
            json={"doi": "10.1056/NEJMoa2001017"},
        )
        print(response.json())
        # {"success": true, "doi": "10.1056/NEJMoa2001017", "document_pk": 42, "chunks_count": 17}
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    doi = (body.get("doi") or "").strip()
    if not doi:
        return JsonResponse({"error": "doi is required"}, status=400)

    pdf_url = (body.get("pdf_url") or "").strip() or None

    try:
        run = ingest_by_doi(doi, pdf_url=pdf_url)
        chunks_count = DocumentChunk.objects.filter(document=run.document).count()
        return JsonResponse(
            {
                "success": True,
                "doi": doi,
                "document_pk": run.document.pk,
                "chunks_count": chunks_count,
                "run_status": run.status,
            }
        )
    except DuplicateDOIError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_POST
def api_attach_pdf(request, pk):
    """Attach a PDF to an existing document (metadata-only) and trigger parsing and embedding.

    The document must not already have a PDF attached.

    Example:
        import requests
        with open("article.pdf", "rb") as f:
            response = requests.post(
                "http://localhost:8000/ingestion/api/ingest/42/pdf/",
                files={"pdf": ("article.pdf", f, "application/pdf")},
            )
        print(response.json())
        # {"success": true, "document_pk": 42, "chunks_count": 17}
    """
    try:
        document = Document.objects.get(pk=pk)
    except Document.DoesNotExist:
        return JsonResponse({"error": "Document not found"}, status=404)

    uploaded_file = request.FILES.get("pdf")
    if not uploaded_file:
        return JsonResponse({"error": "'pdf' file field is required"}, status=400)

    try:
        run = attach_pdf_to_document(document, uploaded_file)
        chunks_count = DocumentChunk.objects.filter(document=run.document).count()
        return JsonResponse(
            {"success": True, "document_pk": pk, "chunks_count": chunks_count}
        )
    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_POST
def api_dash_upload(request):
    """Receive a PDF and metadata from the Dash app, create document and run pipeline."""
    try:
        metadata_raw = request.POST.get("metadata")
        if not metadata_raw:
            return JsonResponse({"error": "metadata field is required"}, status=400)

        metadata = json.loads(metadata_raw)

        uploaded_file = request.FILES.get("pdf")
        if not uploaded_file:
            return JsonResponse({"error": "pdf file is required"}, status=400)

        doi = (metadata.get("doi") or "").strip()

        if doi:
            document, _ = Document.objects.update_or_create(
                doi=doi,
                defaults={
                    "title": metadata.get("title", ""),
                    "keywords": [metadata.get("category")] if metadata.get("category") else [],
                },
            )
        else:
            document = Document.objects.create(
                title=metadata.get("title", ""),
                keywords=[metadata.get("category")] if metadata.get("category") else [],
            )

        if "authors" in metadata and isinstance(metadata["authors"], list):
            document.authors.set(Author.from_list(metadata["authors"]))

        run = attach_pdf_to_document(document, uploaded_file, provider_payload=metadata)
        chunks_count = DocumentChunk.objects.filter(document=run.document).count()

        return JsonResponse(
            {"success": True, "document_pk": document.pk, "chunks_count": chunks_count}
        )
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON in metadata"}, status=400)
    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_POST
def api_check_and_fetch_doi(request):
    """Check if a DOI exists, if not, fetch metadata and optionally PDF."""
    try:
        request_payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    doi = (request_payload.get("doi") or "").strip()
    if not doi:
        return JsonResponse({"error": "doi is required"}, status=400)

    if Document.objects.filter(doi=doi).exists():
        return JsonResponse({"status": "exists", "doi": doi})

    try:
        metadata = fetch_all(doi)
        if not metadata.get("found"):
            return JsonResponse({"status": "not_found", "doi": doi})
            
        pdf_path = _download_pdf(doi, pdf_url=None)
            
        return JsonResponse({
            "status": "fetched",
            "doi": doi,
            "metadata": metadata,
            "pdf_found": bool(pdf_path),
            "pdf_path": str(pdf_path) if pdf_path else None
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def search(request, keyword: str):
    """Semantic search over indexed chunks using a narrative keyword.

    Example:
        import requests
        response = requests.get(
            "http://localhost:8000/ingestion/search/vaccine_autism/",
        )
        print(response.json())
        # {"status": "success", "narrative": "vaccine_autism", "chunks": [...], "documents": [...]}
    """
    _ = keyword
    if FLAG_RETRIEVE_DEFAULT_JSON:
        return JsonResponse(
            json.loads(_DEFAULT_SEARCH_PATH.read_text(encoding="utf-8"))
        )
    try:
        chunks = search_narrative(keyword)
    except NarrativeNotFoundError:
        return JsonResponse(
            {
                "error": f"Unknown narrative keyword {keyword!r}; no matching prompt.",
                "keywords": list_prompt_keywords(),
            },
            status=404,
        )

    return JsonResponse(
        {"status": "success", "narrative": keyword, **chunks_context(chunks)}
    )
