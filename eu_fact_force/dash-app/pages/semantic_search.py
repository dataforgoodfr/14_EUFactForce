from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.colors import EUPHAColors


def make_layout():
    search_bar = html.Div(
        dbc.Row(
            [
                dbc.Col(
                    html.H5("Semantic Search", style={"margin-bottom": "2px"}),
                    width="auto",
                ),
                dbc.Col(
                    dbc.Input(
                        id="sem-search-input",
                        type="text",
                        placeholder="Ask a question or enter keywords…",
                        debounce=False,
                    )
                ),
                dbc.Col(
                    dbc.Button(
                        "Search",
                        id="sem-search-button",
                        color="primary",
                        n_clicks=0,
                        disabled=True,
                    ),
                    width="auto",
                ),
            ],
            align="center",
        ),
        style={
            "border-radius": "15px",
            "padding": "20px",
            "background-color": EUPHAColors.white,
        },
    )

    results_area = html.Div(
        id="sem-results",
        style={"display": "none"},
        children=[
            html.Br(),
            html.Div(id="sem-results-content"),
        ],
    )

    return html.Div([search_bar, results_area])
