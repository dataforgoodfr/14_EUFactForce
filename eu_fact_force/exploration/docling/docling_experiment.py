import json
import time
from pathlib import Path
from tqdm import tqdm
from docling.document_converter import DocumentConverter
from hierarchical.postprocessor import ResultPostprocessor
from PyPDF2 import PdfReader


def get_doc_list(doc_path):
    list_files = []
    for file in doc_path.iterdir():
        if file.is_file():
            list_files.append(file.name)
    return list_files


def run_mini_benchmark_docling():
    # Get list of files
    doc_path = Path("docs/")
    list_files = get_doc_list(doc_path)
    print(f"> number of files: {len(list_files)}")

    # Define Docling converter
    converter = DocumentConverter()

    # Run experiment
    print(f"### Starting - docling benchmark ###")
    experiment_results = {}
    for filename in tqdm(list_files):
        # Select file
        print(f"> selected file: {filename}")
        file_path = Path(filename)
        doc_name = file_path.stem

        # Convert
        start_time = time.time()
        result = converter.convert(doc_path / file_path)
        ResultPostprocessor(result).process()
        total_time = time.time() - start_time

        # Save results
        experiment_results[filename] = {
            "total_time": total_time,
            "total_pages": len(result.pages),
            "time_per_page": total_time / len(result.pages),
            "total_chars": len(result.document.export_to_text()),
        }
        with open("results/mini_benchmark_results_docling.json", "w") as f:
            json.dump(experiment_results, f)

        # Export files
        doc_markdwon = result.document.export_to_markdown()
        with open(f"results/md/{doc_name}_docling.md", "w", encoding="utf-8") as f:
            f.write(doc_markdwon)

        doc_html = result.document.export_to_html()
        with open(f"results/html/{doc_name}_docling.html", "w", encoding="utf-8") as f:
            f.write(doc_html)

        doc_json = result.document.export_to_dict()
        with open(f"results/json/{doc_name}_docling.json", "w", encoding="utf-8") as f:
            json.dump(doc_json, f, ensure_ascii=False)


def run_mini_benchmark_pypdf2():
    # Get list of files
    doc_path = Path("docs/")
    list_files = get_doc_list(doc_path)
    print(f"> number of files: {len(list_files)}")

    # Run experiment
    print(f"### Starting - pypdf2 benchmark ###")
    experiment_results = {}
    for filename in tqdm(list_files):
        # Select file
        print(f"> selected file: {filename}")
        file_path = Path(filename)
        doc_name = file_path.stem

        # Convert
        start_time = time.time()
        result = PdfReader(doc_path / file_path)
        total_time = time.time() - start_time

        # Get full text
        full_text = []
        for page in result.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)
        full_text = "\n".join(full_text)

        # Save results
        experiment_results[filename] = {
            "total_time": total_time,
            "total_pages": len(result.pages),
            "time_per_page": total_time / len(result.pages),
            "total_chars": len(full_text),
        }
        with open("results/mini_benchmark_results_pypdf2.json", "w") as f:
            json.dump(experiment_results, f)

        # Export files
        pages = []
        for i, page in enumerate(result.pages, start=1):
            pages.append({"page": i, "text": page.extract_text() or ""})

        doc_json = {"num_pages": len(result.pages), "pages": pages}
        with open(f"results/json/{doc_name}_pypdf2.json", "w", encoding="utf-8") as f:
            json.dump(doc_json, f, ensure_ascii=False)


if __name__ == "__main__":
    run_mini_benchmark_docling()
    run_mini_benchmark_pypdf2()
