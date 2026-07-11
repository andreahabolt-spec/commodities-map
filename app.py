import streamlit as st
import folium
from streamlit_folium import st_folium

from kml_parser import parse_kml

st.set_page_config(page_title="Commodities Trading Map", layout="wide")

KML_PATH = "Commodities_Trading_EN.kml"

# Point categories -> marker colour. Names must match the KML folder names.
CATEGORY_COLORS = {
    "Refineries": "#8d6e63",
    "Mega-refineries": "#5d4037",
    "Terminals": "#d32f2f",
    "Ports, aviation, defense (fuel demand sites)": "#1976d2",
    "Oil Fields": "#388e3c",
    "Ammonia production sites": "#fbc02d",
    "Petrochemical Plants": "#000000",
    "Strategic Transport Infrastructure": "#757575",
}
DEFAULT_COLOR = "#3388ff"

# Route categories (LineString folders) -> line colour.
# Crude / refined-product / maritime flows are shown in distinct colours.
ROUTE_COLORS = {
    "Pipelines crude": "#e65100",          # dark orange - crude pipelines
    "Pipelines refined products": "#fbc02d", # yellow - refined products pipelines
    "Maritime routes": "#2dc0fb",          # light blue - sea routes
}
DEFAULT_ROUTE_COLOR = "#2dc0fb"


@st.cache_data
def load_data(path):
    return parse_kml(path)


data = load_data(KML_PATH)
route_categories = list(ROUTE_COLORS.keys())
point_categories = [c for c in data["categories"] if c not in route_categories]

st.title("Global Energy Infrastructure Map")
st.caption(
    "Refineries, storage, terminals, production fields and logistics flows "
    "(crude pipelines, product pipelines, maritime routes) into the European hubs "
    "(Rotterdam / ARA)."
)

# --- Sidebar filters ---
st.sidebar.header("Filters")

selected_categories = st.sidebar.multiselect(
    "Point categories to display",
    options=point_categories,
    default=point_categories,
)

st.sidebar.markdown("**Transport flows**")
show_crude = st.sidebar.checkbox("Crude pipelines", value=True)
show_refined = st.sidebar.checkbox("Refined-product pipelines", value=True)
show_maritime = st.sidebar.checkbox("Maritime routes", value=True)

route_visibility = {
    "Pipelines crude": show_crude,
    "Pipelines refined products": show_refined,
    "Maritime routes": show_maritime,
}

search = st.sidebar.text_input("Search a location by name")

filtered_points = [
    p for p in data["points"]
    if p["category"] in selected_categories
    and (search.lower() in p["name"].lower() if search else True)
]

st.sidebar.markdown(
    f"**{len(filtered_points)}** markers shown out of {len(data['points'])} total."
)

# --- Map ---
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

# Route layers, one FeatureGroup per route type, coloured distinctly
for route_cat in route_categories:
    if not route_visibility.get(route_cat, True):
        continue
    color = ROUTE_COLORS.get(route_cat, DEFAULT_ROUTE_COLOR)
    group = folium.FeatureGroup(name=route_cat, show=True)
    for line in (l for l in data["lines"] if l["category"] == route_cat):
        folium.PolyLine(
            locations=line["coords"],
            color=color,
            weight=3,
            opacity=0.85,
            tooltip=line["name"] if line["name"] != "(unnamed)" else None,
        ).add_to(group)
    group.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

st_folium(m, width=None, height=700, returned_objects=[])
