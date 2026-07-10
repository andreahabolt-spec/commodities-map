# Global Energy Infrastructure Map

Interactive map of global energy infrastructure (refineries, storage, ports,
production fields, logistics routes), generated from a Google Earth project
exported as KML.

## Run locally

```bash
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501

> On Windows, if `python` is intercepted by the Microsoft Store shortcut, use `py`
> instead. If PowerShell blocks the venv activation, run
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first.

## Updating the map

1. Edit the project in Google Earth Pro (add / move markers, redraw routes).
   Keep everything organised in folders — one folder per category.
2. Export to KML: right-click the project folder in the Places panel ->
   **Save Place As...** -> file type `.kml`.
3. Replace `Commodities_Trading_EN.kml` in this folder with the new export
   (same filename, or change `KML_PATH` at the top of `app.py`).
4. Restart `streamlit run app.py`. No Python changes needed.

**If you add a brand-new category folder**, also add it to the `CATEGORY_COLORS`
dictionary at the top of `app.py`, otherwise its markers fall back to the default
blue.

## Deploy for free (Streamlit Community Cloud)

1. Push this folder to a GitHub repository.
2. Go to https://share.streamlit.io and connect your GitHub account.
3. Select the repo, point it at `app.py`, click Deploy.
4. You get a public URL to put on your CV / portfolio.

## Project structure

- `app.py` — Streamlit application (map, filters, search)
- `kml_parser.py` — reads the KML, extracts points / routes / categories
- `Commodities_Trading_EN.kml` — the data (your Google Earth project)
- `requirements.txt` — Python dependencies

## Features

- Hover a marker -> shows its name (tooltip)
- Click a marker -> shows the full description (popup)
- Filter by category (sidebar multiselect)
- Search by location name
- Toggle layers on/off (control at the top right of the map)
- Show/hide transport routes independently
