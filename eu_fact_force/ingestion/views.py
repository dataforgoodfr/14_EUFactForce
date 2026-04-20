import json
from pathlib import Path

import requests as http_client
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from eu_fact_force.app.settings import FLAG_RETRIEVE_DEFAULT_JSON
from eu_fact_force.ingestion.search import (
    NarrativeNotFoundError,
    chunks_context,
    list_prompt_keywords,
    search_narrative,
)

from .forms import IngestForm
from .models import Author, Document
from .services import (
    attach_pdf_to_document,
    run_parse_and_embed_async,
    run_pipeline,
    save_uploaded_file_to_document,
    fetch_file_and_metadata,
)

_DEFAULT_SEARCH_PATH = (
    Path(__file__).resolve().parent / "data_collection" / "default_search.json"
)


def ingest(request):
    """Accept a DOI via form and delegate ingestion to the API endpoint."""
    context = {"form": IngestForm()}
    if request.method == "POST":
        form = IngestForm(request.POST)
        if form.is_valid():
            doi = form.cleaned_data["doi"]
            api_url = request.build_absolute_uri(reverse("ingestion:api_ingest"))
            try:
                response = http_client.post(api_url, json={"doi": doi}, timeout=300)
                data = response.json()
                if data.get("success"):
                    context.update(
                        {
                            "success": True,
                            "doi": doi,
                            "elements_count": data.get("chunks_count", 0),
                        }
                    )
                else:
                    context.update({"success": False, "error": data.get("error", "Unknown error")})
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

    try:
        document, chunks = run_pipeline(doi)
        return JsonResponse(
            {"success": True, "doi": doi, "document_pk": document.pk, "chunks_count": len(chunks)}
        )
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
        chunks = attach_pdf_to_document(document, uploaded_file)
        return JsonResponse(
            {"success": True, "document_pk": pk, "chunks_count": len(chunks)}
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
        metadata_raw = request.POST.get('metadata')
        if not metadata_raw:
            return JsonResponse({"error": "metadata field is required"}, status=400)

        metadata = json.loads(metadata_raw)

        uploaded_file = request.FILES.get('pdf')
        pdf_path = metadata.get('pdf_path')
        if not uploaded_file and not pdf_path:
            return JsonResponse({"error": "pdf file or pdf_path is required"}, status=400)

        doi = (metadata.get('doi') or "").strip()

        if doi:
            document, _ = Document.objects.update_or_create(
                doi=doi,
                defaults={
                    "title": metadata.get("title", ""),
                    "keywords": [metadata.get("category")] if metadata.get("category") else [],
                }
            )
        else:
            document = Document.objects.create(
                title=metadata.get("title", ""),
                keywords=[metadata.get("category")] if metadata.get("category") else [],
            )

        if "authors" in metadata and isinstance(metadata["authors"], list):
            document.authors.set(Author.from_list(metadata["authors"]))

        if uploaded_file:
            save_uploaded_file_to_document(document, uploaded_file)
        elif pdf_path:
            import os
            from .models import SourceFile
            
            if not os.path.exists(pdf_path):
                return JsonResponse({"error": "Provided pdf_path does not exist on server"}, status=400)
                
            if document.source_file_id is None:
                source_file = SourceFile.create_from_file(file_path=Path(pdf_path), doi=document.doi or None)
                document.source_file = source_file
                document.save(update_fields=["source_file"])
            else:
                raise ValueError("Document already has a PDF attached.")

        run_parse_and_embed_async(document.pk)

        return JsonResponse(
            {"success": True, "document_pk": document.pk, "status": "processing"}
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
        pdf_path, metadata = fetch_file_and_metadata(doi)
        if not metadata.get("found"):
            return JsonResponse({"status": "not_found", "doi": doi})
            
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
