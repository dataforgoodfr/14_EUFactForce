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

### Déploiement de l'application

L'application se compose d'un serveur Django, d'une base PostgreSQL (avec pgvector) et de LocalStack pour le stockage S3.
Pour déployer et utiliser l'application en local :

**1. Prérequis**

- [Python 3.12+](https://www.python.org/) et [uv](https://docs.astral.sh/uv/)
- [Docker](https://www.docker.com/) et Docker Compose (pour Postgres et LocalStack)

**2. Variables d'environnement**

Copiez le fichier d'exemple et adaptez les valeurs si besoin :

```bash
cp .env.template .env
```

Pour un usage local avec les services Docker, les valeurs par défaut de `.env.template` (notamment `DATABASE_URL=postgresql://eu_fact_force:eu_fact_force@localhost:5432/eu_fact_force`) conviennent.

**3. Lancer les services (Postgres et LocalStack)**

À la racine du projet :

```bash
docker compose up -d
```

Cela démarre PostgreSQL (port 5432) et LocalStack S3 (port 4566). Le bucket configuré est créé automatiquement au démarrage de LocalStack.

**4. Installer les dépendances et appliquer les migrations**

```bash
uv sync
uv run python manage.py migrate
```

**5. (Optionnel) Créer un superutilisateur**

Pour accéder à l'interface d'administration Django :

```bash
uv run python manage.py createsuperuser
```

**6. Démarrer le serveur Django**

```bash
uv run python manage.py runserver
```

L'application est alors disponible sur [http://127.0.0.1:8000/](http://127.0.0.1:8000/). L'admin Django est accessible à [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/) si un superutilisateur a été créé.

**Utilisation du stockage S3 en local**

Pour que Django utilise LocalStack pour le stockage des fichiers, décommentez et renseignez dans `.env` les variables S3 (voir `.env.template`), par exemple :

```bash
USE_LOCAL_STACK=1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_STORAGE_BUCKET_NAME=eu-fact-force-files
AWS_S3_REGION_NAME=eu-west-1
```

Sans ces variables, l'application utilise le stockage fichier local par défaut.


**7. Démarrer la web-app d'ingestion vers le S3 local**

Pour rapatrier l'upload d'un couple PDF/métadatas :

***Lancer le containeur Docker***
```bash
docker compose up -d
```

Cela démarre PostgreSQL (port 5432) et LocalStack S3 (port 4566) et écoute sur
ce port.
Le bucket configuré est créé automatiquement au démarrage de LocalStack.

***Installer les dépendances et appliquer les migrations***

```bash
uv sync
uv run python manage.py migrate
```

***Lancer la Dash-app pour sauvegarder PDF & métadatas Localstack***

***Démarrer le serveur Django :***

```bash
uv run python manage.py runserver
```

***Démarrer la webapp Dash***

```bash
uv run python ingestion/front_upload/api_front_upload.py
```
