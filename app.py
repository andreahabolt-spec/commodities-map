import streamlit as st
import folium
from streamlit_folium import st_folium

from kml_parser import parse_kml

st.set_page_config(page_title="Commodities Trading Map", layout="wide")

KML_PATH = "Commodities_Trading_Eng.kml"

# Point categories -> marker colour. Names must match the KML folder names.
CATEGORY_COLORS = {
    "Mega-refineries": "#5d4037",
    "Refineries": "#8d6e63",
    "Terminals": "#d32f2f",
    "Ports, aviation, defense (fuel demand sites)": "#1976d2",
    "Oil Fields": "#388e3c",
    "Renewable Fuels & Low-Carbon Production Sites": "#00c853",
    "Ammonia production sites": "#fbc02d",
    "Petrochemical Plants": "#000000",
    "Strategic Transport Infrastructure": "#757575",
}
DEFAULT_COLOR = "#3388ff"

# Route categories (LineString folders) -> line colour.
ROUTE_COLORS = {
    "Pipelines crude": "#e65100",            # dark orange - crude pipelines
    "Pipelines refined products": "#fbc02d", # yellow - refined-product pipelines
    "Maritime routes": "#2dc0fb",            # light blue - sea routes
}
DEFAULT_ROUTE_COLOR = "#2dc0fb"

# Specific routes that override their folder colour, keyed by exact name.
ROUTE_NAME_COLORS = {
    "Kirkuk–Ceyhan Oil Pipeline": "#b71c1c",  # dark red - currently NOT operational
}
NON_OPERATIONAL_ROUTES = {"Kirkuk–Ceyhan Oil Pipeline"}

# Human-readable labels for the route categories (used in legend + filters)
ROUTE_LABELS = {
    "Pipelines crude": "Crude pipelines",
    "Pipelines refined products": "Refined-product pipelines",
    "Maritime routes": "Maritime routes",
}


@st.cache_data
def load_data(path):
    return parse_kml(path)


def color_dot(color):
    """Return an inline HTML dot of the given colour, for the sidebar legend."""
    return (
        f"<span style='display:inline-block;width:12px;height:12px;"
        f"border-radius:50%;background:{color};margin-right:8px;"
        f"vertical-align:middle;border:1px solid #00000022'></span>"
    )


def line_swatch(color, dashed=False):
    """Return an inline HTML line swatch for the route legend."""
    style = "dashed" if dashed else "solid"
    return (
        f"<span style='display:inline-block;width:22px;height:0;"
        f"border-top:3px {style} {color};margin-right:8px;"
        f"vertical-align:middle'></span>"
    )


data = load_data(KML_PATH)
route_categories = list(ROUTE_COLORS.keys())
point_categories = [c for c in data["categories"] if c not in route_categories]

st.title("Global Energy Infrastructure Map")
st.caption(
    "Refineries, storage, terminals, production fields and logistics flows "
    "(crude pipelines, product pipelines, maritime routes) into the European hubs "
    "(Rotterdam / ARA)."
)

# =========================================================================
# SIDEBAR: filters + legend combined. Each row shows a colour swatch next to
# a checkbox, so the filter panel doubles as the map legend.
# =========================================================================
st.sidebar.header("Map controls")
st.sidebar.caption("Use the arrow at the top-left of the sidebar to collapse this panel and view the map full-width.")

# --- Point categories ---
st.sidebar.subheader("Infrastructure (points)")
selected_categories = []
for category in point_categories:
    color = CATEGORY_COLORS.get(category, DEFAULT_COLOR)
    count = sum(1 for p in data["points"] if p["category"] == category)
    cols = st.sidebar.columns([0.12, 0.88])
    with cols[0]:
        st.markdown(color_dot(color), unsafe_allow_html=True)
    with cols[1]:
        checked = st.checkbox(f"{category}  ({count})", value=True, key=f"cat_{category}")
    if checked:
        selected_categories.append(category)

