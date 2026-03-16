# Exploration - Dash Cytoscape

This folder contains a first version of a local Dash app to explore Cytoscape capabilities. 

# Repo structure
- `app.py`: the main app file.
- `assets/`: the app asset folder, with custom css, icon and plotly template.
- `utils/`: app utility files, including d4g colors and random graph generator.


## Setup
- Install `graph` group depedencies using `uv sync --group graph`.
- Start app from here with `pyhon app.py`.
- Visit `http://127.0.0.1:8050/` to see the app on your local.

## App overview
- This app contains a search bar with an "Search" button to simulate search.
- On search button click, a random network graph will be generated.
- Clicking on a node in the chart will open an offcanevas displaying node metadata.
- A list of all nodes in the graph will also be generated, with node metadatWHen a in each element.