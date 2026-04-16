import json
import os
from urllib.parse import urlparse

import psycopg2
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


class TestGraph:
    """Test graph object from static JSON file."""

    def __init__(self):
        self.load_search_results()
        self.stylesheet = stylesheet

    def load_search_results(self):
        """Load JSON file from data/"""
        with open("data/search_results.json", "r") as f:
            self.search_results = json.load(f)

    def transform(self):
        """Parse JSON file and create nodes (dict), edges (list) and filters (dict)."""
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
            document_id = chunk["metadata"]["document_id"]
            document_metadata = self.search_results["documents"][document_id]
            filters["chunk_types"].append(chunk["type"])
            filters["documents"].append(document_id)
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
                        "label": document_metadata["title"],
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
            # journal and authors
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
            for author in document_metadata["authors"]:
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
            for keyword in chunk["metadata"]["keywords"]:
                keyword_id = f"keyword_{keyword}"
                filters["keywords"].append(keyword)
                if keyword_id not in nodes:
                    nodes[keyword_id] = {
                        "data": {"id": keyword_id, "label": keyword, "type": "keyword"}
                    }
                edges.append(
                    {
                        "data": {
                            "source": chunk_id,
                            "target": keyword_id,
                        }
                    }
                )

        return nodes, edges, filters


class DBGraph:
    """Graph built from real DocumentChunk / Document rows in PostgreSQL."""

    def __init__(self, search_query: str):
        self.search_query = search_query.strip()
        self.stylesheet = stylesheet

    def _connect(self):
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise RuntimeError("DATABASE_URL is not set")
        p = urlparse(db_url)
        return psycopg2.connect(
            dbname=p.path.lstrip("/"),
            user=p.username,
            password=p.password,
            host=p.hostname,
            port=p.port or 5432,
        )

    def fetch_data(self):
        query = f"%{self.search_query}%"
        sql = """
            SELECT
                c.id, c.content, c."order",
                d.id, d.title, d.doi, d.created_at
            FROM ingestion_documentchunk c
            JOIN ingestion_document d ON c.document_id = d.id
            WHERE d.title ILIKE %(q)s OR c.content ILIKE %(q)s
            ORDER BY d.id, c."order"
            LIMIT 300
        """
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, {"q": query})
                return cur.fetchall()
        finally:
            conn.close()

    def transform(self):
        rows = self.fetch_data()
        nodes = {}
        edges = []
        filters = {
            "node_types": ["chunk", "document"],
            "chunk_types": [],
            "documents": [],
            "journal": [],
            "keywords": [],
            "authors": [],
            "date": [],
        }

        for chunk_id, content, order, doc_id, title, doi, created_at in rows:
            chunk_node_id = f"chunk_{chunk_id}"
            doc_node_id = f"doc_{doc_id}"
            date_str = created_at.strftime("%Y-%m-%d") if created_at else "2000-01-01"
            label = (content[:50] + "…") if len(content) > 50 else content

            filters["chunk_types"].append("text")
            filters["documents"].append(doc_node_id)
            filters["date"].append(date_str)

            nodes[chunk_node_id] = {
                "data": {
                    "id": chunk_node_id,
                    "label": label,
                    "type": "chunk",
                    "metadata": {
                        "type": "text",
                        "content": content,
                        "metadata": {
                            "document_id": doc_node_id,
                            "keywords": [],
                        },
                    },
                    "document_metadata": {
                        "date": date_str,
                        "journal": "",
                        "authors": [],
                        "title": title,
                    },
                }
            }

            if doc_node_id not in nodes:
                nodes[doc_node_id] = {
                    "data": {
                        "id": doc_node_id,
                        "label": title,
                        "type": "document",
                        "metadata": {
                            "title": title,
                            "doi": doi or "",
                            "date": date_str,
                            "journal": "",
                            "authors": [],
                        },
                    }
                }

            edges.append({"data": {"source": chunk_node_id, "target": doc_node_id}})

        if not filters["date"]:
            filters["date"] = ["2000-01-01"]

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
