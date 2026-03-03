from django.shortcuts import render

from .forms import IngestForm
from .services import run_pipeline


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
