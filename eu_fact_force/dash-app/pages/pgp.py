# pages/pgp.py

from dash import html, dcc
from utils.pgpxd4g_graphs import get_figures

def make_layout():

    trend, lang, source, themes = get_figures()

    return html.Div(
        style={
            "backgroundColor": "#F4F6F8",
            "padding": "20px",
            "fontFamily": "Arial",
        },
        children=[

            # HEADER
            html.Div(
                "PGP Dashboard",
                style={
                    "backgroundColor": "#0B5FA5",
                    "color": "white",
                    "padding": "15px",
                    "borderRadius": "10px",
                    "textAlign": "center",
                    "fontSize": "22px",
                    "fontWeight": "bold",
                },
            ),

           
            html.Div(
                  "This dashboard summarizes posting dynamics, linguistic distribution, platform sources, and key thematic patterns extracted from the dataset.",
                style={
                    "textAlign": "center",
                    "marginTop": "6px",
                    "marginBottom": "16px",
                    "color": "#6B7280",
                    "fontSize": "12.5px",
                    "fontStyle": "italic",
                },
            ),
        
            
            # GRAPHS GRID PROPRE
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "1fr 1fr",
                    "gap": "15px",
                },
                children=[

                    dcc.Graph(figure=trend),
                    dcc.Graph(figure=lang),

                    dcc.Graph(figure=source),
                    dcc.Graph(figure=themes),
                ],
            ),
        ],
    )