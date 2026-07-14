import glob
import os
import re

import streamlit as st
import folium
from streamlit_folium import st_folium

from kml_parser import parse_kml

st.set_page_config(page_title="Commodities Trading Map", layout="wide")

# Expected data file. If it is missing (e.g. Google Earth exported under another
# name), fall back to any .kml present in the folder so the app still runs.
KML_PATH = "Commodities_Trading.kml"


def resolve_kml_path(preferred):
    if os.path.exists(preferred):
        return preferred, None
    candidates = sorted(glob.glob("*.kml"))
    if not candidates:
        return None, "No .kml file found in the app folder."
    return candidates[0], (
        f"'{preferred}' not found — using '{candidates[0]}' instead. "
        f"Rename your export to '{preferred}' to silence this warning."
    )


# Point categories -> marker colour. Names must match the KML folder names.
CATEGORY_COLORS = {
    "Mega-refineries": "#5d4037",                              # dark brown
    "Refineries": "#8d6e63",                                   # brown
    "Major Oil Storage & Distribution Terminals": "#d32f2f",   # red
    "Ports & Maritime Logistics Hubs": "#1976d2",              # blue
    "Offshore tanker loading terminal": "#ad1457",             # magenta
    "Oil Fields": "#388e3c",                                   # green
    "Renewable Fuels & Low-Carbon Production Sites": "#00c853",  # bright green
    "Ammonia production sites": "#fbc02d",                     # yellow
    "Petrochemical Plants": "#000000",                         # black
    "Major Industrial & Energy Hubs": "#7b1fa2",               # purple
    "Aviation Fuel Demand": "#00acc1",                         # cyan
}
DEFAULT_COLOR = "#3388ff"

# Route categories (LineString folders) -> line colour.
ROUTE_COLORS = {
    "Pipelines crude": "#e65100",             # dark orange - crude pipelines
    "Pipelines refined products": "#fdd835",  # yellow - refined-product pipelines
    "Maritime routes": "#2dc0fb",             # light blue - sea routes
}
DEFAULT_ROUTE_COLOR = "#2dc0fb"

# Specific routes that override their folder colour, keyed by exact name.
ROUTE_NAME_COLORS = {
    "Kirkuk–Ceyhan Oil Pipeline": "#b71c1c",  # dark red - currently NOT operational
}
NON_OPERATIONAL_ROUTES = {"Kirkuk–Ceyhan Oil Pipeline"}

# Human-readable labels for the route categories (legend + filters)
ROUTE_LABELS = {
    "Pipelines crude": "Crude pipelines",
    "Pipelines refined products": "Refined-product pipelines",
    "Maritime routes": "Maritime routes",
}


@st.cache_data
def load_data(path):
    return parse_kml(path)


def color_dot(color):
    """Inline HTML dot of the given colour, for the sidebar legend."""
    return (
        f"<span style='display:inline-block;width:12px;height:12px;"
        f"border-radius:50%;background:{color};margin-right:8px;"
        f"vertical-align:middle;border:1px solid #00000022'></span>"
    )


def line_swatch(color, dashed=False):
    """Inline HTML line swatch for the route legend."""
    style = "dashed" if dashed else "solid"
    return (
        f"<span style='display:inline-block;width:22px;height:0;"
        f"border-top:3px {style} {color};margin-right:8px;"
        f"vertical-align:middle'></span>"
    )


# Labels used in the KML descriptions. Each is put on its own line (bold) when
# found, turning a dense block into an airy fact sheet. Longer/more specific
# labels are listed first so they win over their shorter prefixes.
DESCRIPTION_LABELS = [
    "Latitude / Longitude",
    "Coordinate confidence",
    "Connected infrastructure",
    "Industrial integration",
    "Storage infrastructure",
    "Energy-transition role",
    "Berths / vessel size",
    "Main export markets",
    "Operating history",
    "Recent development",
    "Recent operations",
    "Nearest settlement",
    "Crude-import role",
    "Renewable capacity",
    "Alternative name",
    "Pipeline capacity",
    "Nominal capacity",
    "Planned capacity",
    "Storage capacity",
    "Current capacity",
    "Main feedstocks",
    "Main facilities",
    "Main activities",
    "Main commodities",
    "Main functions",
    "Main products",
    "Refining cluster",
    "Strategic role",
    "Bunkering role",
    "Owner/Operator",
    "Classification",
    "Infrastructure",
    "Configuration",
    "Connectivity",
    "Connected to",
    "Recent data",
    "Main markets",
    "Export role",
    "Marine role",
    "Crude flows",
    "Operated by",
    "Integration",
    "Asset type",
    "Feedstocks",
    "Feedstock",
    "Logistics",
    "Operator",
    "Capacity",
    "Location",
    "Refinery",
    "Terminal",
    "Facility",
    "Markets",
    "Sulphur",
    "Used for",
    "Vessels",
    "Pricing",
    "Transit",
    "Handles",
    "Process",
    "Country",
    "Region",
    "Origin",
    "Sulfur",
    "Status",
    "Source",
    "Output",
    "Crude",
    "Owner",
    "Input",
    "Risks",
    "Route",
    "Site",
    "Role",
    "Type",
    "Hub",
    "API",
]

