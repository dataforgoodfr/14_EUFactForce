import pandas as pd
import plotly.graph_objects as go

DATA_PATH = "data/PGP x D4G- Exported Vaccine Data.xlsx" # Correct to the actual Excel file

# ── Load all sheets ────────────────────────────────────────────────
xl = pd.ExcelFile(DATA_PATH)

df_trend = pd.read_excel(xl, "Trendline")
df_trend.columns = ["date", "posts"]
df_trend["date"] = pd.to_datetime(df_trend["date"])

df_lang = pd.read_excel(xl, "Language")
df_lang.columns = ["language", "posts", "share"]
df_lang = df_lang.dropna(subset=["language", "posts"])
df_lang = df_lang[df_lang["posts"].apply(lambda x: str(x).isdigit() or isinstance(x, (int, float)))]
df_lang["posts"] = pd.to_numeric(df_lang["posts"], errors="coerce")
df_lang = df_lang.dropna(subset=["posts"]).head(8)

df_source = pd.read_excel(xl, "Source")
df_source.columns = ["source", "mentions"]
df_source["mentions"] = pd.to_numeric(df_source["mentions"], errors="coerce").fillna(0)
df_source = df_source.dropna(subset=["source", "mentions"])

df_themes_raw = pd.read_excel(xl, "Crosstab- themes across all vac")

# Corrected processing for df_th
df_th = df_themes_raw.drop(columns=['Topics \\ Themes']).T.reset_index()
df_th.columns = ['theme', 'mentions']
df_th['mentions'] = pd.to_numeric(df_th['mentions'], errors='coerce')
df_th = df_th.dropna(subset=["mentions"])
df_th = df_th.sort_values("mentions", ascending=False)

PALETTE = ["#1E5AA8", "#2F6FB6", "#5C8FD6", "#E6EEF8"]
BG = "#FFFFFF"
PAPER = "#FFFFFF"
FONT_COLOR = "#333333"
GRID_COLOR = "#E0E0E0"


def base_layout(title):
    return dict(
        title=dict(text=title, font=dict(size=16, color=FONT_COLOR), x=0.02),
        paper_bgcolor=PAPER,
        plot_bgcolor=BG,
        font=dict(family="Inter, sans-serif", color=FONT_COLOR),
        margin=dict(l=50, r=30, t=60, b=50),
    )


# ── 1. Daily post volume trendline ─────────────────────────────
fig_trend = go.Figure()
fig_trend.add_trace(go.Scatter(
    x=df_trend["date"], y=df_trend["posts"],
    mode="lines+markers",
    line=dict(color=PALETTE[0], width=2),
    marker=dict(size=5, color=PALETTE[0]),
    fill="tozeroy",
    fillcolor="rgba(30,90,168,0.15)",
    name="Posts",
    hovertemplate="%{x|%b %d}<br><b>%{y:,}</b> posts<extra></extra>",
))
fig_trend.update_layout(
    **base_layout("Daily Post Volume — March–April 2026"),
    xaxis=dict(showgrid=False, tickformat="%b %d", tickcolor=GRID_COLOR),
    yaxis=dict(showgrid=True, gridcolor=GRID_COLOR, tickformat=","),
)

# ── 2. Language donut ───────────────────────────────────
fig_lang = go.Figure(go.Pie(
    labels=df_lang["language"],
    values=df_lang["posts"],
    hole=0.55,
    marker=dict(colors=PALETTE),
    textinfo="label+percent",
    hovertemplate="<b>%{label}</b><br>%{value:,} posts (%{percent})<extra></extra>",
))
fig_lang.update_layout(
    **base_layout("Post Distribution by Language"),
    showlegend=False,
)

# Create a color list for df_source that matches its length
source_colors = []
for i in range(len(df_source)):
    source_colors.append(PALETTE[i % len(PALETTE)])

# ── 3. Source donut chart ───────────────────────────────────
fig_source = go.Figure(go.Pie(
    labels=df_source["source"].tolist(),
    values=df_source["mentions"].tolist(),
    hole=0.55,
    marker=dict(colors=source_colors), # Use the explicit color list
    textinfo="label+percent", # Reverted to include percentage
    hovertemplate="<b>%{label}</b><br>%{value:,} mentions (%{percent})<extra></extra>", # Reverted to include percentage
))
fig_source.update_layout(
    **base_layout("Mentions by Platform"),
    showlegend=False,
)

# ── 4. Anti-vaccine themes treemap ─────────────────────
# Define a colorscale using the PALETTE in reverse order to map higher mentions to darker blues
gradient_colors = [[0, PALETTE[3]], [0.33, PALETTE[2]], [0.66, PALETTE[1]], [1, PALETTE[0]]]
fig_themes = go.Figure(go.Treemap(
    labels=df_th["theme"],
    parents=[""] * len(df_th),
    values=df_th["mentions"],
    # Assign the 'mentions' column to marker.colors for the gradient effect
    marker=dict(colors=df_th["mentions"], colorscale=gradient_colors, showscale=False),
    hovertemplate="<b>%{label}</b><br>%{value:,} mentions (%{percent parent})<extra></extra>",
    textinfo="label+percent parent"
))
fig_themes.update_layout(**base_layout("Anti-vaccine Themes — All Vaccines"))
fig_themes.update_layout(margin=dict(l=10, r=10, t=60, b=10))

# ── Preview all figures ────────────────────────────────
if __name__ == "__main__":
    for name, fig in [
        ("Trendline", fig_trend),
        ("Language", fig_lang),
        ("Source", fig_source),
        ("Themes Treemap", fig_themes)
    ]:
        print(f"Attempting to display: {name}")
        try:
            fig.show()
            print(f"Opened: {name}")
        except Exception as e:
            print(f"Error opening {name}: {e}")
            print(f"Skipping {name} due to error.")
