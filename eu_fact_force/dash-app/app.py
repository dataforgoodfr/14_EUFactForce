from dash import Dash, dcc, html, Input, Output, State, ALL, ctx, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

import plotly.io as pio
import plotly.graph_objects as go

# PDF ingestion
import base64
import io
import json
import os
from pathlib import Path
import requests
import uuid

from utils.colors import EUPHAColors
from utils.graph import TestGraph
from utils.parsing import extract_pdf_metadata
from pages import readme, ingest, graph

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Plotly template
with open(Path(__file__).parent / "assets/template.json", "r") as f:
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

# Backend URL
DJANGO_URL = os.getenv("DJANGO_URL")
if not DJANGO_URL:
    raise RuntimeError("DJANGO_URL environment variable in .env is required")

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


# Layout
app.layout = html.Div([dcc.Location(id="url", refresh=False), header, content])


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


# Callback update graph
@app.callback(
    [
        Output("graph-cytoscape", "elements"),
        Output("list-elements", "children"),
        Output("graph", "style"),
        Output("list", "style"),
        Output("search-input", "value"),
    ],
    inputs=[Input("search-button", "n_clicks")],
    state=[State("search-input", "value")],
    prevent_updates=True,
)
def update_graph(n_clicks, search_text):
    if n_clicks > 0:
        # Graph generator
        graph_elements = RandomGraphGenerator().get_graph_data()
        list_elements = [x["data"] for x in graph_elements if "id" in x["data"]]
        list_elements = sorted(list_elements, key=lambda x: x["id"])
        return [
            graph_elements,
            dbc.Accordion(
                [
                    dbc.AccordionItem(
                        dcc.Markdown(
                            "\n".join(
                                [f"- {key.capitalize()} : __{x[key]}__" for key in x]
                            )
                        ),
                        title=x["label"],
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
            {
                "border-radius": "15px",
                "padding": "20px",
                "background-color": EUPHAColors.white,
                "display": "block",
            },
            "",
        ]
    else:
        raise PreventUpdate


# Callback show selected element
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
        return [
            not is_open,
            dcc.Markdown(
                "\n".join(
                    [
                        f"- {key.capitalize()} : __{node_data[key]}__"
                        for key in node_data
                        if key != "timeStamp"
                    ]
                )
            ),
        ]


# --------------------
# Callbacks - Ingest
# --------------------

### Create here callbacks for ingestions

@app.callback(
    Output('input-doi', 'value'),
    Output('input-abstract', 'value'),
    Output('input-journal', 'value'),
    Output('input-date', 'value'),
    Output('input-link', 'value'),
    Output('input-title', 'value'),
    Output('session-store', 'data'),
    Input('upload-pdf', 'contents')
)
def handle_pdf_upload(contents):

    if contents is None:
        return no_update, no_update, no_update, no_update, no_update, no_update, {}

    # decoding of passed PDFs
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    # extract_pdf_metadata call
    metadata = extract_pdf_metadata(io.BytesIO(decoded))

    return (
        metadata.get('doi', ''),
        metadata.get('abstract', ''),
        metadata.get('journal', ''),
        metadata.get('publication_date', ''),
        metadata.get('article_link', ''),
        metadata.get('title', ''),
        metadata
    )
@app.callback(
    Output('authors-container', 'children'),
    Input('btn-add-author', 'n_clicks'),
    Input({'type': 'remove-author', 'index': ALL}, 'n_clicks'),
    Input('session-store', 'data'),
    State({'type': 'auth-name', 'index': ALL}, 'value'),
    State({'type': 'auth-surname', 'index': ALL}, 'value'),
    State({'type': 'auth-email', 'index': ALL}, 'value'),
    State({'type': 'auth-name', 'index': ALL}, 'id'),
)
def update_authors_list(add_clicks, remove_clicks, metadata, names, surnames, emails, ids):
    triggered = ctx.triggered_id

    # on a new pdf uplaod
    if triggered == 'session-store' and metadata:
        authors = metadata.get('authors', [])
        return [ingest.add_author_line(str(uuid.uuid4()), a.get('name', ''), a.get('surname', ''), a.get('email', '')) for a in authors]

    # reconstructing authors list
    current_authors = []
    if ids:
        for idx_id, name, surname, email in zip(ids, names, surnames, emails):
            current_authors.append({
                'index': idx_id['index'],
                'name': name or "",
                'surname': surname or "",
                'email': email or ""
            })

    # if missing author
    if triggered == 'btn-add-author':
        current_authors.append({
            'index': str(uuid.uuid4()),
            'name': "",
            'surname': "",
            'email': ""
        })

    # remove blank/irrelevant author field
    if isinstance(triggered, dict) and triggered.get('type') == 'remove-author':
        remove_index = triggered.get('index')
        current_authors = [a for a in current_authors if a['index'] != remove_index]

    return [ingest.add_author_line(a['index'], a['name'], a['surname'], a['email']) for a in current_authors]


@app.callback(
    Output('input-doi', 'disabled'),
    Output('input-abstract', 'disabled'),
    Output('input-journal', 'disabled'),
    Output('input-date', 'disabled'),
    Output('input-link', 'disabled'),
    Output('input-category', 'disabled'),
    Output('input-type', 'disabled'),
    Output('input-title', 'disabled'),
    Input('chk-meta-correct', 'value')
)
def lock_metadata(is_correct):
    val = bool(is_correct)
    return val, val, val, val, val, val, val, val


@app.callback(
    Output({'type': 'auth-name', 'index': ALL}, 'disabled'),
    Output({'type': 'auth-surname', 'index': ALL}, 'disabled'),
    Output({'type': 'auth-email', 'index': ALL}, 'disabled'),
    Output({'type': 'remove-author', 'index': ALL}, 'disabled'),
    Output('btn-add-author', 'disabled'),
    Input('chk-authors-correct', 'value'),
    State({'type': 'auth-name', 'index': ALL}, 'id')
)
def lock_authors(is_correct, ids):
    is_corr = bool(is_correct)
    if not ids:
        return [], [], [], [], is_corr
    length = len(ids)
    return [is_corr]*length, [is_corr]*length, [is_corr]*length, [is_corr]*length, is_corr


@app.callback(
    Output('final-output', 'children'),
    Input('btn-final-upload', 'n_clicks'),
    State('upload-pdf', 'contents'),
    State('upload-pdf', 'filename'),
    State('input-doi', 'value'),
    State('input-abstract', 'value'),
    State('input-journal', 'value'),
    State('input-date', 'value'),
    State('input-link', 'value'),
    State('input-category', 'value'),
    State('input-type', 'value'),
    State('input-title', 'value'),
    State({'type': 'auth-name', 'index': ALL}, 'value'),
    State({'type': 'auth-surname', 'index': ALL}, 'value'),
    State({'type': 'auth-email', 'index': ALL}, 'value'),
    prevent_initial_call=True
)
def finalize_and_send(n_clicks, pdf_base64, filename, doi, abstract, journal, date, link, category, study_type, title, names, surnames, emails):
    # Assertion pdf_base64 <- 'contents' and filename <- 'filename'

    if not n_clicks or pdf_base64 is None:
        return no_update

    print(f"Attempting upload for: {filename}") # Server log to verify data upload

    authors_list = [
        {"name": n, "surname": s, "email": e}
        for n, s, e in zip(names, surnames, emails) if n or s
    ]

    metadata_payload = {
        "title": title,
        "category": category,
        "study_type": study_type,
        "journal": journal,
        "publication_year": date,
        "doi": doi,
        "article_link": link,
        "abstract": abstract,
        "authors": authors_list
    }

    try:
        # Decode the PDF content from base64
        content_type, content_string = pdf_base64.split(',')
        pdf_bytes = base64.b64decode(content_string)

        # API call to Django backend
        url = DJANGO_URL + "/ingestion/api/upload/"

        files = {
            'file': (filename, pdf_bytes, 'application/pdf')
        }
        data = {
            'metadata': json.dumps(metadata_payload)
        }

        # Timeout set to allow sync embedding in backend
        # Consider async for prod
        response = requests.post(url, files=files, data=data, timeout=70)

        if response.status_code == 201:
            return dbc.Alert(f"Success ! {metadata_payload['title']} has been uploaded.", color="success")
        else:
            return dbc.Alert(f"Erreur API : {response.text}", color="danger")

    except Exception as e:
        print(f"Detailed error: {str(e)}") # Visible dans ton terminal Dash
        return dbc.Alert(f"Uploading error: {str(e)}", color="danger")

if __name__ == "__main__":
    app.run(debug=True)
