import base64
import io
import json
import uuid
import requests
from pathlib import Path

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.io as pio
from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
from pages import graph, ingest, readme
from utils.colors import EUPHAColors
from utils.graph import BackendGraph, format_node_metadata
from utils.parsing import extract_pdf_metadata

plotly_template = Path(__file__).parent / "assets/template.json"
with plotly_template.open() as f:
    debate_template = json.load(f)
pio.templates["app_template"] = go.layout.Template(debate_template)
pio.templates.default = "app_template"

# Dash app
app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=["custom.css", dbc.themes.BOOTSTRAP],
)

# Dash params
DASHBOARD_NAME = "EU Fact Force"

# Custom dash app tab and logo
app.title = DASHBOARD_NAME
app._favicon = "logo-eupha-u-blue.png"

# App pages
pages = {
    "Readme": {"href": "/", "content": readme},
    "Ingestion": {"href": "/ingest", "content": ingest},
    "Graph": {"href": "/graph", "content": graph},
}

# Header and navigation
nav_pages = [
    dbc.NavLink(
        page,
        href=pages[page]["href"],
        style={"color": EUPHAColors.white},
        active="exact",
    )
    for page in pages
]

nav_col = dbc.Col(
    [dbc.Nav(nav_pages, vertical=False, pills=True, justified=True)],
    width=4,
    align="center",
    style={"padding": "0rem"},
)

header = html.Div(
    dbc.Row(
        [
            dbc.Col(
                html.Div(
                    [
                        html.Img(
                            src="assets/logo-eupha-white.png",
                            alt="image",
                            height=50,
                            style={"padding-right": "10px"},
                        ),
                        html.H1(
                            DASHBOARD_NAME,
                            style={
                                "color": EUPHAColors.white,
                                "font-weight": "bold",
                                "margin": "0",
                                "padding": "0",
                            },
                        ),
                    ],
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "gap": "0px",
                    },
                ),
                width=4,
            ),
            nav_col,
            dbc.Col(
                html.Div(
                    [
                        html.Img(
                            src="assets/logo-d4g.png",
                            alt="image",
                            height=50,
                            style={"padding-right": "10px"},
                        )
                    ],
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "gap": "0px",
                    },
                ),
                width=4,
                className="d-grid gap-2 d-md-flex justify-content-md-end",
            ),
        ],
        className="g-0",
    ),
    style={
        "padding": "1rem",
        "background-color": EUPHAColors.dark_blue,
        "position": "fixed",
        "width": "100%",
        "zIndex": 1000,
    },
)

# Content
content = html.Div(
    style={
        "margin-left": "1rem",
        "margin-right": "1rem",
        "padding": "1rem",
        "padding-top": "120px",
    },
    id="page-content",
)

# Storage
store = html.Div([dcc.Store(id="store-search")])


# Layout
app.layout = html.Div([dcc.Location(id="url", refresh=False), header, content, store])


# --------------------
# Callbacks - General
# --------------------


# Routing
@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    for page in pages:
        if pages[page]["href"] == pathname:
            return pages[page]["content"].make_layout()

    return html.Div("404 - Page not found")


# --------------------
# Callbacks - Graph
# --------------------


# Callback search button activate
@app.callback(
    Output("search-button", "disabled"),
    inputs=[Input("search-input", "value"), Input("graph", "children")],
)
def activate_search_buton(search_text, graph):
    if search_text is None or search_text == "":
        return True
    else:
        return False


