import json
from dash import dcc

from .colors import EUPHAColors

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
