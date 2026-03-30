from dash import html
import dash_bootstrap_components as dbc
import dash_cytoscape as cyto

from utils.colors import EUPHAColors
from utils.graph import stylesheet


def make_layout():

    # Search bar
    search_bar = html.Div(
        children=[
            dbc.Row(
                [
                    dbc.Col(
                        html.H5("Search", style={"margin-bottom": "2px"}), width="auto"
                    ),
                    dbc.Col(
                        dbc.Input(
                            id="search-input",
                            placeholder="Disinformation narrative...",
                            style={"overflow": "hidden"},
                        )
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Search",
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
            html.H5("Graph"),
            cyto.Cytoscape(
                id="graph-cytoscape",
                stylesheet=stylesheet,
                layout={"name": "cose"},
                style={"width": "100%", "height": "300px"},
                zoomingEnabled=True,
                userZoomingEnabled=False,
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
        children=[html.H5("List of results"), html.Div(id="list-elements")],
        style={
            "border-radius": "15px",
            "padding": "20px",
            "background-color": EUPHAColors.white,
        },
    )

    # Filters

    # > Keywords
    keyword_filter = dbc.Row([html.H6("Keywords")])

    # > Evidence type
    evidence_filter = dbc.Row([html.H6("Evidence type")])

    # > Type of document
    doc_type_filter = dbc.Row([html.H6("Document type")])

    # > Paper filters
    paper_filter = dbc.Row([html.H6("Paper filters")])

    filter_results = html.Div(
        id="filters",
        children=[
            html.H5("Filters"),
            keyword_filter,
            html.Br(),
            evidence_filter,
            html.Br(),
            doc_type_filter,
            html.Br(),
            paper_filter,
            html.Br(),
        ],
        style={
            "border-radius": "15px",
            "padding": "20px",
            "background-color": EUPHAColors.white,
        },
    )

    # Results
    results = html.Div(
        id="results",
        children=dbc.Row(
            [dbc.Col(filter_results, width=3), dbc.Col(list_results, width=9)]
        ),
        style={"display": "none"},
    )

    return html.Div(
        [search_bar, html.Br(), graph_results, html.Br(), results, offcanevas]
    )