# Callback search data
@app.callback(
    [
        Output("store-search", "data"),
        Output("results", "style"),
        Output("search-input", "value"),
        Output("filter_node_types", "options"),
        Output("filter_chunk_types", "options"),
        Output("filter_keywords", "options"),
        Output("filter_documents", "options"),
        Output("filter_journals", "options"),
        Output("filter_authors", "options"),
        Output("filter_dates", "min_date_allowed"),
        Output("filter_dates", "max_date_allowed"),
        Output("filter_node_types", "value"),
        Output("filter_chunk_types", "value"),
        Output("filter_keywords", "value"),
        Output("filter_documents", "value"),
        Output("filter_journals", "value"),
        Output("filter_authors", "value"),
        Output("filter_dates", "start_date"),
        Output("filter_dates", "end_date"),
    ],
    inputs=[Input("search-button", "n_clicks")],
    state=[State("search-input", "value")],
    prevent_updates=True,
)
def get_search_data(n_clicks, search_text):
    if n_clicks > 0:
        nodes, edges, filters = BackendGraph(search_text).transform()
        return [
            {"nodes": nodes, "edges": edges},
            {
                "display": "block",
                "border-radius": "15px",
                "padding": "20px",
                "background-color": EUPHAColors.white,
            },
            "",
            list(set(filters["node_types"])),
            list(set(filters["chunk_types"])),
            list(set(filters["keywords"])),
            list(set(filters["documents"])),
            list(set(filters["journal"])),
            list(set(filters["authors"])),
            min(filters["date"]) if filters["date"] else None,
            max(filters["date"]) if filters["date"] else None,
            list(set(filters["node_types"])),
            list(set(filters["chunk_types"])),
            list(set(filters["keywords"])),
            list(set(filters["documents"])),
            list(set(filters["journal"])),
            list(set(filters["authors"])),
            min(filters["date"]) if filters["date"] else None,
            max(filters["date"]) if filters["date"] else None,
        ]
    else:
        raise PreventUpdate


# Callback update graph and list
@app.callback(
    [
        Output("graph-cytoscape", "elements"),
        Output("list-elements", "children"),
        Output("graph", "style"),
    ],
    inputs=[
        Input("store-search", "data"),
        Input("filter_node_types", "value"),
        Input("filter_chunk_types", "value"),
        Input("filter_keywords", "value"),
        Input("filter_documents", "value"),
        Input("filter_journals", "value"),
        Input("filter_authors", "value"),
        Input("filter_dates", "start_date"),
        Input("filter_dates", "end_date"),
    ],
    prevent_updates=True,
)
def update_graph_and_list(
    store_search,
    filter_node_types,
    filter_chunk_types,
    filter_keywords,
    filter_documents,
    filter_journals,
    filter_authors,
    start_date,
    end_date,
):
    if store_search is None:
        raise PreventUpdate
    else:
        # Search data
        nodes = store_search["nodes"]
        edges = store_search["edges"]

        # Filter node type
        nodes = {
            n: nodes[n] for n in nodes if nodes[n]["data"]["type"] in filter_node_types
        }

        # Filter chunk type
        nodes = {
            n: nodes[n]
            for n in nodes
            if nodes[n]["data"]["type"] != "chunk"
            or nodes[n]["data"]["metadata"]["type"] in filter_chunk_types
        }

        # Filter keywords
        nodes = {
            n: nodes[n]
            for n in nodes
            if nodes[n]["data"]["type"] not in ("chunk", "document", "keyword")
            or (
                nodes[n]["data"]["type"] == "chunk"
                and any(
                    item in filter_keywords
                    for item in nodes[n]["data"]["document_metadata"].get("keywords", [])
                )
            )
            or (
                nodes[n]["data"]["type"] == "document"
                and any(
                    item in filter_keywords
                    for item in nodes[n]["data"]["metadata"].get("keywords", [])
                )
            )
            or (
                nodes[n]["data"]["type"] == "keyword"
                and nodes[n]["data"]["label"] in filter_keywords
            )
        }

        # Filter dates
        nodes = {
            n: nodes[n]
            for n in nodes
            if nodes[n]["data"]["type"] not in ("chunk", "document")
            or (
                nodes[n]["data"]["type"] == "chunk"
                and nodes[n]["data"]["document_metadata"]["date"] >= start_date
                and nodes[n]["data"]["document_metadata"]["date"] <= end_date
            )
            or (
                nodes[n]["data"]["type"] == "document"
                and nodes[n]["data"]["metadata"]["date"] >= start_date
                and nodes[n]["data"]["metadata"]["date"] <= end_date
            )
        }

        # Filter documents
        nodes = {
            n: nodes[n]
            for n in nodes
            if nodes[n]["data"]["type"] not in ("chunk", "document")
            or (
                nodes[n]["data"]["type"] == "chunk"
                and str(nodes[n]["data"]["metadata"].get("metadata", {}).get("document_id"))
                in filter_documents
            )
            or (
                nodes[n]["data"]["type"] == "document"
                and nodes[n]["data"]["id"] in filter_documents
            )
        }

        # Filter journals
        nodes = {
            n: nodes[n]
            for n in nodes
            if nodes[n]["data"]["type"] not in ("chunk", "document", "journal")
            or (
                nodes[n]["data"]["type"] == "chunk"
                and nodes[n]["data"]["document_metadata"]["journal"] in filter_journals
            )
            or (
                nodes[n]["data"]["type"] == "document"
                and nodes[n]["data"]["metadata"]["journal"] in filter_journals
            )
            or (
                nodes[n]["data"]["type"] == "journal"
                and nodes[n]["data"]["label"] in filter_journals
            )
        }

        # Filter authors
        nodes = {
            n: nodes[n]
            for n in nodes
            if nodes[n]["data"]["type"] not in ("chunk", "document", "author")
            or (
                nodes[n]["data"]["type"] == "chunk"
                and any(
                    item in filter_authors
                    for item in nodes[n]["data"]["document_metadata"]["authors"]
                )
            )
            or (
                nodes[n]["data"]["type"] == "document"
                and any(
                    item in filter_authors
                    for item in nodes[n]["data"]["metadata"]["authors"]
                )
            )
            or (
                nodes[n]["data"]["type"] == "author"
                and nodes[n]["data"]["label"] in filter_authors
            )
        }

        # Update edges
        edges = [
            e
            for e in edges
            if e["data"]["source"] in nodes and e["data"]["target"] in nodes
        ]

        # Clean nodes without any edge
        nodes = {
            n: nodes[n]
            for n in nodes
            if any(n == e["data"]["source"] or n == e["data"]["target"] for e in edges)
        }

        # Graph elements
        graph_elements = [nodes[x] for x in nodes] + edges

        # List elements
        list_elements = [x["data"] for x in graph_elements if "id" in x["data"]]
        list_elements = sorted(list_elements, key=lambda x: x["id"])
        return [
            graph_elements,
            dbc.Accordion(
                [
                    dbc.AccordionItem(
                        format_node_metadata(x),
                        title=x["label"].replace("_", " ").title(),
                    )
                    for x in list_elements
                ],
                start_collapsed=True,
            ),
            {
                "border-radius": "15px",
                "padding": "20px",
                "background-color": EUPHAColors.white,
                "display": "block",
            },
        ]


