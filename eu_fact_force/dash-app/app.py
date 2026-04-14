from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.io as pio
import plotly.graph_objects as go

import json

from utils.colors import EUPHAColors
from utils.graph import RandomGraphGenerator
from pages import readme, ingest, graph

# Plotly template
with open("assets/template.json", "r") as f:
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


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8050)