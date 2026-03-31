from dash import html, dcc
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
                        dcc.Dropdown(
                            id="search-input",
                            options=[
                                {"label": "Test local", "value": "Test local"},
                            ],
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
                style={"width": "100%", "height": "400px"},
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

    # > Chunk types
    chunk_type_filter = dbc.Row(
        [html.H6("Chunk types"), dcc.Dropdown(id="filter_chunk_types", multi=True)]
    )

    # > Keywords
    keyword_filter = dbc.Row(
        [html.H6("Keywords"), dcc.Dropdown(id="filter_keywords", multi=True)]
    )

    # > Document filters
    document_filter = dbc.Row(
        [
            html.H6("Document filters"),
            html.P("Date", style={"margin-bottom": 0, "margin-top": "5px"}),
            dcc.DatePickerRange(id="filter_dates"),
            html.P("Journal", style={"margin-bottom": 0, "margin-top": "5px"}),
            dcc.Dropdown(id="filter_journals", multi=True),
            html.P("Authors", style={"margin-bottom": 0, "margin-top": "5px"}),
            dcc.Dropdown(id="filter_authors", multi=True),
            html.P("Documents", style={"margin-bottom": 0, "margin-top": "5px"}),
            dcc.Dropdown(id="filter_documents", multi=True),
        ]
    )

    filter_results = html.Div(
        id="filters",
        children=[
            html.H5("Filters"),
            keyword_filter,
            html.Br(),
            chunk_type_filter,
            html.Br(),
            document_filter,
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
            [
                dbc.Col(filter_results, width=3),
                dbc.Col([graph_results, html.Br(), list_results], width=9),
            ]
        ),
        style={"display": "none"},
    )

    return html.Div([search_bar, html.Br(), results, offcanevas])
