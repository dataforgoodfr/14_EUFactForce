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
                        "EU Fact Force - PGP Dashboard",
                        className="mb-3 text-center",
                        style={
                            "color": EUPHAColors.text_main,
                            "fontWeight": "800",
                            "marginBottom": "10px", 
                            "fontSize": "36px"
                        }
                    ),
                    html.P(
                        "This dashboard summarizes posting dynamics, linguistic distribution, platform sources, and key thematic patterns extracted from the dataset.",
                        className="text-center mb-5",
                        style={
                            "fontSize": "17px", 
                            "color": EUPHAColors.text_main, 
                            "marginTop": "20px", 
                            "lineHeight": "1.6", 
                            "maxWidth": "800px",
                            "margin": "20px auto 0 auto"
                        }
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
        style=
        {
            "borderRadius": "16px",
            "padding": "60px",
            "backgroundColor": EUPHAColors.white, 
            "color": EUPHAColors.text_main,
            "boxShadow": "0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -2px rgba(0,0,0,0.025)",
            "fontFamily": "system-ui, -apple-system, sans-serif" 
        }
    )
