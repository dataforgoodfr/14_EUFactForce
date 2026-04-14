import json
from pathlib import Path

from django.http import JsonResponse
from django.shortcuts import render

from eu_fact_force.app.settings import FLAG_RETRIEVE_DEFAULT_JSON
from eu_fact_force.ingestion.search import (
    NarrativeNotFoundError,
    chunks_context,
    list_prompt_keywords,
    search_narrative,
)

from .forms import IngestForm
from .services import run_pipeline

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
                source_file, elements = run_pipeline(doi)
                context.update(
                    {
                        "success": True,
                        "doi": doi,
                        "source_file": source_file,
                        "elements_count": len(elements),
                    }
                )
            except Exception as e:
                context.update(
                    {
                        "success": False,
                        "error": str(e),
                    }
                )
        else:
            context["form"] = form
    return render(request, "ingestion/ingest.html", context)


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
