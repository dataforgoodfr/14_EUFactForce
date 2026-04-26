from dash import html

def create_layout():
    return html.Div(
        style={
            "backgroundColor": "#FFFFFF",
            "fontFamily": "Arial",
            "padding": "20px"
        },

        children=[

            html.Div(
                children=[
                    html.H1(
                        "European Vaccine Dashboard",
                        style={
                            "color": "white",
                            "textAlign": "center",
                            "margin": "0"
                        }
                    )
                ],
                style={
                    "backgroundColor": "#00669B",
                    "padding": "15px",
                    "borderRadius": "8px"
                }
            ),

            html.Br(),

            html.Div(
                children=[
                    html.H3("Filters"),
                    html.P("Add dropdowns / filters here")
                ],
                style={
                    "backgroundColor": "#E6F4F9",
                    "padding": "15px",
                    "borderRadius": "8px"
                }
            ),

            html.Br(),

            html.Div(
                children=[
                    html.H3("Visualizations"),
                    html.P("Graphs will be added here")
                ],
                style={
                    "backgroundColor": "#F5F5F5",
                    "padding": "20px",
                    "borderRadius": "8px"
                }
            )
        ]
    )