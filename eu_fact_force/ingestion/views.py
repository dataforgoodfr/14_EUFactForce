from django.shortcuts import render

from .forms import IngestForm
from .services import run_pipeline


def ingest(request):
    """Accept a file_id via form, run the pipeline, display success and count."""
    context = {"form": IngestForm()}
    if request.method == "POST":
        form = IngestForm(request.POST)
        if form.is_valid():
            file_id = form.cleaned_data["file_id"]
            try:
                source_file, elements = run_pipeline(file_id)
                context.update(
                    {
                        "success": True,
                        "file_id": file_id,
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
