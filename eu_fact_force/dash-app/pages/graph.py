from dash import html, dcc
import dash_bootstrap_components as dbc
import dash_cytoscape as cyto

from utils.colors import EUPHAColors
from utils.graph import stylesheet, dict_node_type_colors

# Reusable label style for the sidebar
def _sidebar_label(text):
    return html.Label(text, style={"fontSize": "12px", "fontWeight": "600", "textTransform": "uppercase", "color": EUPHAColors.text_muted, "marginTop": "15px", "marginBottom": "5px"})

def make_layout():

    search_bar = html.Div(
        dbc.Row(
            [
                dbc.Col(html.H5("Semantic Search", style={"margin": "0", "color": EUPHAColors.text_dark, "fontWeight": "600"}), width="auto", className="pe-4"),
                dbc.Col(
                    dcc.Dropdown(
                        id="search-input",
                        options=[{"label": "vaccines and autism correlation", "value": "vaccine_autism"}],
                        placeholder="Enter keywords to explore the science...",
                        style={"border": "none"}
                    )
                ),
                dbc.Col(
                    dbc.Button("Search", id="search-button", color="primary", className="px-4", n_clicks=0, disabled=True),
                    width="auto",
                ),
            ],
            align="center",
        ),
        id="search",
        style={
            "borderRadius": "12px",
            "padding": "20px 25px",
            "backgroundColor": EUPHAColors.white,
            "boxShadow": "0 2px 4px rgba(0,0,0,0.04)",
            "border": f"1px solid {EUPHAColors.border_color}"
        },
    )

    legend_items = [
        html.Div(
            [
                html.Div(style={"width": "12px", "height": "12px", "borderRadius": "50%", "backgroundColor": color, "marginRight": "8px"}),
                html.Span(label.capitalize(), style={"fontSize": "13px", "color": EUPHAColors.text_muted, "fontWeight": "500"})
            ], 
            style={"display": "flex", "alignItems": "center"}
        )
        for label, color in dict_node_type_colors.items()
    ]
    
    graph_legend = html.Div(
        legend_items, 
        style={
            "display": "flex", "gap": "20px", "padding": "12px 20px", 
            "backgroundColor": EUPHAColors.light_bg, 
            "borderBottom": f"1px solid {EUPHAColors.border_color}",
            "borderTopLeftRadius": "12px", "borderTopRightRadius": "12px"
        }
    )

    graph_results = html.Div(
        id="graph",
        children=[
            cyto.Cytoscape(
                id="graph-cytoscape",
                stylesheet=stylesheet,
                layout={
                    "name": "cose", 
                    "padding": 40,
                    "avoidOverlap": True,
                    "nodeRepulsion": 400000,
                    "idealEdgeLength": 100
                },
                style={"width": "100%", "height": "550px", "backgroundColor": EUPHAColors.white},
                zoomingEnabled=True,
                userZoomingEnabled=True,
                wheelSensitivity=0.1,
            ),
        ],
        style={"display": "none"},
    )

    offcanevas = dbc.Offcanvas(id="offcanvas", title="Entity Details", is_open=False, placement="end")

    list_results = html.Div(
        id="list",
        children=[html.Div(id="list-elements", style={"padding": "20px"})],
        style={"backgroundColor": EUPHAColors.white},
    )

    filter_results = html.Div(
        id="filters",
        children=[
            html.H5("Filters", style={"color": EUPHAColors.text_dark, "fontWeight": "600", "marginBottom": "20px"}),
            
            _sidebar_label("Entity Types"),
            dcc.Dropdown(id="filter_node_types", multi=True, searchable=False, placeholder="All nodes"),
            
            _sidebar_label("Extracted Keywords"),
            dcc.Dropdown(id="filter_keywords", multi=True, placeholder="Filter by keyword..."),
            
            _sidebar_label("Content Chunk Types"),
            dcc.Dropdown(id="filter_chunk_types", multi=True, searchable=False, placeholder="All types"),
            
            html.Hr(style={"borderColor": EUPHAColors.border_color, "margin": "25px 0"}),
            
            html.H6("Document Meta", style={"color": EUPHAColors.text_dark, "fontWeight": "600", "fontSize": "14px"}),
            
            _sidebar_label("Publication Date"),
            dcc.DatePickerRange(id="filter_dates", updatemode="singledate", clearable=True, className="w-100"),
            
            _sidebar_label("Journals"),
            dcc.Dropdown(id="filter_journals", multi=True, placeholder="Select journals..."),
            
            _sidebar_label("Authors"),
            dcc.Dropdown(id="filter_authors", multi=True, placeholder="Select authors..."),
            
            _sidebar_label("Specific Documents"),
            dcc.Dropdown(id="filter_documents", multi=True, placeholder="Select docs by ID..."),
        ],
        style={
            "backgroundColor": EUPHAColors.light_bg,
            "padding": "25px",
            "borderRadius": "12px",
            "border": f"1px solid {EUPHAColors.border_color}",
            "height": "100%"
        }
    )

    tab_graph = dbc.Card(
        [graph_legend, graph_results, offcanevas], 
        style={"border": f"1px solid {EUPHAColors.border_color}", "borderTop": "none", "borderBottomLeftRadius": "12px", "borderBottomRightRadius": "12px"}
    )

    tab_list = dbc.Card(
        [list_results],
        style={"border": f"1px solid {EUPHAColors.border_color}", "borderTop": "none", "borderBottomLeftRadius": "12px", "borderBottomRightRadius": "12px"}
    )

    tabs = dbc.Tabs(
        [
            dbc.Tab(tab_graph, label="Network Graph", tab_style={"cursor": "pointer"}),
            dbc.Tab(tab_list, label="List View", tab_style={"cursor": "pointer"}),
        ],
    )

    results = html.Div(
        id="results",
        children=dbc.Row(
            [
                dbc.Col(filter_results, width=3),
                dbc.Col(tabs, width=9),
            ],
            className="g-4"
        ),
        style={"display": "none", "marginTop": "20px"},
    )

    return html.Div(
        [search_bar, html.Br(), results], 
        style={"fontFamily": "system-ui, -apple-system, sans-serif"}
    )