# EU Fact Force - Ingestion - Experiment - Docling 

### Contenu
- `notebook.ipynb`: notebook d'exploration de la structure du parsing produit par Docling, et execution d'un mini-benchmark.
- `docling_experiment.py`: code du mini-benchmark (`Docling` vs `PyPDF2` en terme de temps d'execution, pages, quantité de texte, export des resultats json, ainsi que markdown et html pour Docling)
- `docs/`: les documents PDF utilisés pour ce mini-benchmark
- `results`: Exports des résultats du benchmark, avec:
    - `mini_benchmark_results_docling.json`: les résultats Docling 
    - `mini_benchmark_results_pypdf2.json`: les résultats PyPDF2
    - `json/`: exports JSON
    - `html/`: exports HTML
    - `md/`: exports markdwon

### Remarques
- Testé avec tous les PDFs présents sur Kdrive en local, pour certains documents les temps d'exécutions sont très long (plusieurs dizaines de minutes pour un fichier...) 
- De ce que je comprends, la méthode d'OCR derrière peut être assez lourde. Ça peut être un problème si l'utilisateur doit attendre 10min avant de pouvoir éditer / visualiser le document.

### Next 
- Ajouter Docling au benchmark complet
- Investiguer une métrique d'évaluation de la qualité des sections / sous-sections identifiées (ex: est-ce que ce text est bien détecté comme appartenant à cette section?). La libraire de post-processing retourne des warnings qui pourraient être utilisés comme indicateur de qualité. 
- Convertir les résultats en une liste de chunks comme attendu (metadata du document, page du chunk, contenu de l'extrait, metadata des sections correspondantes...)