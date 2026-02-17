import json
import time
from pathlib import Path
from tqdm import tqdm
from docling.document_converter import DocumentConverter
from hierarchical.postprocessor import ResultPostprocessor


def get_doc_list(doc_path):
    list_files = []
    for file in doc_path.iterdir():
        if file.is_file():
            list_files.append(file.name)
    return list_files


def run_mini_benchmark():
    # Get list of files
    doc_path = Path("docs/")
    list_files = get_doc_list(doc_path)
    print(f"> number of files: {len(list_files)}")

    # Define Docling converter
    converter = DocumentConverter()

    # Run experiment
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
        with open("results/mini_benchmark_results.json", "w") as f:
            json.dump(experiment_results, f)

        # Export files
        doc_markdwon = result.document.export_to_markdown()
        with open(f"results/md/{doc_name}.md", "w", encoding="utf-8") as f:
            f.write(doc_markdwon)

        doc_html = result.document.export_to_html()
        with open(f"results/html/{doc_name}.html", "w", encoding="utf-8") as f:
            f.write(doc_html)

        doc_json = result.document.export_to_dict()
        with open(f"results/json/{doc_name}.json", "w", encoding="utf-8") as f:
            json.dump(doc_json, f, ensure_ascii=False)


if __name__ == "__main__":
    run_mini_benchmark()