# --- Transport flows ---
st.sidebar.subheader("Transport flows (routes)")
route_visibility = {}
for route_cat in route_categories:
    color = ROUTE_COLORS.get(route_cat, DEFAULT_ROUTE_COLOR)
    label = ROUTE_LABELS.get(route_cat, route_cat)
    count = sum(1 for l in data["lines"] if l["category"] == route_cat)
    cols = st.sidebar.columns([0.12, 0.88])
    with cols[0]:
        st.markdown(line_swatch(color), unsafe_allow_html=True)
    with cols[1]:
        route_visibility[route_cat] = st.checkbox(f"{label}  ({count})", value=True, key=f"route_{route_cat}")

# --- Legend note for non-operational infrastructure ---
st.sidebar.markdown(
    line_swatch("#b71c1c", dashed=True) + "<span style='vertical-align:middle'>Non-operational (e.g. Kirkuk–Ceyhan)</span>",
    unsafe_allow_html=True,
)

st.sidebar.divider()

# --- Search ---
search = st.sidebar.text_input("Search a location by name")

filtered_points = [
    p for p in data["points"]
    if p["category"] in selected_categories
    and (search.lower() in p["name"].lower() if search else True)
]

st.sidebar.markdown(
    f"**{len(filtered_points)}** markers shown out of {len(data['points'])} total."
)

# =========================================================================
# MAP
# =========================================================================
# CartoDB Positron has clean, discreet, English-language labels.
m = folium.Map(
    location=[30, 15],
    zoom_start=3,
    min_zoom=2,
    max_bounds=True,
    tiles=None,
)
folium.TileLayer("cartodbpositron", no_wrap=True, control=False).add_to(m)

# Point layers, one FeatureGroup per category
for category in point_categories:
    if category not in selected_categories:
        continue
    group = folium.FeatureGroup(name=category, show=True)
    color = CATEGORY_COLORS.get(category, DEFAULT_COLOR)
    for point in (p for p in filtered_points if p["category"] == category):
        popup_html = f"<b>{point['name']}</b>"
        if point["description"]:
            popup_html += f"<br>{point['description']}"
        folium.CircleMarker(
            location=[point["lat"], point["lon"]],
            radius=6,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            tooltip=point["name"],
            popup=folium.Popup(popup_html, max_width=320),
        ).add_to(group)
    group.add_to(m)

# Route layers, native Leaflet highlight_function (hover thickens the line)
for route_cat in route_categories:
    if not route_visibility.get(route_cat, True):
        continue
    default_color = ROUTE_COLORS.get(route_cat, DEFAULT_ROUTE_COLOR)
    group = folium.FeatureGroup(name=route_cat, show=True)
    for line in (l for l in data["lines"] if l["category"] == route_cat):
        name = line["name"]
        color = ROUTE_NAME_COLORS.get(name, default_color)
        dash = "8, 8" if name in NON_OPERATIONAL_ROUTES else None

        if name in NON_OPERATIONAL_ROUTES:
            tooltip_text = f"{name} — NOT operational"
        else:
            tooltip_text = name if name != "(unnamed)" else ""

        popup_html = None
        if name != "(unnamed)":
            popup_html = f"<b>{name}</b>"
            if line.get("description"):
                popup_html += f"<br>{line['description']}"

        geojson = {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "LineString",
                "coordinates": [[lon, lat] for (lat, lon) in line["coords"]],
            },
        }
        base_style = {"color": color, "weight": 3, "opacity": 0.85}
        if dash:
            base_style["dashArray"] = dash

        gj = folium.GeoJson(
            geojson,
            style_function=lambda _f, s=dict(base_style): s,
            highlight_function=lambda _f: {"weight": 7, "opacity": 1.0},
        )
        if tooltip_text:
            gj.add_child(folium.Tooltip(tooltip_text))
        if popup_html:
            gj.add_child(folium.Popup(popup_html, max_width=340))
        gj.add_to(group)
    group.add_to(m)

st_folium(m, width=None, height=700, returned_objects=[])
