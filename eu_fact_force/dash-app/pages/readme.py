from dash import dcc, html
from utils.colors import EUPHAColors 

def make_layout():
    return html.Div(
        [
            html.Div(
                [
                    html.H1(
                        "Welcome to EU Health Fact Force", 
                        style={"color": EUPHAColors.text_main, "fontWeight": "800", "marginBottom": "10px", "fontSize": "36px"}
                    ),
                    html.H3(
                        "Stand up for science. A Hub for reclaiming trust in public health.",
                        style={"color": EUPHAColors.primary, "fontStyle": "normal", "fontWeight": "500", "marginTop": "0px", "fontSize": "22px"}
                    ),
                    html.P(
                        "A long-term collaborative project led by EUPHA in collaboration with Data for Good and The Public Good Projects"
                        "to bring together technical experts, researchers, and civil society actors"
                        "to detect, analyze, and respond collectively to health misinformation.",
                        style={
                            "fontSize": "17px", 
                            "color": EUPHAColors.text_main, 
                            "marginTop": "20px", 
                            "lineHeight": "1.6", 
                            "maxWidth": "800px",
                            "margin": "20px auto 0 auto"
                        }
                    )
                ],
                style={"textAlign": "center", "marginBottom": "50px"}
            ),

            html.Div(
                html.H4(
                    "\"Health misinformation is not only a problem of facts, but a problem of power, trust, and scale.\"",
                    style={"textAlign": "center", "color": EUPHAColors.text_dark, "margin": "0", "fontWeight": "500", "fontStyle": "italic", "fontSize": "20px"}
                ),
                style={
                    "backgroundColor": EUPHAColors.light_bg,
                    "padding": "35px",
                    "borderRadius": "12px",
                    "marginBottom": "60px",
                    "border": f"1px solid {EUPHAColors.border_color}",
                    "boxShadow": "0 2px 4px rgba(0,0,0,0.02)" 
                }
            ),

            html.Div(
                [
                    html.Div(
                        [
                            html.H4("The Infodemic Context", style={"color": EUPHAColors.primary, "fontSize": "22px", "marginBottom": "15px", "fontWeight": "600"}),
                            html.P(
                                "Health misinformation has reached an unprecedented scale"
                                "driven by political polarization, commercial interests, and geopolitical strategies."
                                "Traditional public health systems are struggling to monitor"
                                "and respond to these false narratives in a timely, coordinated way."
                                "The EU Health Fact Force hub transforms fragmented reactions"
                                "into proactive, unified public-health communication.",
                                style={"lineHeight": "1.7", "color": EUPHAColors.text_main}
                            )
                        ],
                        style={"flex": "1"}
                    ),
                    
                    html.Div(
                        [
                            html.H4("Beyond Automated Fact-Checking", style={"color": EUPHAColors.primary, "fontSize": "22px", "marginBottom": "15px", "fontWeight": "600"}),
                            html.P(
                                "Rather than relying solely on automated counter-messaging,"
                                "the EUHFF Hub prioritizes human coordination, collective intelligence, and solidarity."
                                "We focus on bridging science, lived experience, and community insight to meet people where they are,"
                                "equipping trusted local messengers with evidence-based content.",
                                style={"lineHeight": "1.7", "color": EUPHAColors.text_main}
                            )
                        ],
                        style={"flex": "1"}
                    ),
                ],
                style={"display": "flex", "flexDirection": "row", "gap": "60px", "marginBottom": "50px"} 
            ),

            html.Hr(style={"borderTop": f"1px solid {EUPHAColors.border_color}", "marginBottom": "50px", "opacity": "1"}),

            html.H3("What the Hub Delivers", style={"color": EUPHAColors.text_dark, "marginBottom": "30px", "fontSize": "28px", "fontWeight": "700", "textAlign": "center"}),
            html.Div(
                [
                    _create_pillar_card(
                        title="1. Observatory",
                        description="Detect and analyze emerging health misinformation narratives across languages and platforms. Document patterns, trends, and drivers ethically and transparently.",
                        color=EUPHAColors.primary
                    ),
                    _create_pillar_card(
                        title="2. Coordination",
                        description="Connect misinformation narratives with scientific evidence. Support rapid, coordinated responses by public health actors through shared playbooks and early-warning models.",
                        color=EUPHAColors.primary
                    ),
                    _create_pillar_card(
                        title="3. Community Hub",
                        description="Allow the fragmented public health workforce to register, connect, and receive tailored, evidence-informed content directly through channels they use (e.g., WhatsApp).",
                        color=EUPHAColors.primary
                    ),
                ],
                style={"display": "flex", "gap": "30px"} 
            )
        ],
        style={
            "borderRadius": "16px",
            "padding": "60px",
            "backgroundColor": EUPHAColors.white, 
            "color": EUPHAColors.text_main,
            "boxShadow": "0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -2px rgba(0,0,0,0.025)",
            "fontFamily": "system-ui, -apple-system, sans-serif" 
        },
    )

def _create_pillar_card(title, description, color):
    return html.Div(
        [
            html.H4(title, style={"color": color, "marginTop": "0", "fontSize": "20px", "fontWeight": "600"}),
            html.P(description, style={"fontSize": "15px", "lineHeight": "1.6", "margin": "0", "color": EUPHAColors.text_muted})
        ],
        style={
            "flex": "1",
            "backgroundColor": EUPHAColors.white,
            "border": f"1px solid {EUPHAColors.border_color}",
            "borderTop": f"4px solid {color}", 
            "borderRadius": "12px",
            "padding": "30px",
            "boxShadow": "0 2px 4px rgba(0,0,0,0.02)"
        }
    )