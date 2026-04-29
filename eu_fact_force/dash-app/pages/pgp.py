from dash import html, dcc

def make_layout():

    return html.Div(

        style={
            "backgroundColor": "#F8FAFC",
            "fontFamily": "Arial",
            "padding": "20px"
        },

        children=[

            # HEADER
            html.Div(
                children=[
                    html.H1(
                        "PGP Dashboard",
                        style={
                            "color": "white",
                            "textAlign": "center",
                            "margin": "0"
                        }
                    )
                ],
                style={
                    "backgroundColor": "#0B5FA5",
                    "padding": "18px",
                    "borderRadius": "10px",
                    "boxShadow": "0px 2px 6px rgba(0,0,0,0.15)"
                }
            ),

            html.Br(),

            # FILTERS
            html.Div(

                children=[

                    html.H3(
                        "Filters",
                        style={"marginBottom": "15px"}
                    ),

                    html.Div(

                        style={
                            "display": "flex",
                            "gap": "15px",
                            "flexWrap": "wrap"
                        },

                        children=[

                            dcc.Dropdown(
                                id="metric-filter",
                                placeholder="Select metric",
                                options=[
                                    {"label": "Metric A", "value": "A"},
                                    {"label": "Metric B", "value": "B"},
                                ],
                                style={"width": "260px"}
                            ),

                            dcc.Dropdown(
                                id="context-filter",
                                placeholder="Select category / country",
                                options=[
                                    {"label": "France", "value": "FR"},
                                    {"label": "Germany", "value": "DE"},
                                ],
                                style={"width": "260px"}
                            ),

                        ]
                    )
                ],

                style={
                    "backgroundColor": "white",
                    "padding": "18px",
                    "borderRadius": "10px",
                    "boxShadow": "0px 2px 6px rgba(0,0,0,0.08)"
                }
            ),

            html.Br(),

            # VISUALIZATIONS
            html.Div(

                children=[

                    html.H3("Visualizations"),

                    html.Div(

                        style={
                            "display": "grid",
                            "gridTemplateColumns": "1fr 1fr",
                            "gap": "20px"
                        },

                        children=[

                            dcc.Graph(id="graph-1"),
                            dcc.Graph(id="graph-2"),

                        ]
                    )

                ],

                style={
                    "backgroundColor": "white",
                    "padding": "20px",
                    "borderRadius": "10px",
                    "boxShadow": "0px 2px 6px rgba(0,0,0,0.08)"
                }
            )

        ]
    )