import os
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import json

from eu_fact_force.ingestion.data_collection.parsers.base import doi_to_id

from eu_fact_force.app.settings import FLAG_RETRIEVE_DEFAULT_JSON
from eu_fact_force.ingestion.search import (
    NarrativeNotFoundError,
    chunks_context,
    list_prompt_keywords,
    search_narrative,
)

from .services import DuplicateDOIError, ingest_by_doi

_DEFAULT_SEARCH_PATH = (
    Path(__file__).resolve().parent / "data_collection" / "default_search.json"
)


@csrf_exempt
@require_POST
def ingest_doi(request):
    """Multipart API: POST doi + optional pdf_file → trigger ingest_by_doi."""
    doi = (request.POST.get("doi") or "").strip()
    if not doi:
        return JsonResponse({"error": "Missing required field: doi."}, status=400)

    pdf_url = (request.POST.get("pdf_url") or "").strip() or None

    pdf_path = None
    pdf_file = request.FILES.get("pdf_file")
    if pdf_file:
        pdf_dir = Path(__file__).parents[2] / "data" / "data_collection" / "pdf"
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_path = pdf_dir / f"{doi_to_id(doi)}.pdf"
        with open(pdf_path, "wb") as fh:
            for chunk in pdf_file.chunks():
                fh.write(chunk)

    try:
        run = ingest_by_doi(doi, pdf_url=pdf_url, pdf_path=pdf_path)
    except DuplicateDOIError as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse(
        {
            "status": "success",
            "run_id": run.pk,
            "doi": doi,
            "success_kind": run.success_kind,
        }
    )


def search(request, keyword: str):
    """Return the default search fixture JSON (keyword reserved for future filtering)."""
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
