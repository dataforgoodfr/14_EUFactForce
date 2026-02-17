# EU Fact Force - Ingestion - Experiment - Docling 

### Structure
- `notebook.ipynb`: notebook d'exploration de la structure du parsing produit par Docling, et execution d'un mini-benchmark.
- `docling_experiment.py`: code du mibi-benchmark (temps d'execution, pages, quantité de texte, export des resultats json, markdown et html)
- `docs/`: les PDFs de ce mini-benchmark
- `results`: Exports des résultats du benchmark, avec:
    - `mini_benchmark_results.json`: les résultats 
    - `json/`: exports JSON
    - `html/`: exports HTML
    - `md/`: exports markdwon

### Remarques
- Testé avec tous les PDFs présents sur Kdrive en local, pour certains codument les temps d'executions sont très long (plusieurs dizaines de minutes pour un fichier...) 
- De ce que je comprends, la methode d'OCR derrière peut être assez lourde. Ça peut être un problème si l'utilisateur doit attendre 10min avant de pouvoir éditer / visualiser le document.

### Next 
- Ajouter Docling au benchmark complet
- Investiguer une métrique d'évaluation de la qualité des sections / sous-sections identifiées
- Convertir les résultats en une list de chunks comme attendu (metadata du document, page du chunk, contenu de l'extrait, metadata des sections correspondantes...)