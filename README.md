# EU Fact Force

This file will become your README and also the index of your
documentation.


# Contributing

## Project structure

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

## Installation

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

Ou alors, utilisez la commande `uv run ...` (au lieu de `python ...`) pour lancer un script Python. Par exemple:

```bash
uv run pipelines/run.py run build_database
```


## Lancer les precommit-hook localement

[Installer les precommit](https://pre-commit.com/)

    pre-commit run --all-files

## Utiliser Tox pour tester votre code

    tox -vv
