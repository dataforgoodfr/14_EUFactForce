from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.io as pio
import plotly.graph_objects as go
import dash_cytoscape as cyto

import json

from utils.colors import EUPHAColors
from utils.graph import RandomGraphGenerator

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

# Graph generator
generator = RandomGraphGenerator()

# Header
header = html.Div(
    dbc.Row(
        dbc.Col(
            html.Div(
                [
                    html.Img(src="assets/logo-eupha-white.png", alt="image", height=50, style={"padding-right": "10px"}),
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
            width=12,
        ),
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
search_bar = html.Div(
    children=[
        dbc.Row(
            [
                dbc.Col(
                    dbc.Input(
                        id="search-input",
                        placeholder="Disinformation narrative...",
                        style={"overflow": "hidden"},
                    )
                ),
                dbc.Col(
                    dbc.Button(
                        "Rechercher",
                        id="search-button",
                        color="primary",
                        className="me-1",
                        n_clicks=0,
                        disabled=True,
                    ),
                    width="auto",
                ),
            ],
            align="center",
        )
    ],
    id="search",
    style={
        "border-radius": "15px",
        "padding": "20px",
        "background-color": EUPHAColors.white,
    },
)

graph = html.Div(
    children=cyto.Cytoscape(
        id="graph-cytoscape",
        stylesheet=generator.stylesheet,
        layout={"name": "cose"},
        style={"width": "100%", "height": "400px"},
    ),
    id="graph",
    style={
        "border-radius": "15px",
        "padding": "20px",
        "background-color": EUPHAColors.light_blue,
        "display": "none",
    },
)

list_elements = html.Div(
    id="list",
    style={
        "border-radius": "15px",
        "padding": "20px",
        "background-color": EUPHAColors.light_blue,
        "display": "none",
    },
)

offcanevas = dbc.Offcanvas(
    id="offcanvas",
    title="Focus",
    is_open=False,
    placement="end",
    style={"width": "50%"},
)


content = html.Div(
    [search_bar, html.Br(), graph, html.Br(), list_elements, offcanevas],
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
# Callbacks
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
        Output("list", "children"),
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
        graph_elements = generator.get_graph_data()
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


if __name__ == "__main__":
    app.run(debug=True)
