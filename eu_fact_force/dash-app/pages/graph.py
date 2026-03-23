from dash import html
import dash_bootstrap_components as dbc
import dash_cytoscape as cyto

from utils.colors import EUPHAColors
from utils.graph import stylesheet


def make_layout():

    # Search bar
    search_bar = html.Div(
        children=[
            html.H3("Search"),
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
            ),
        ],
        id="search",
        style={
            "border-radius": "15px",
            "padding": "20px",
            "background-color": EUPHAColors.white,
        },
    )

    # Graph
    graph_results = html.Div(
        id="graph",
        children=[
            html.H3("Graph"),
            cyto.Cytoscape(
                id="graph-cytoscape",
                stylesheet=stylesheet,
                layout={"name": "cose"},
                style={"width": "100%", "height": "400px"},
            ),
        ],
        style={
            "border-radius": "15px",
            "padding": "20px",
            "background-color": EUPHAColors.light_blue,
            "display": "none",
        },
    )

    # Graph offcanevas
    offcanevas = dbc.Offcanvas(
        id="offcanvas",
        title="Focus",
        is_open=False,
        placement="end",
        style={"width": "50%"},
    )

    # List
    list_results = html.Div(
        id="list",
        children=[html.H3("List of results"), html.Div(id="list-elements")],
        style={
            "border-radius": "15px",
            "padding": "20px",
            "background-color": EUPHAColors.light_blue,
            "display": "none",
        },
    )

    return html.Div(
        [search_bar, html.Br(), graph_results, html.Br(), list_results, offcanevas]
    )
