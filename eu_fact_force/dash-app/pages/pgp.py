# pages/pgp.py

from dash import dcc, html
from utils.colors import EUPHAColors
from utils.pgpxd4g_graphs import get_figures


def make_layout():

    trend, lang, source, themes = get_figures()

    return html.Div(
        children=[
            # HEADER
            html.Div(
                [
                    html.H1(
                        "PGP Dashboard",
                        style={
                            "fontFamily": "system-ui, -apple-system, sans-serif",
                            "textAlign": "center",
                            "fontSize": "22px",
                            "fontWeight": "bold",
                        },
                    ),
                    html.P(
                        "This dashboard summarizes posting dynamics, linguistic distribution, platform sources, and key thematic patterns extracted from the dataset.",
                        style={
                            "fontFamily": "system-ui, -apple-system, sans-serif",
                            "textAlign": "center",
                            "fontSize": "14px",
                            "fontStyle": "italic",
                        },
                    ),
                ],
                style={
                    "borderRadius": "16px",
                    "padding": "20px",
                    "backgroundColor": EUPHAColors.white,
                    "color": EUPHAColors.text_main,
                    "boxShadow": "0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -2px rgba(0,0,0,0.025)",
                },
            ),
            html.Br(),
            # GRAPHS GRID PROPRE
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "1fr 1fr",
                    "gap": "15px",
                },
                children=[
                    html.Div(
                        dcc.Graph(figure=trend),
                        style={
                            "borderRadius": "16px",
                            "padding": "20px",
                            "backgroundColor": EUPHAColors.white,
                            "color": EUPHAColors.text_main,
                            "boxShadow": "0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -2px rgba(0,0,0,0.025)",
                            "fontFamily": "system-ui, -apple-system, sans-serif",
                        },
                    ),
                    html.Div(
                        dcc.Graph(figure=lang),
                        style={
                            "borderRadius": "16px",
                            "padding": "20px",
                            "backgroundColor": EUPHAColors.white,
                            "color": EUPHAColors.text_main,
                            "boxShadow": "0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -2px rgba(0,0,0,0.025)",
                            "fontFamily": "system-ui, -apple-system, sans-serif",
                        },
                    ),
                    html.Div(
                        dcc.Graph(figure=source),
                        style={
                            "borderRadius": "16px",
                            "padding": "20px",
                            "backgroundColor": EUPHAColors.white,
                            "color": EUPHAColors.text_main,
                            "boxShadow": "0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -2px rgba(0,0,0,0.025)",
                            "fontFamily": "system-ui, -apple-system, sans-serif",
                        },
                    ),
                    html.Div(
                        dcc.Graph(figure=themes),
                        style={
                            "borderRadius": "16px",
                            "padding": "20px",
                            "backgroundColor": EUPHAColors.white,
                            "color": EUPHAColors.text_main,
                            "boxShadow": "0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -2px rgba(0,0,0,0.025)",
                            "fontFamily": "system-ui, -apple-system, sans-serif",
                        },
                    ),
                ],
            ),
        ],
    )