# Callback focus selected element
@app.callback(
    [
        Output("offcanvas", "is_open"),
        Output("offcanvas", "children"),
    ],
    inputs=[Input("graph-cytoscape", "tapNodeData")],
    state=[State("offcanvas", "is_open")],
    prevent_initial_call=True,
)
def toggle_offcanvas(node_data, is_open):
    if node_data:
        return [not is_open, format_node_metadata(node_data)]


# --------------------
# Callbacks - Ingest
# --------------------

### Create here callbacks for ingestions


@app.callback(
    Output("input-doi", "value"),
    Output("input-abstract", "value"),
    Output("input-journal", "value"),
    Output("input-date", "value"),
    Output("input-link", "value"),
    Output("input-title", "value"),
    Output("session-store", "data"),
    Input("upload-pdf", "contents"),
)
def handle_pdf_upload(contents):

    if contents is None:
        return no_update, no_update, no_update, no_update, no_update, no_update, {}

    # decoding of passed PDFs
    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)

    # extract_pdf_metadata call
    metadata = extract_pdf_metadata(io.BytesIO(decoded))

    return (
        metadata.get("doi", ""),
        metadata.get("abstract", ""),
        metadata.get("journal", ""),
        metadata.get("publication_date", ""),
        metadata.get("article_link", ""),
        metadata.get("title", ""),
        metadata,
    )


@app.callback(
    Output("authors-container", "children"),
    Input("btn-add-author", "n_clicks"),
    Input({"type": "remove-author", "index": ALL}, "n_clicks"),
    Input("session-store", "data"),
    State({"type": "auth-name", "index": ALL}, "value"),
    State({"type": "auth-surname", "index": ALL}, "value"),
    State({"type": "auth-email", "index": ALL}, "value"),
    State({"type": "auth-name", "index": ALL}, "id"),
)
def update_authors_list(
    add_clicks, remove_clicks, metadata, names, surnames, emails, ids
):
    triggered = ctx.triggered_id

    # on a new pdf uplaod
    if triggered == "session-store" and metadata:
        authors = metadata.get("authors", [])
        return [
            ingest.add_author_line(
                str(uuid.uuid4()),
                a.get("name", ""),
                a.get("surname", ""),
                a.get("email", ""),
            )
            for a in authors
        ]

    # reconstructing authors list
    current_authors = []
    if ids:
        for idx_id, name, surname, email in zip(ids, names, surnames, emails):
            current_authors.append(
                {
                    "index": idx_id["index"],
                    "name": name or "",
                    "surname": surname or "",
                    "email": email or "",
                }
            )

    # if missing author
    if triggered == "btn-add-author":
        current_authors.append(
            {"index": str(uuid.uuid4()), "name": "", "surname": "", "email": ""}
        )

    # remove blank/irrelevant author field
    if isinstance(triggered, dict) and triggered.get("type") == "remove-author":
        remove_index = triggered.get("index")
        current_authors = [a for a in current_authors if a["index"] != remove_index]

    return [
        ingest.add_author_line(a["index"], a["name"], a["surname"], a["email"])
        for a in current_authors
    ]