# A label must start at a word boundary and be followed by a colon.
_LABEL_RE = re.compile(
    r"\s*(?<![A-Za-z])(" + "|".join(re.escape(l) for l in DESCRIPTION_LABELS) + r")\s*:"
)


def format_description(text):
    """Turn a dense labelled description into an airy, one-field-per-line block.

    Runs at display time only — the KML itself is never modified. Free-text
    descriptions without known labels are returned essentially unchanged.
    """
    if not text:
        return ""
    cleaned = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    cleaned = cleaned.replace("&nbsp;", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    formatted = _LABEL_RE.sub(lambda m: f"<br><b>{m.group(1)}:</b> ", cleaned)
    formatted = re.sub(r"^\s*<br>\s*", "", formatted)
    return formatted


def popup_html(name, description):
    """Scrollable popup: title + formatted, height-capped body."""
    body = format_description(description) if description else ""
    inner = "<div style='font-family:Arial,sans-serif;font-size:13px;line-height:1.45'>"
    inner += f"<div style='font-weight:bold;font-size:14px;margin-bottom:4px'>{name}</div>"
    if body:
        inner += (
            "<div style='max-height:260px;overflow-y:auto;padding-right:6px'>"
            f"{body}</div>"
        )
    inner += "</div>"
    return inner


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
kml_file, kml_warning = resolve_kml_path(KML_PATH)
if kml_file is None:
    st.error(kml_warning)
    st.stop()

data = load_data(kml_file)
route_categories = [c for c in data["categories"] if c in ROUTE_COLORS]
point_categories = [c for c in data["categories"] if c not in ROUTE_COLORS]

st.title("Global Energy Infrastructure Map")
st.caption(
    "Refineries, storage, terminals, ports, production fields and logistics flows "
    "(crude pipelines, product pipelines, maritime routes) into the European hubs "
    "(Rotterdam / ARA)."
)
if kml_warning:
    st.warning(kml_warning)

# ---------------------------------------------------------------------------
# SIDEBAR: filters + legend combined (colour swatch next to each checkbox)
# ---------------------------------------------------------------------------
st.sidebar.header("Map controls")
st.sidebar.caption(
    "Use the arrow at the top-left of the sidebar to collapse this panel "
    "and view the map full-width."
)

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
        route_visibility[route_cat] = st.checkbox(
            f"{label}  ({count})", value=True, key=f"route_{route_cat}"
        )

st.sidebar.markdown(
    line_swatch("#b71c1c", dashed=True)
    + "<span style='vertical-align:middle'>Non-operational (e.g. Kirkuk–Ceyhan)</span>",
    unsafe_allow_html=True,
)

st.sidebar.divider()

search = st.sidebar.text_input("Search a location by name")

filtered_points = [
    p for p in data["points"]
    if p["category"] in selected_categories
    and (search.lower() in p["name"].lower() if search else True)
]

st.sidebar.markdown(
    f"**{len(filtered_points)}** markers shown out of {len(data['points'])} total."
)

# ---------------------------------------------------------------------------
# MAP
# ---------------------------------------------------------------------------
m = folium.Map(
    location=[30, 15],
    zoom_start=3,
    min_zoom=2,
    max_bounds=True,
    tiles=None,
)
folium.TileLayer("cartodbpositron", no_wrap=True, control=False).add_to(m)

# Points, one FeatureGroup per category
for category in point_categories:
    if category not in selected_categories:
        continue
    group = folium.FeatureGroup(name=category, show=True)
    color = CATEGORY_COLORS.get(category, DEFAULT_COLOR)
    for point in (p for p in filtered_points if p["category"] == category):
        folium.CircleMarker(
            location=[point["lat"], point["lon"]],
            radius=6,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            tooltip=point["name"],
            popup=folium.Popup(popup_html(point["name"], point["description"]), max_width=320),
        ).add_to(group)
    group.add_to(m)

# Routes, native Leaflet highlight_function (hover thickens the line)
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

        popup_content = None
        if name != "(unnamed)":
            popup_content = popup_html(name, line.get("description", ""))

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
        if popup_content:
            gj.add_child(folium.Popup(popup_content, max_width=340))
        gj.add_to(group)
    group.add_to(m)

st_folium(m, width=None, height=700, returned_objects=[])
