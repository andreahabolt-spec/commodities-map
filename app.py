import glob
import os
import re

import streamlit as st
import folium
from streamlit_folium import st_folium

from kml_parser import parse_kml

st.set_page_config(page_title="Commodities Trading Map", layout="wide")

# Expected data file. If missing, fall back to any .kml in the folder.
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
    "Mega-refineries": "#5d4037",
    "Refineries": "#8d6e63",
    "Major Oil Storage & Distribution Terminals": "#d32f2f",
    "Ports & Maritime Logistics Hubs": "#1976d2",
    "Offshore tanker loading terminal": "#ad1457",
    "Oil Fields": "#388e3c",
    "Renewable Fuels & Low-Carbon Production Sites": "#00c853",
    "Ammonia production sites": "#f9a825",
    "Petrochemical Plants": "#000000",
    "Major Industrial & Energy Hubs": "#7b1fa2",
    "Aviation Fuel Demand": "#00acc1",
}
DEFAULT_COLOR = "#3388ff"

# --- Minimal flat SVG glyphs per category (one recognisable symbol each) ---
# Each glyph is a tiny set of primitives in a 24x24 viewBox, filled with the
# category colour. A white drop-shadow halo keeps them readable on the basemap.
GLYPHS = {
    # factory silhouette + chimney
    "Refineries":
        "<rect x='4' y='4' width='2.6' height='7' fill='{c}'/>"
        "<path d='M3 21V10.5l5.4 2.7v-2.7l5.4 2.7v-2.7l6.2-3.1V21H3z' fill='{c}'/>",
    "Mega-refineries":
        "<rect x='4' y='4' width='2.6' height='7' fill='{c}'/>"
        "<path d='M3 21V10.5l5.4 2.7v-2.7l5.4 2.7v-2.7l6.2-3.1V21H3z' fill='{c}'/>",
    # storage tank (cylinder)
    "Major Oil Storage & Distribution Terminals":
        "<rect x='5' y='7' width='14' height='11' rx='1.5' fill='{c}'/>"
        "<ellipse cx='12' cy='7' rx='7' ry='2.6' fill='{c}' stroke='white' stroke-width='0.9'/>",
    # anchor
    "Ports & Maritime Logistics Hubs":
        "<circle cx='12' cy='5' r='2.1' fill='none' stroke='{c}' stroke-width='2'/>"
        "<path d='M12 7.2V19M5.2 14.2c.6 3 3 4.8 6.8 4.8s6.2-1.8 6.8-4.8' "
        "stroke='{c}' stroke-width='2.4' fill='none' stroke-linecap='round'/>"
        "<path d='M8.6 10.6h6.8' stroke='{c}' stroke-width='2' stroke-linecap='round'/>",
    # SPM buoy (ring)
    "Offshore tanker loading terminal":
        "<circle cx='12' cy='12' r='6.2' fill='none' stroke='{c}' stroke-width='4.2'/>",
    # derrick (A-frame)
    "Oil Fields":
        "<path d='M12 3L6.2 21h2.4l3.4-10.6L15.4 21h2.4L12 3z' fill='{c}'/>"
        "<path d='M8.9 13.4h6.2' stroke='{c}' stroke-width='1.6'/>",
    # leaf
    "Renewable Fuels & Low-Carbon Production Sites":
        "<path d='M5 19c0-8 6.5-13.2 14-14-1 8-6.5 13-14 14z' fill='{c}'/>"
        "<path d='M6.5 17.5C9.5 13 13.5 9.5 17 7.5' stroke='white' stroke-width='1.2' fill='none'/>",
    # hexagon (chemical)
    "Ammonia production sites":
        "<path d='M12 3l7.2 4.1v8.2L12 19.4l-7.2-4.1V7.1L12 3z' fill='{c}'/>",
    # Erlenmeyer flask
    "Petrochemical Plants":
        "<path d='M10 3h4v2.2l-1 1v3.6l5.6 8.4A2 2 0 0 1 16.9 21H7.1a2 2 0 0 1"
        " -1.7-2.8L11 9.8V6.2l-1-1V3z' fill='{c}'/>",
    # star
    "Major Industrial & Energy Hubs":
        "<path d='M12 2.5l2.8 5.9 6.4.8-4.7 4.4 1.2 6.3L12 16.9l-5.7 3 1.2-6.3"
        "L2.8 9.2l6.4-.8L12 2.5z' fill='{c}'/>",
    # plane
    "Aviation Fuel Demand":
        "<path d='M21.5 15.2l-8.3-4.2V4.6a1.2 1.2 0 0 0-2.4 0V11l-8.3 4.2v2.3"
        "l8.3-2.6v3.9l-2.2 1.6v1.4l3.4-1 3.4 1v-1.4l-2.2-1.6v-3.9l8.3 2.6v-2.3z' fill='{c}'/>",
}

ICON_SIZE = {"Mega-refineries": 30, "Major Industrial & Energy Hubs": 26}
DEFAULT_ICON_SIZE = 21


def category_icon_svg(category, size):
    """Inline SVG glyph for a category, with a white halo for readability."""
    color = CATEGORY_COLORS.get(category, DEFAULT_COLOR)
    glyph = GLYPHS.get(category, "<circle cx='12' cy='12' r='7' fill='{c}'/>")
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' "
        f"viewBox='0 0 24 24' "
        f"style='filter:drop-shadow(0 0 1.4px #fff) drop-shadow(0 0 1.4px #fff)'>"
        + glyph.format(c=color) + "</svg>"
    )


