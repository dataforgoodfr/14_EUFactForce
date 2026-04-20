from dash import dcc, html
import dash_bootstrap_components as dbc

from utils.colors import EUPHAColors

def make_layout():

    #Sidebar
    sidebar = html.Div(
        [
            html.Div(
                [

                    html.H3(
                        "EU Fact Force",
                        className="text-center",
                        style={
                            "fontWeight": "700",
                            "fontSize": "1.9rem",
                            "marginBottom": "20px",
                            "color": EUPHAColors.dark_blue
                        }
                    ),

                    html.Hr(style={"margin": "1.2rem 0"}),

                    html.H5(
                        "How it works",
                        style={
                            "fontWeight": "500",
                            "marginBottom": "12px",
                            "marginTop": "45px"
                        }
                    ),

                    html.Ol(
                        [
                            html.Li("Upload a PDF"),
                            html.Li("Validate DOI + abstract"),
                            html.Li("Validate authors"),
                            html.Li("Click Upload file")
                        ],
                        style={
                            "paddingLeft": "1.2rem",
                            "marginLeft": "0",
                            "lineHeight": "1.8"
                        }
                    ),
                ],
                style={
                    "maxWidth": "240px",
                    "margin": "0 auto"
                }
            )
        ],
        style={
            "padding": "2rem 1rem",
            "backgroundColor": EUPHAColors.white,
            "height": "100vh",
            "position": "fixed",
            "top": 0,
            "left": 0,
            "width": "16%",
            "borderRight": "1px solid #dee2e6"
        }
    )

    # Main page
    main_content = html.Div(
        [
            html.Div(
                [
                    html.H1(
                        "EU Fact Force - Article uploading page",
                        className="mb-3 text-center",
                        style={
                            "fontWeight": "700",
                            "fontSize": "2.5rem",
                            "lineHeight": "1.15"
                        }
                    ),
                    html.H3(
                        "Welcome to EU Fact Force articles uploading pages",
                        className="text-center mb-4",
                        style={
                            "color": EUPHAColors.black,
                            "fontWeight": "500",
                            "fontSize": "1.5rem",
                            "lineHeight": "1.3"
                        }
                    ),
                    html.P(
                        "Thank you for collaborating with us, you will find here a page where you can upload and declare authors of your papers in attempt to build a safer and healthier community! Thank you for your contribution!",
                        className="text-center mb-5",
                        style={
                            "maxWidth": "900px",
                            "margin": "0 auto",
                            "fontSize": "1.1rem",
                            "lineHeight": "1.7",
                            "color": EUPHAColors.black
                        }
                    ),
                ],
                style={
                    "maxWidth": "1100px",
                    "margin": "0 auto 2rem auto"
                }
            ),

            dbc.Card([
                dbc.CardBody([
                    html.H4(
                        "Upload & Metadatas",
                        className="card-title font-weight-bold mb-4"
                    ),
                    dcc.Upload(
                        id='upload-pdf',
                        children=html.Div(['Drop your article here or ', html.A('Select a PDF', className="font-weight-bold")]),
                        style={
                            'width': '100%',
                            'height': '80px',
                            'lineHeight': '80px',
                            'borderWidth': '2px',
                            'borderStyle': 'dashed',
                            'borderColor': EUPHAColors.dark_blue,
                            'textAlign': 'center',
                            'borderRadius': '10px',
                            'marginBottom': '20px',
                            'backgroundColor': EUPHAColors.white,
                            'cursor': 'pointer'
                        }
                    ),
                    html.H5("General informations", className="mt-4 font-weight-bold"),
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Article Title"),
                            dbc.Input(id='input-title', type='text', placeholder="Title of the article", className="mb-3"),

                            dbc.Row([
                                dbc.Col([
                                    dbc.Label("Category"),
                                    dcc.Dropdown(
                                        id='input-category',
                                        options=[
                                            {'label': 'Scientific Article', 'value': 'scientific_article'},
                                            {'label': 'Report', 'value': 'report'},
                                            {'label': 'Thesis', 'value': 'thesis'},
                                            {'label': 'Working Paper', 'value': 'working_paper'},
                                            {'label': 'Book Chapter', 'value': 'book_chapter'},
                                            {'label': 'Other', 'value': 'other'}
                                        ],
                                        value='scientific_article',
                                        className="mb-3"
                                    ),
                                ], width=6),
                                dbc.Col([
                                    dbc.Label("Study Type"),
                                    dcc.Dropdown(
                                        id='input-type',
                                        options=[
                                            {'label': 'Meta-analysis', 'value': 'meta_analysis'},
                                            {'label': 'Systematic review', 'value': 'systematic_review'},
                                            {'label': 'Evidence review', 'value': 'evidence_review'},
                                            {'label': 'Cohort study', 'value': 'cohort_study'},
                                            {'label': 'Case-control study', 'value': 'case_control_study'},
                                            {'label': 'Cross-sectional study', 'value': 'cross_sectional_study'},
                                            {'label': 'Randomized controlled trial', 'value': 'rct'},
                                            {'label': 'Other', 'value': 'other'}
                                        ],
                                        className="mb-3"
                                    ),
                                ], width=6),
                            ]),
                            dbc.Label("Journal / Source"),
                            dbc.Input(id='input-journal', type='text', placeholder="ex: The Lancet Public Health", className="mb-3"),

                            dbc.Row([
                                dbc.Col([
                                    dbc.Label("Publication Year"),
                                    dbc.Input(id='input-date', type='text', placeholder="ex: 2023"),
                                ], width=6),
                                dbc.Col([
                                    dbc.Label("DOI"),
                                    dbc.Input(id='input-doi', type='text', placeholder="ex: 10.1038/s41586-021-00000-x"),
                                ], width=6),
                            ], className="mb-3"),

                            dbc.Label("Publication URL"),
                            dbc.Input(id='input-link', type='text', placeholder="https://pubmed.ncbi.nlm.nih.gov/...", className="mb-3"),

                            dbc.Label("Abstract"),
                            dbc.Textarea(id='input-abstract', style={'height': 150}, placeholder="Lorem ipsum dolor sit amet"),

                            dbc.Checkbox(id='chk-meta-correct', label="This information is correct", className="mt-3 font-weight-bold text-success"),
                        ], width=12)
                    ]),
                ])
            ], className="mb-4 shadow-sm", style={"borderRadius": "16px"}),

            dbc.Card([
                dbc.CardBody([
                    html.H4(
                        "Authors",
                        className="card-title font-weight-bold mb-4"
                    ),
                    html.Div(id='authors-container'),
                    dbc.Button(
                        "➕ Add an author",
                        id='btn-add-author',
                        n_clicks=0,
                        outline=True,
                        className="mt-3",
                        style={
                            "color": "#3B6096",
                            "borderColor": "#3B6096",
                            "borderRadius": "10px",
                            "fontWeight": "500"
                        }
                    ),
                    html.Br(),
                    dbc.Checkbox(id='chk-authors-correct', label="Authors information is correct", className="mt-3 font-weight-bold text-success"),
                ])
            ], className="mb-4 shadow-sm", style={"borderRadius": "16px"}),

            dbc.Button(
                "Upload file",
                id='btn-final-upload',
                size="lg",
                className="w-100 mb-4",
                style={
                    "backgroundColor": EUPHAColors.dark_blue,
                    "borderColor": EUPHAColors.dark_blue,
                    "color": "white",
                    "fontWeight": "600",
                    "borderRadius": "10px"
                }
            ),

            html.Div(id='final-output', className="mt-4 pb-5")
        ],
        style={
            "marginLeft": "16%",
            "padding": "5rem 1.5rem 2rem 1.5rem",
            "width": "84%",
            "backgroundColor": "#ffffff"
        }
    )

    return html.Div([
        dcc.Store(id='session-store', data={}),
        sidebar, main_content],
        style={"fontFamily": "system-ui, -apple-system, sans-serif",
            "backgroundColor": "#f5f7fa"})




def add_author_line(index, name="", surname="", email=""):
    """One-click addition/suppression of a new author line"""

    return dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col(
                    dbc.Input(
                        id={'type': 'auth-name', 'index': index},
                        value=name,
                        placeholder="Name"
                    ),
                    width=3
                ),
                dbc.Col(
                    dbc.Input(
                        id={'type': 'auth-surname', 'index': index},
                        value=surname,
                        placeholder="Surname"
                    ),
                    width=3
                ),
                dbc.Col(
                    dbc.Input(
                        id={'type': 'auth-email', 'index': index},
                        value=email,
                        placeholder="Email (Corresponding)"
                    ),
                    width=4
                ),
                dbc.Col(
                    dbc.Button(
                        "Remove",
                        id={'type': 'remove-author', 'index': index},
                        color="danger",
                        outline=True,
                        className="w-100",
                        style={
                            "whiteSpace": "nowrap",
                            "minWidth": "100px"
                        }
                    ),
                    width=2
                )
            ], className="align-items-center g-2")
        ], className="p-2")
    ], className="mb-3 border-light shadow-sm")
