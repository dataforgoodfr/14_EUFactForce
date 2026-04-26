# European Vaccine Dashboard (Dash + Django + Plotly)
 Status: Work in progress

## Overview
This project is a collaborative dashboard built with:

- Dash (frontend UI)
- Plotly (data visualization)
- Django (data access layer - coming soon)
- PostgreSQL (raw + analytics schemas)

The goal is to visualize vaccine-related analytics data coming from an external partner dataset.

---

## Architecture (current phase)

Dash App
│
├── layout.py → UI structure
├── callbacks.py → (to be implemented)
├── services.py → mock data (temporary)
├── plotly/charts.py → graph definitions
└── app.py → entry point

           PostgreSQL
        ┌─────────────────┐
        │      RAW        │
        │ raw datasets    │
        └────────┬────────┘
                 │
                 │ SQL transformations
                 │
        ┌────────▼────────┐
        │    ANALYTICS    │
        │ SQL views       │
        └────────┬────────┘
                 │
                 │
                 ▼
            Django Backend
        (ORM / Data services)
                 │
                 │
                 ▼
             Dash App
        (layout + callbacks)
                 │
                 ▼
              Plotly
         Interactive graphs
---

## How to run the app

```bash
pip install dash plotly
python app.py