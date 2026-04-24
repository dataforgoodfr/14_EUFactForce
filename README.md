# 🛡️ EU Fact Force

**A shared hub for coordinated response to health misinformation**

## Table of Contents

- [Quick Start](#quick-start)
- [About](#about)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Contributing](#contributing)
- [Seeding the database](#seeding-the-database)

## Quick Start

The fastest way to run the full stack locally is via Docker Compose. The only prerequisite is [Docker Desktop](https://www.docker.com/products/docker-desktop/).

**1. Start all services**

```bash
docker compose up --build -d
```

This builds the app image, starts PostgreSQL, MinIO (S3-compatible storage), the Django backend, and the Dash frontend. Database migrations run automatically on first start.
Avoid having `DATABASE_URL` set in your `.env` for this step, to avoid a connection timeout when the app tries to reach the DB.

**2. Seed the database**

```bash
docker compose exec app uv run --no-sync python manage.py seed_db --csv data/seed/vaccine_autism_evidence_curated.csv -e DATABASE_URL=postgresql://eu_fact_force:eu_fact_force@localhost:5432/eu_fact_force
```

This ingests a curated set of vaccine/autism research articles (fetches PDFs and metadata from the internet). See [Seeding the database](#seeding-the-database) for other input options.

**3. Create an admin user**

```bash
docker compose exec app uv run --no-sync python manage.py createsuperuser
```

**4. Open in your browser**

| Service | URL |
|---|---|
| Dash frontend | http://localhost:8050 |
| Django admin | http://localhost:8000/admin/ |
| MinIO console | http://localhost:9001 (user: `minioadmin` / pass: `minioadmin`) |

**Stopping**

```bash
docker compose down
```

---

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
> **Time to find relevant evidence: <30 s**

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
│   └── app/ # web app
├── tests/
```

### Installation

- [Installation de Python](#installation-de-python)

Ce projet utilise [uv](https://docs.astral.sh/uv/) pour la gestion des dépendances Python. Il est préréquis pour l'installation de ce projet.

Une fois installé, il suffit de lancer la commande suivante pour installer la version de Python adéquate, créer un environnement virtuel et installer les dépendances du projet.

```bash
uv sync
uv run pre-commit install
```

Pour exécuter le pipeline d'ingestion avec parsing Docling, installez aussi les dépendances de parsing :

```bash
uv sync --group parsing
```

Pour exécuter l'étape d'embedding dans le pipeline d'ingestion :

- le modèle utilisé est `intfloat/multilingual-e5-base`
- `sentence-transformers` est requis (installé via `uv sync`)
- prévoir plus de RAM/temps au premier chargement du modèle

A l'usage, si vous utilisez VSCode, l'environnement virtuel sera automatiquement activé lorsque vous ouvrirez le projet. Sinon, il suffit de l'activer manuellement avec la commande suivante :

```bash
source .venv/bin/activate
```


### Tests et formattage

[Installer les precommit](https://pre-commit.com/)

```bash
uv run pre-commit run --all-files
```

**Utiliser pytest pour tester votre code**

```bash
uv run pytest
```

### Déploiement de l’application

L’application se compose d’un serveur Django, d’une base PostgreSQL (avec pgvector), de **MinIO** pour le stockage S3 (compatible AWS), et d’un frontend **Dash**.

Pour un démarrage rapide, voir la section [Quick Start](#quick-start) en haut de ce document.

**Développement hors Docker (Django au host)**

Si vous souhaitez lancer Django directement sur votre machine (sans le conteneur `app`) :

**1. Prérequis**

- [Python 3.12+](https://www.python.org/) et [uv](https://docs.astral.sh/uv/)
- [Docker](https://www.docker.com/) et Docker Compose (pour Postgres et MinIO)

**2. Démarrer uniquement les services d’infrastructure**

```bash
docker compose up -d postgres minio minio-init
```

**3. Variables d’environnement**

```bash
cp .env.template .env
```

Pour pointer Django vers MinIO local, définissez dans `.env` :

```bash
DATABASE_URL=postgresql://eu_fact_force:eu_fact_force@localhost:5432/eu_fact_force
AWS_S3_ENDPOINT_URL=http://localhost:9000
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_STORAGE_BUCKET_NAME=eu-fact-force-files
AWS_S3_REGION_NAME=eu-west-1
```

**4. Installer les dépendances et appliquer les migrations**

```bash
uv sync
uv run python manage.py migrate
```

**5. (Optionnel) Créer un superutilisateur**

```bash
uv run python manage.py createsuperuser
```

**6. Démarrer le serveur Django**

```bash
uv run python manage.py runserver
```

**7. Lancer le frontend Dash**

```bash
uv run python eu_fact_force/dash-app/app.py
```

Puis ouvrir : http://127.0.0.1:8050/

Pour utiliser le JSON par défaut (`default_search.json`) côté backend, définir dans `.env` :
```
FLAG_RETRIEVE_DEFAULT_JSON=1
```

## Seeding the database

The `seed_db` management command populates the database with scientific articles. It supports two input modes.

**From a CSV of DOIs** (fetches PDFs from the internet):

```bash
uv run python manage.py seed_db --csv data/seed/vaccine_autism_evidence_curated.csv
```

The CSV must have a `doi` column. An optional `pdf_url` column can provide a direct download link. A curated list of vaccine/autism articles is included at `data/seed/vaccine_autism_evidence_curated.csv`.

**From a zip archive of pre-downloaded PDFs** (skips the download step):

```bash
uv run python manage.py seed_db --zip archive.zip
```

The DOI is extracted automatically from the text of each PDF (first 3 pages). PDFs where no DOI can be found are skipped and reported. Metadata is still fetched from the API using the extracted DOI.

**Dry run** (preview without writing to the database):

```bash
uv run python manage.py seed_db --csv data/seed/vaccine_autism_evidence_curated.csv --dry-run
uv run python manage.py seed_db --zip archive.zip --dry-run
```

Duplicate DOIs (already in the database or repeated in the input) are skipped and reported without causing the command to fail.