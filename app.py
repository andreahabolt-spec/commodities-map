import streamlit as st
import folium
from streamlit_folium import st_folium

from kml_parser import parse_kml

st.set_page_config(page_title="Commodities Trading Map", layout="wide")

KML_PATH = "Commodities_Trading_EN.kml"

# Marker colour per category. Keep these in sync with the folder names in the KML.
CATEGORY_COLORS = {
    "Refineries": "#8d6e63",
    "Mega-refineries": "#5d4037",
    "Ports & Storage": "#d32f2f",
    "Terminals & Strategic Reserves": "#ef5350",
    "Ports / Cities / Mines": "#1976d2",
    "Oil Fields & Production": "#388e3c",
    "Offshore Oil & Gas Fields": "#66bb6a",
    "Power Plants & Offshore Fields": "#00796b",
    "Power Plants & LNG": "#5c6bc0",
    "Petrochemical Plants": "#000000",
    "Ammonia & Renewables": "#fbc02d",
    "Storage & Refineries (Asia)": "#7b1fa2",
    "Straits & Strategic Hubs": "#ffee58",
    "Geopolitical Points": "#ab47bc",
    "Rivers & Waterways": "#757575",
    "Uncategorised": "#9e9e9e",
}
ROUTE_CATEGORY = "Transport Routes"
ROUTE_COLOR = "#2dc0fb"
DEFAULT_COLOR = "#3388ff"


@st.cache_data
def load_data(path):
    return parse_kml(path)


data = load_data(KML_PATH)
point_categories = [c for c in data["categories"] if c != ROUTE_CATEGORY]

st.title("Global Energy Infrastructure Map")
st.caption(
    "Refineries, storage, ports, production fields and logistics routes "
    "into the European hubs (Rotterdam / ARA)."
)

# --- Sidebar filters ---
st.sidebar.header("Filters")

selected_categories = st.sidebar.multiselect(
    "Categories to display",
    options=point_categories,
    default=point_categories,
)

show_routes = st.sidebar.checkbox("Show transport routes", value=True)

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
# tiles=None + an explicit TileLayer lets us set no_wrap, which stops Leaflet
# from repeating the world horizontally at low zoom levels.
m = folium.Map(
    location=[30, 15],
    zoom_start=3,
    min_zoom=2,
    max_bounds=True,
    tiles=None,
)
folium.TileLayer(
    "cartodbpositron",
    no_wrap=True,
    control=False,  # hide the single-basemap radio button from the layer control
).add_to(m)

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
            tooltip=point["name"],                            # shown on hover
            popup=folium.Popup(popup_html, max_width=300),    # shown on click
        ).add_to(group)

    group.add_to(m)

if show_routes:
    routes = folium.FeatureGroup(name=ROUTE_CATEGORY, show=True)
    for line in data["lines"]:
        folium.PolyLine(
            locations=line["coords"],
            color=ROUTE_COLOR,
            weight=3,
            opacity=0.8,
            tooltip=line["name"] if line["name"] != "(unnamed)" else None,
        ).add_to(routes)
    routes.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

st_folium(m, width=None, height=700, returned_objects=[])
