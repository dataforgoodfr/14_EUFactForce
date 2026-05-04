# trendline data
file_path = "PGP x D4G- Exported Vaccine Data.xlsx" # excel source to be modified 

trendline = pd.read_excel(file_path, sheet_name="Trendline")

# colors creation
primary = "#1E5AA8"
secondary = "#2F6FB6"
background = "#E6EEF8"

# graph creation
import plotly.graph_objects as go

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=trendline["Publication Date (GMT+01:00) London"],
    y=trendline["Posts"],
    name="Posts count evolution",
    line=dict(color=primary, width=2),
    marker=dict(size=6, color=secondary),
    hovertemplate="Date: %{x}<br>Posts: %{y}<extra></extra>"
))

fig.update_layout(
    title="Posts count evolution in the last month",
    plot_bgcolor="white",
    paper_bgcolor=background,
    xaxis_title="Date",
    yaxis_title="Number of posts",
)

fig.show()
