import os

import requests
from dash import dcc, html
import dash_bootstrap_components as dbc

from .colors import EUPHAColors

dict_node_type_colors = {
    "chunk": EUPHAColors.light_green,
    "document": EUPHAColors.orange,
    "author": EUPHAColors.light_blue,
    "journal": EUPHAColors.dark_blue,
    "keyword": EUPHAColors.dark_green,
}

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
            "background-color": dict_node_type_colors["chunk"],
            "width": "60px",
            "height": "60px",
            "font-size": "20px",
        },
    },
    {
        "selector": 'node[type="document"]',
        "style": {
            "background-color": dict_node_type_colors["document"],
            "width": "80px",
            "height": "80px",
            "font-size": "25px",
        },
    },
    {
        "selector": 'node[type="author"]',
        "style": {
            "background-color": dict_node_type_colors["author"],
            "width": "30px",
            "height": "30px",
        },
    },
    {
        "selector": 'node[type="journal"]',
        "style": {
            "background-color": dict_node_type_colors["journal"],
            "width": "30px",
            "height": "30px",
        },
    },
    {
        "selector": 'node[type="keyword"]',
        "style": {
            "background-color": dict_node_type_colors["keyword"],
            "width": "30px",
            "height": "30px",
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
        authors_dict = self.search_results.get("authors", {})
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
            document_metadata = self.search_results["documents"][str(document_id)]
            filters["chunk_types"].append(chunk["type"])
            filters["documents"].append(document_id)

            if document_metadata.get("date"):
                filters["date"].append(document_metadata["date"])
            author_names = [
                authors_dict.get(str(a_id), {}).get("name")
                for a_id in document_metadata.get("author_ids", [])
                ]
            document_metadata["author_names"] = [name for name in author_names if name]

            nodes[chunk_id] = {
                "data": {
                    "id": chunk_id,
                    "label": chunk_id.replace("_", " ").capitalize(),
                    "type": "chunk",
                    "metadata": chunk,
                    "document_metadata": document_metadata,
                }
            }

            if str(document_id) not in nodes:
                document_label = document_metadata.get("title", document_id)
                max_label_size = 25
                if len(document_label) > max_label_size:
                    document_label = document_label[:max_label_size] + "..."
                nodes[str(document_id)] = {
                    "data": {
                        "id": str(document_id),
                        "label": document_label,
                        "type": "document",
                        "metadata": document_metadata,
                    }
                }

            edges.append(
                {
                    "data": {
                        "source": chunk_id,
                        "target": str(document_id),
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
                            "source": str(document_id),
                            "target": journal_id,
                        }
                    }
                )

            # authors
            for author_id in document_metadata.get("author_ids", []):
                author_data = authors_dict.get(author_id, {})
                author_name = author_data.get("name", f"author_{author_id}")
                node_id = f"author_{author_id}"

                filters["authors"].append(author_name)

                if node_id not in nodes:
                    nodes[node_id] = {
                        "data": {
                            "id": node_id,
                            "label": author_name,
                            "type": "author",
                            "metadata": author_data,
                        }
                    }

                edges.append(
                    {
                        "data": {
                            "source": str(document_id),
                            "target": node_id,
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
                            "source": str(document_id),
                            "target": keyword_id,
                        }
                    }
                )

        return nodes, edges, filters


def format_node_metadata(node_data):
    """Format node metadata into card content"""

    # Document nodes
    if node_data["type"] == "document":
        return html.Div(
            [
                dbc.Row(
                    dcc.Markdown(f"__{node_data['metadata']['title']}__"),
                    style={"font-size": "20px"},
                ),
                dbc.Row(
                    dcc.Markdown(
                        ", ".join(
                            [f"_{x}_" for x in node_data["metadata"]["author_names"]]
                        )
                    )
                ),
                dbc.Row(
                    html.Span(
                        [
                            dbc.Badge(x, color="secondary", className="me-1")
                            for x in node_data["metadata"]["keywords"]
                        ]
                    )
                ),
                html.Br(),
                dbc.Button(
                    "Access document ↗️",
                    href=f"http://doi.org/{node_data['metadata']['doi']}",
                    target="_blank",
                    color="primary",
                    className="me-1",
                ),
            ]
        )

    # Chunk nodes
    elif node_data["type"] == "chunk":
        return html.Div(
            [
                dbc.Row(
                    dcc.Markdown(
                        f"__{node_data['label']}__ (score: {round(node_data['metadata']['score'], 2)})"
                    ),
                    style={"font-size": "20px"},
                ),
                dbc.Row(
                    node_data["metadata"]["content"],
                    style={
                        "font-style": "italic",
                        "border-radius": "15px",
                        "padding": "20px",
                        "background-color": EUPHAColors.light_green,
                    },
                ),
                html.Hr(),
                dbc.Row(
                    dcc.Markdown(f"__{node_data['document_metadata']['title']}__"),
                    style={"font-size": "20px"},
                ),
                dbc.Row(
                    dcc.Markdown(
                        ", ".join(
                            [
                                f"_{x}_"
                                for x in node_data["document_metadata"]["author_names"]
                            ]
                        )
                    )
                ),
                dbc.Row(
                    html.Span(
                        [
                            dbc.Badge(x, color="secondary", className="me-1")
                            for x in node_data["document_metadata"]["keywords"]
                        ]
                    )
                ),
                html.Br(),
                # dbc.Row(
                #     dcc.Markdown(f"Page: {node_data['metadata']['metadata']['page']}"),
                #     style={"font-size": "16px"},
                # ), # TODO: Use this when real page numbers available
                dbc.Button(
                    "Access document ↗️",
                    href=f"http://doi.org/{node_data['document_metadata']['doi']}",
                    target="_blank",
                    color="primary",
                    className="me-1",
                ),
            ]
        )

    # Author nodes
    elif node_data["type"] == "author":
        return html.Div(
            [
                dbc.Row(
                    dcc.Markdown(f"__{node_data['metadata']['name']}__"),
                    style={"font-size": "20px"},
                ),
                dbc.Row(
                    dcc.Markdown(f"ORCID: {node_data['metadata']['orcid']}"),
                    style={"font-size": "16px"},
                ),
            ]
        )

    # Keyword nodes
    elif node_data["type"] == "keyword":
        return html.Div(
            [
                dbc.Row(
                    dcc.Markdown(f"__{node_data['label']}__"),
                    style={"font-size": "20px"},
                ),
            ]
        )
    else:
        return dcc.Markdown(
            "\n".join(
                [
                    f"- {key.capitalize()} : __{node_data[key]}__"
                    for key in node_data
                    if key != "timeStamp"
                ]
            )
        )