def category_marker_icon(category):
    size = ICON_SIZE.get(category, DEFAULT_ICON_SIZE)
    return folium.DivIcon(
        html=category_icon_svg(category, size),
        icon_size=(size, size),
        icon_anchor=(size // 2, size // 2),
        class_name="svg-marker",
    )


# Route categories (LineString folders) -> line colour.
ROUTE_COLORS = {
    "Pipelines crude": "#e65100",
    "Pipelines refined products": "#fdd835",
    "Maritime routes": "#2dc0fb",
}
DEFAULT_ROUTE_COLOR = "#2dc0fb"
CASING_COLOR = "#37474f"  # dark under-stroke giving pipelines a "tube" look

ROUTE_NAME_COLORS = {
    "Kirkuk–Ceyhan Oil Pipeline": "#b71c1c",  # dark red - currently NOT operational
}
NON_OPERATIONAL_ROUTES = {"Kirkuk–Ceyhan Oil Pipeline"}

ROUTE_LABELS = {
    "Pipelines crude": "Crude pipelines",
    "Pipelines refined products": "Refined-product pipelines",
    "Maritime routes": "Maritime routes",
}


@st.cache_data
def load_data(path):
    return parse_kml(path)


def line_swatch(color, dashed=False, casing=False):
    """Inline HTML line swatch for the route legend."""
    style = "dashed" if dashed else "solid"
    shadow = f"box-shadow:0 1.5px 0 0 {CASING_COLOR};" if casing else ""
    return (
        f"<span style='display:inline-block;width:22px;height:0;"
        f"border-top:3px {style} {color};{shadow}margin-right:8px;"
        f"vertical-align:middle'></span>"
    )


# Labels used in the KML descriptions (longer/more specific first).
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

_LABEL_RE = re.compile(
    r"\s*(?<![A-Za-z])(" + "|".join(re.escape(l) for l in DESCRIPTION_LABELS) + r")\s*:"
)


def format_description(text):
    """Dense labelled description -> airy one-field-per-line block (display only)."""
    if not text:
        return ""
    cleaned = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    cleaned = cleaned.replace("&nbsp;", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    formatted = _LABEL_RE.sub(lambda m: f"<br><b>{m.group(1)}:</b> ", cleaned)
    return re.sub(r"^\s*<br>\s*", "", formatted)


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
# SIDEBAR: filters + legend (the category icon doubles as the legend symbol)
# ---------------------------------------------------------------------------
st.sidebar.header("Map controls")
st.sidebar.caption(
    "Use the arrow at the top-left of the sidebar to collapse this panel "
    "and view the map full-width."
)

st.sidebar.subheader("Infrastructure (points)")
selected_categories = []
for category in point_categories:
    count = sum(1 for p in data["points"] if p["category"] == category)
    cols = st.sidebar.columns([0.13, 0.87])
    with cols[0]:
        st.markdown(category_icon_svg(category, 18), unsafe_allow_html=True)
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
    cols = st.sidebar.columns([0.13, 0.87])
    with cols[0]:
        st.markdown(
            line_swatch(color, casing=("Pipelines" in route_cat)),
            unsafe_allow_html=True,
        )
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

# DivIcon markers get a white box by default in Leaflet — make them transparent.
m.get_root().html.add_child(folium.Element(
    "<style>.svg-marker{background:transparent;border:none;}</style>"
))

# Points: one FeatureGroup per category, each marker a flat SVG glyph
for category in point_categories:
    if category not in selected_categories:
        continue
    group = folium.FeatureGroup(name=category, show=True)
    for point in (p for p in filtered_points if p["category"] == category):
        folium.Marker(
            location=[point["lat"], point["lon"]],
            icon=category_marker_icon(category),
            tooltip=point["name"],
            popup=folium.Popup(popup_html(point["name"], point["description"]), max_width=320),
        ).add_to(group)
    group.add_to(m)

# Routes: dark casing underneath + coloured line on top ("tube" look),
# native Leaflet highlight on hover. Non-operational lines stay pure dashed red.
for route_cat in route_categories:
    if not route_visibility.get(route_cat, True):
        continue
    default_color = ROUTE_COLORS.get(route_cat, DEFAULT_ROUTE_COLOR)
    is_pipeline = "Pipelines" in route_cat
    group = folium.FeatureGroup(name=route_cat, show=True)
    for line in (l for l in data["lines"] if l["category"] == route_cat):
        name = line["name"]
        color = ROUTE_NAME_COLORS.get(name, default_color)
        non_op = name in NON_OPERATIONAL_ROUTES
        dash = "8, 8" if non_op else None

        tooltip_text = f"{name} — NOT operational" if non_op else (
            name if name != "(unnamed)" else ""
        )
        popup_content = popup_html(name, line.get("description", "")) if name != "(unnamed)" else None

        geojson = {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "LineString",
                "coordinates": [[lon, lat] for (lat, lon) in line["coords"]],
            },
        }

        # casing first (non-interactive), pipelines only, skipped for dashed lines
        if is_pipeline and not non_op:
            folium.GeoJson(
                geojson,
                style_function=lambda _f: {
                    "color": CASING_COLOR, "weight": 6, "opacity": 0.55,
                },
                control=False,
            ).add_to(group)

        base_style = {"color": color, "weight": 3.2, "opacity": 0.95}
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