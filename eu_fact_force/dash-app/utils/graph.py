import os

import requests
from dash import dcc
from dotenv import load_dotenv

from .colors import EUPHAColors

# Load DATABASE_URL from project root .env when running the dash app standalone
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

stylesheet = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "text-valign": "center",
            "color": "black",
            "font-size": 10,
        },
    },
    {
        "selector": 'node[type="chunk"]',
        "style": {
            "background-color": EUPHAColors.light_green,
        },
    },
    {
        "selector": 'node[type="document"]',
        "style": {
            "background-color": EUPHAColors.orange,
        },
    },
    {
        "selector": 'node[type="author"]',
        "style": {
            "background-color": EUPHAColors.light_blue,
        },
    },
    {
        "selector": 'node[type="journal"]',
        "style": {
            "background-color": EUPHAColors.dark_blue,
        },
    },
    {
        "selector": 'node[type="keyword"]',
        "style": {
            "background-color": EUPHAColors.dark_green,
        },
    },
    {
        "selector": "edge",
        "style": {
            "width": 1,
            "line-color": "black",
        },
    },
]


class BackendGraph:
    """Graph object loaded from backend API."""

    def __init__(self, keyword):
        self.keyword = keyword
        self.load_search_results()
        self.stylesheet = stylesheet

    def load_search_results(self):
        """Load JSON from backend route."""
        base_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
        url = f"{base_url}/ingestion/search/{self.keyword}/"

        response = requests.get(url, timeout=30)
        response.raise_for_status()
        self.search_results = response.json()

    def transform(self):
        """Parse JSON and create nodes (dict), edges (list) and filters (dict)."""
        nodes = {}
        edges = []
        filters = {
            "node_types": [
                x["selector"].split('type="')[1].split('"')[0]
                for x in self.stylesheet
                if "type" in x["selector"]
            ],
            "chunk_types": [],
            "documents": [],
            "journal": [],
            "keywords": [],
            "authors": [],
            "date": [],
        }

        # chunks
        for i, chunk in enumerate(self.search_results["chunks"]):
            chunk_id = f"chunk_{i}"
            document_id = str(chunk["metadata"]["document_id"])
            document_metadata = self.search_results["documents"][document_id]
            filters["chunk_types"].append(chunk["type"])
            filters["documents"].append(document_id)

            if document_metadata.get("date"):
                filters["date"].append(document_metadata["date"])

            nodes[chunk_id] = {
                "data": {
                    "id": chunk_id,
                    "label": chunk_id,
                    "type": "chunk",
                    "metadata": chunk,
                    "document_metadata": document_metadata,
                }
            }

            if document_id not in nodes:
                nodes[document_id] = {
                    "data": {
                        "id": document_id,
                        "label": document_metadata.get("title", document_id),
                        "type": "document",
                        "metadata": document_metadata,
                    }
                }

            edges.append(
                {
                    "data": {
                        "source": chunk_id,
                        "target": document_id,
                    }
                }
            )

            # journal
            if document_metadata.get("journal"):
                journal_id = f"journal_{document_metadata['journal']}"
                filters["journal"].append(document_metadata["journal"])

                if journal_id not in nodes:
                    nodes[journal_id] = {
                        "data": {
                            "id": journal_id,
                            "label": document_metadata["journal"],
                            "type": "journal",
                        }
                    }

                edges.append(
                    {
                        "data": {
                            "source": document_id,
                            "target": journal_id,
                        }
                    }
                )

            # authors
            for author in document_metadata.get("authors", []):
                author_id = f"author_{author}"
                filters["authors"].append(author)

                if author_id not in nodes:
                    nodes[author_id] = {
                        "data": {"id": author_id, "label": author, "type": "author"}
                    }

                edges.append(
                    {
                        "data": {
                            "source": document_id,
                            "target": author_id,
                        }
                    }
                )

            # keywords
            for keyword in document_metadata.get("keywords", []):
                keyword_id = f"keyword_{keyword}"
                filters["keywords"].append(keyword)

                if keyword_id not in nodes:
                    nodes[keyword_id] = {
                        "data": {"id": keyword_id, "label": keyword, "type": "keyword"}
                    }

                edges.append(
                    {
                        "data": {
                            "source": document_id,
                            "target": keyword_id,
                        }
                    }
                )

        return nodes, edges, filters


def format_node_metadata(node_data):
    """Format node metadata into card content"""
    return dcc.Markdown(
        "\n".join(
            [
                f"- {key.capitalize()} : __{node_data[key]}__"
                for key in node_data
                if key != "timeStamp"
            ]
        )
    )