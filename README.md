# 🛡️ EU Fact Force

**A shared hub for coordinated response to health misinformation**

## Table of Contents

- [About](#about)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Contributing](#contributing)

## About

EU Fact Force is a collaborative platform developed by [EUPHA](https://www.eupha.org) (European Public Health Association) with support from [Data For Good](https://dataforgood.fr) volunteers. The platform empowers public health professionals to counter health misinformation by:

- **Connecting scientific evidence** with disinformation narratives
- **Visualizing knowledge graphs** of research articles, claims, and concepts
- **Tracking disinformation trends** through integration with PGP (The Public Good Projects) monitoring data
- **Enabling rapid response** with validated counter-narratives
###  Use Case

> **Marie**, a health communicator at a national public health association, sees a viral post claiming "vaccines cause autism." She needs to respond quickly with solid evidence.
> 
> She searches **"vaccines autism"** on EU Fact Force and immediately sees:
> - An interactive graph showing 15+ peer-reviewed articles that refute this claim
> - The scientific consensus: **"Refuted with high confidence"**
> - Current disinformation trends: 1,200 mentions this week, peak in France/Belgium
> - Key evidence to cite in her response
> 
> **Time to find relevant evidence: <30 seconds**

## Key Features

### V0 (Minimum Viable Product - Target: April 2026)

- **Semantic Search** (FR/EN): Find relevant scientific articles even without exact keyword matches
- **Interactive Knowledge Graph**: Explore connections between articles, claims, and narratives
- **Disinformation Trends**: Visualize PGP monitoring data (volume, geography, examples)
- **Researcher Upload**: Members can upload scientific articles with auto-extracted metadata
- **Multilingual**: Interface and search in French and English
- **Access Control**: Authentication system for EUPHA members

### Scope V0

- **3 priority narratives** (e.g., vaccines-autism, moderate alcohol benefits, COVID misinformation)
- **100-150 scientific articles** from EJPH, WHO, ECDC, and other trusted sources
- **20-30 claims per narrative** (confirmed/refuted/nuanced)
- **Integration with PGP data** (weekly batch updates)

## Contributing

### Project structure
```
14_EUFactForce/
├── .github/
│   └── workflows/
│       ├── d4g-utils.yml
│       └── pre-commit.yaml
├── docs/
├── eu_fact_force/
│   ├── exploration/ # code to keep track of benchmarks
│   ├── ingestion/ # ingestion and indexing of documents
│   └── web/ # web app
├── tests/
```

### Installation

- [Installation de Python](#installation-de-python)

Ce projet utilise [uv](https://docs.astral.sh/uv/) pour la gestion des dépendances Python. Il est préréquis pour l'installation de ce projet.

Une fois installé, il suffit de lancer la commande suivante pour installer la version de Python adéquate, créer un environnement virtuel et installer les dépendances du projet.

```bash
uv sync
```

A l'usage, si vous utilisez VSCode, l'environnement virtuel sera automatiquement activé lorsque vous ouvrirez le projet. Sinon, il suffit de l'activer manuellement avec la commande suivante :

```bash
source .venv/bin/activate
```


### Lancer les precommit-hook localement

[Installer les precommit](https://pre-commit.com/)

```bash
uv run pre-commit run --all-files
```

### Utiliser pytest pour tester votre code

```bash
uv run pytest
```