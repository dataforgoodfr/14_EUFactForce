from dash import Dash
from layout import create_layout

app = Dash(__name__)
app.layout = create_layout()

if __name__ == "__main__":
    app.run(debug=True)