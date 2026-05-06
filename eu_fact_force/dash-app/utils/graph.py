import os
import requests
from dash import html
import dash_bootstrap_components as dbc
from .colors import EUPHAColors

dict_node_type_colors = {
    "chunk": EUPHAColors.light_green,
    "document": EUPHAColors.orange,
    "author": EUPHAColors.secondary,
    "journal": EUPHAColors.primary,
    "keyword": EUPHAColors.dark_green,
}

stylesheet = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "text-valign": "center",
            "text-halign": "center",
            "color": "#2c3e50",
            "font-size": 10,
            "text-wrap": "wrap",
            "text-max-width": 80,
        },
    },

    # KEYWORD (most important)
    {
        "selector": 'node[type="keyword"]',
        "style": {
            "background-color": dict_node_type_colors["keyword"],
            "width": "90px",
            "height": "90px",
            "font-size": "16px",
            "color": EUPHAColors.white,
            "border-width": 3,
            "border-color": "#1b5e20",
        },
    },

    # DOCUMENT
    {
        "selector": 'node[type="document"]',
        "style": {
            "background-color": dict_node_type_colors["document"],
            "width": "75px",
            "height": "75px",
            "font-size": "13px",
        },
    },

    # CHUNK
    {
        "selector": 'node[type="chunk"]',
        "style": {
            "background-color": dict_node_type_colors["chunk"],
            "width": "55px",
            "height": "55px",
            "font-size": "11px",
            "opacity": 0.9,
        },
    },

    # AUTHOR
    {
        "selector": 'node[type="author"]',
        "style": {
            "background-color": dict_node_type_colors["author"],
            "width": "30px",
            "height": "30px",
            "opacity": 0.7,
        },
    },

    # JOURNAL (least important)
    {
        "selector": 'node[type="journal"]',
        "style": {
            "background-color": dict_node_type_colors["journal"],
            "width": "25px",
            "height": "25px",
            "opacity": 0.5,
        },
    },

    {
        "selector": "edge",
        "style": {
            "width": 1,
            "line-color": EUPHAColors.primary,
            "opacity": 0.4,
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
        base_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
        url = f"{base_url}/ingestion/search/{self.keyword}/"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            self.search_results = response.json()
        except Exception:
            # Fallback/Mock data if backend is down (to prevent app crash during design)
            self.search_results = {"chunks": [], "documents": {}, "authors": {}}

    def transform(self):
        nodes = {}
        edges = []
        authors_dict = self.search_results.get("authors", {})
        filters = {
            "node_types": list(dict_node_type_colors.keys()),
            "chunk_types": [], "documents": [], "journal": [], 
            "keywords": [], "authors": [], "date": [],
        }

        for i, chunk in enumerate(self.search_results.get("chunks", [])):
            chunk_id = f"chunk_{i}"
            document_id = str(chunk["metadata"]["document_id"])
            document_metadata = self.search_results["documents"].get(document_id, {})
            
            filters["chunk_types"].append(chunk.get("type"))
            filters["documents"].append(document_id)

            if document_metadata.get("date"):
                filters["date"].append(document_metadata["date"])
            
            author_names = [authors_dict.get(str(a_id), {}).get("name") for a_id in document_metadata.get("author_ids", [])]
            document_metadata["author_names"] = [name for name in author_names if name]

            nodes[chunk_id] = {
                "data": {"id": chunk_id, "label": chunk_id.replace("_", " ").capitalize(), "type": "chunk", "metadata": chunk, "document_metadata": document_metadata}
            }

            if str(document_id) not in nodes:
                document_label = document_metadata.get("title", f"Doc {document_id}")
                if len(document_label) > 25:
                    document_label = document_label[:25] + "..."
                nodes[str(document_id)] = {
                    "data": {"id": str(document_id), "label": document_label, "type": "document", "metadata": document_metadata}
                }

            edges.append({"data": {"source": chunk_id, "target": str(document_id)}})

            if document_metadata.get("journal"):
                journal_id = f"journal_{document_metadata['journal']}"
                filters["journal"].append(document_metadata["journal"])
                if journal_id not in nodes:
                    nodes[journal_id] = {"data": {"id": journal_id, "label": document_metadata["journal"], "type": "journal"}}
                edges.append({"data": {"source": str(document_id), "target": journal_id}})

            for author_id in document_metadata.get("author_ids", []):
                author_data = authors_dict.get(str(author_id), {})
                author_name = author_data.get("name", f"Author {author_id}")
                node_id = f"author_{author_id}"
                filters["authors"].append(author_name)
                if node_id not in nodes:
                    nodes[node_id] = {"data": {"id": node_id, "label": author_name, "type": "author", "metadata": author_data}}
                edges.append({"data": {"source": str(document_id), "target": node_id}})

            for keyword in document_metadata.get("keywords", []):
                keyword_id = f"keyword_{keyword}"
                filters["keywords"].append(keyword)
                if keyword_id not in nodes:
                    nodes[keyword_id] = {"data": {"id": keyword_id, "label": keyword, "type": "keyword"}}
                edges.append({"data": {"source": str(document_id), "target": keyword_id}})

        return nodes, edges, filters

def format_node_metadata(node_data):
    if node_data["type"] == "document":
        return html.Div([
            html.H4(node_data['metadata'].get('title', 'Untitled'), className="fw-bold mb-2", style={"color": EUPHAColors.text_dark}),
            html.P(", ".join(node_data["metadata"].get("author_names", [])), className="text-muted fst-italic mb-3"),
            html.Div([dbc.Badge(x, color="light", text_color="dark", className="me-1 border") for x in node_data["metadata"].get("keywords", [])], className="mb-4"),
            dbc.Button("Access Source Document ↗", href=f"http://doi.org/{node_data['metadata'].get('doi', '')}", target="_blank", color="primary", outline=True, size="sm")
        ])

    elif node_data["type"] == "chunk":
        score = round(node_data['metadata'].get('score', 0), 2)
        return html.Div([
            html.H5("Extracted Segment", className="fw-bold mb-1", style={"color": EUPHAColors.text_dark}),
            html.P(f"Relevance Score: {score}", className="text-muted small mb-3"),
            
            html.Div(
                node_data["metadata"].get("content", ""),
                style={"fontStyle": "italic", "borderRadius": "8px", "padding": "15px", "backgroundColor": EUPHAColors.light_bg, "border": f"1px solid {EUPHAColors.border_color}", "fontSize": "14px", "color": EUPHAColors.text_main},
                className="mb-4"
            ),
            
            html.Hr(style={"borderColor": EUPHAColors.border_color}),
            html.H6("Source Document", className="fw-bold mt-4 mb-2"),
            html.P(node_data['document_metadata'].get('title', 'Unknown Title'), className="small mb-1"),
            html.P(", ".join(node_data["document_metadata"].get("author_names", [])), className="text-muted small fst-italic mb-3"),
            dbc.Button("Access Source Document ↗", href=f"http://doi.org/{node_data['document_metadata'].get('doi', '')}", target="_blank", color="primary", size="sm", className="w-100")
        ])

    elif node_data["type"] == "author":
        return html.Div([
            html.H4(node_data['metadata'].get('name', 'Unknown'), className="fw-bold mb-2", style={"color": EUPHAColors.text_dark}),
            html.P(f"ORCID: {node_data['metadata'].get('orcid', 'N/A')}", className="text-muted")
        ])

    elif node_data["type"] == "keyword":
        return html.Div([
            html.H4(node_data.get('label', ''), className="fw-bold mb-2", style={"color": EUPHAColors.text_dark}),
            html.P("Keyword Extracted", className="text-muted")
        ])
    
    return html.Div("No metadata available.")