@app.callback(
    Output("input-doi", "disabled"),
    Output("input-abstract", "disabled"),
    Output("input-journal", "disabled"),
    Output("input-date", "disabled"),
    Output("input-link", "disabled"),
    Output("input-category", "disabled"),
    Output("input-type", "disabled"),
    Output("input-title", "disabled"),
    Input("chk-meta-correct", "value"),
)
def lock_metadata(is_correct):
    val = bool(is_correct)
    return val, val, val, val, val, val, val, val


@app.callback(
    Output({"type": "auth-name", "index": ALL}, "disabled"),
    Output({"type": "auth-surname", "index": ALL}, "disabled"),
    Output({"type": "auth-email", "index": ALL}, "disabled"),
    Output({"type": "remove-author", "index": ALL}, "disabled"),
    Output("btn-add-author", "disabled"),
    Input("chk-authors-correct", "value"),
    State({"type": "auth-name", "index": ALL}, "id"),
)
def lock_authors(is_correct, ids):
    is_corr = bool(is_correct)
    if not ids:
        return [], [], [], [], is_corr
    length = len(ids)
    return (
        [is_corr] * length,
        [is_corr] * length,
        [is_corr] * length,
        [is_corr] * length,
        is_corr,
    )


@app.callback(
    Output("final-output", "children"),
    Input("btn-final-upload", "n_clicks"),
    State("upload-pdf", "contents"),
    State("input-doi", "value"),
    State("input-abstract", "value"),
    State("input-journal", "value"),
    State("input-date", "value"),
    State("input-link", "value"),
    State("input-category", "value"),
    State("input-type", "value"),
    State("input-title", "value"),
    State({"type": "auth-name", "index": ALL}, "value"),
    State({"type": "auth-surname", "index": ALL}, "value"),
    State({"type": "auth-email", "index": ALL}, "value"),
    prevent_initial_call=True,
)
def finalize_and_display_json(
    n_clicks,
    pdf_contents,
    doi,
    abstract,
    journal,
    date,
    link,
    category,
    study_type,
    title,
    names,
    surnames,
    emails,
):

    authors_list = [
        {"name": n, "surname": s, "email": e}
        for n, s, e in zip(names, surnames, emails)
        if n or s
    ]

    metadata_json = {
        "title": title,
        "category": category,
        "study_type": study_type,
        "journal": journal,
        "publication_year": date,
        "doi": doi,
        "article_link": link,
        "abstract": abstract,
        "authors": authors_list,
    }

    if not pdf_contents:
        return html.Div([dbc.Alert("Missing PDF file. Please upload a file first.", color="danger")])

    content_type, content_string = pdf_contents.split(",")
    decoded = base64.b64decode(content_string)

    api_url = "http://127.0.0.1:8000/ingestion/api/dash_upload/"
    files = {"pdf": ("uploaded_article.pdf", io.BytesIO(decoded), "application/pdf")}
    data = {"metadata": json.dumps(metadata_json)}

    try:
        response = requests.post(api_url, files=files, data=data, timeout=300)
        response_data = response.json()
        if response.status_code == 200 and response_data.get("success"):
            return html.Div(
                [
                    dbc.Alert("Successfully contributed, thank you!", color="success"),
                    html.H4("Ingestion Successful"),
                    html.P(f"Document ID: {response_data.get('document_pk')} | Elements Extracted: {response_data.get('chunks_count')}"),
                ]
            )
        else:
            return html.Div([dbc.Alert(f"Server Error: {response_data.get('error', 'Unknown error')}", color="danger")])
    except Exception as e:
        return html.Div([dbc.Alert(f"Connection Error: {str(e)}", color="danger")])


if __name__ == "__main__":
    app.run(debug=True)
