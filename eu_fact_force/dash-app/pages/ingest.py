from dash import dcc, html

from utils.colors import EUPHAColors


def make_layout():

    return html.Div(
        [
            html.H2("Ingestion"),
            dcc.Markdown("Ingestion layout to be completed here..."),
        ],
        style={
            "border-radius": "15px",
            "padding": "20px",
            "background-color": EUPHAColors.white,
        },
    )
