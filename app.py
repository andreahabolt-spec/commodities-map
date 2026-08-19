import glob
import os
import re

import streamlit as st
import folium
from streamlit_folium import st_folium

from kml_parser import parse_kml, get_field

st.set_page_config(page_title="Commodities Trading Map", layout="wide")

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


# ---------------------------------------------------------------------------
# TAXONOMY: main section -> colour. Names must match the KML section folders.
# ---------------------------------------------------------------------------
CATEGORY_COLORS = {
    # A. Production
    "Oil Fields": "#388e3c",
    "Refineries": "#8d6e63",
    "Biofuel & Low-Carbon Production": "#00c853",
    # B. Gateways
    "Crude Terminals (import / export)": "#d32f2f",
    "Ports & Logistics Hubs": "#1976d2",
    # D. Storage & Pricing
    "Product Storage & Depots": "#880e4f",
    "Pricing Hubs": "#f9a825",
    # E. Demand & Constraints
    "Petrochemical Plants": "#000000",
    "Aviation Fuel Demand": "#00acc1",
    "Chokepoints": "#b71c1c",
    # C. Corridors — point assets that live inside corridor folders (e.g. gauges)
    "Inland Waterways": "#00897b",
}
DEFAULT_COLOR = "#3388ff"

# Sub-sections that change the glyph or size within a section
MEGA_SUBSECTION = "Mega-refineries"
OFFSHORE_SUBSECTION = "Offshore tanker loading terminals (SPM / CALM / SBM)"

# Route sections -> line colour
ROUTE_COLORS = {
    "Crude Pipelines": "#e65100",
    "Product Pipelines": "#fdd835",
    "Maritime Routes": "#2dc0fb",
    "Inland Waterways": "#00897b",
}
DEFAULT_ROUTE_COLOR = "#2dc0fb"
CASING_COLOR = "#37474f"

STAGE_LABELS = {
    "A. Production": "A · Production",
    "B. Gateways": "B · Gateways",
    "C. Corridors": "C · Corridors",
    "D. Storage & Pricing": "D · Storage & Pricing",
    "E. Demand & Constraints": "E · Demand & Constraints",
}
STAGE_ORDER = list(STAGE_LABELS.keys())

STATUS_VALUES = ["Operational", "Reduced", "Offline", "Planned", "Converting"]


def normalize_status(raw):
    """Map a free-text Status: value onto one of STATUS_VALUES."""
    s = (raw or "").strip().lower()
    if not s:
        return "Operational"
    first = s.split()[0]
    for v in STATUS_VALUES:
        if first.startswith(v.lower()[:4]):
            return v
    if any(k in s for k in ("offline", "shut", "halted", "closed", "idle", "suspend", "not operational", "non-operational")):
        return "Offline"
    if any(k in s for k in ("reduced", "record low", "disrupt", "constrain", "limited", "partial", "low water", "hot standby")):
        return "Reduced"
    if any(k in s for k in ("planned", "proposed", "under construction", "construction")):
        return "Planned"
    if any(k in s for k in ("convert", "transform", "repurpos")):
        return "Converting"
    return "Operational"

# ---------------------------------------------------------------------------
# GLYPHS (flat SVG, 24x24 viewBox). One per section; sub-section variants below.
# ---------------------------------------------------------------------------
GLYPHS = {
    "Refineries":
        "<rect x='4' y='4' width='2.6' height='7' fill='{c}'/>"
        "<path d='M3 21V10.5l5.4 2.7v-2.7l5.4 2.7v-2.7l6.2-3.1V21H3z' fill='{c}'/>",
    "Biofuel & Low-Carbon Production":
        "<path d='M5 19c0-8 6.5-13.2 14-14-1 8-6.5 13-14 14z' fill='{c}'/>"
        "<path d='M6.5 17.5C9.5 13 13.5 9.5 17 7.5' stroke='white' stroke-width='1.2' fill='none'/>",
    "Oil Fields":
        "<path d='M12 3L6.2 21h2.4l3.4-10.6L15.4 21h2.4L12 3z' fill='{c}'/>"
        "<path d='M8.9 13.4h6.2' stroke='{c}' stroke-width='1.6'/>",
    "Crude Terminals (import / export)":
        "<rect x='5' y='7' width='14' height='11' rx='1.5' fill='{c}'/>"
        "<ellipse cx='12' cy='7' rx='7' ry='2.6' fill='{c}' stroke='white' stroke-width='0.9'/>",
    "Product Storage & Depots":
        "<rect x='5' y='7' width='14' height='11' rx='1.5' fill='{c}'/>"
        "<ellipse cx='12' cy='7' rx='7' ry='2.6' fill='{c}' stroke='white' stroke-width='0.9'/>"
        "<path d='M8 13h8' stroke='white' stroke-width='1.6' stroke-linecap='round'/>",
    "Ports & Logistics Hubs":
        "<circle cx='12' cy='5' r='2.1' fill='none' stroke='{c}' stroke-width='2'/>"
        "<path d='M12 7.2V19M5.2 14.2c.6 3 3 4.8 6.8 4.8s6.2-1.8 6.8-4.8' "
        "stroke='{c}' stroke-width='2.4' fill='none' stroke-linecap='round'/>"
        "<path d='M8.6 10.6h6.8' stroke='{c}' stroke-width='2' stroke-linecap='round'/>",
    "Pricing Hubs":
        "<path d='M12 2.5l9 9.5-9 9.5-9-9.5z' fill='{c}'/>"
        "<path d='M12 7v10M9.3 9.4h4.2a1.6 1.6 0 0 1 0 3.2H10.5a1.6 1.6 0 0 0 0 3.2h4.2' "
        "stroke='white' stroke-width='1.3' fill='none' stroke-linecap='round'/>",
    "Petrochemical Plants":
        "<path d='M10 3h4v2.2l-1 1v3.6l5.6 8.4A2 2 0 0 1 16.9 21H7.1a2 2 0 0 1"
        " -1.7-2.8L11 9.8V6.2l-1-1V3z' fill='{c}'/>",
    "Aviation Fuel Demand":
        "<path d='M21.5 15.2l-8.3-4.2V4.6a1.2 1.2 0 0 0-2.4 0V11l-8.3 4.2v2.3"
        "l8.3-2.6v3.9l-2.2 1.6v1.4l3.4-1 3.4 1v-1.4l-2.2-1.6v-3.9l8.3 2.6v-2.3z' fill='{c}'/>",
    "Chokepoints":
        "<path d='M12 3L2.5 20h19L12 3z' fill='{c}'/>"
        "<path d='M12 9v5' stroke='white' stroke-width='2.2' stroke-linecap='round'/>"
        "<circle cx='12' cy='17' r='1.2' fill='white'/>",
    "Inland Waterways":  # gauge glyph for points inside the waterways folder
        "<rect x='10.6' y='3' width='2.8' height='18' fill='{c}'/>"
        "<path d='M8 6h4M8 10h4M8 14h4M8 18h4' stroke='{c}' stroke-width='1.8' stroke-linecap='round'/>"
        "<path d='M3 20c2-1.6 4-1.6 6 0s4 1.6 6 0 4-1.6 6 0' stroke='{c}' stroke-width='1.8' fill='none'/>",
}
# sub-section glyph overrides
GLYPH_OFFSHORE = "<circle cx='12' cy='12' r='6.2' fill='none' stroke='{c}' stroke-width='4.2'/>"

DEFAULT_ICON_SIZE = 21
MEGA_ICON_SIZE = 30


def glyph_for(category, subsection):
    if category == "Crude Terminals (import / export)" and subsection == OFFSHORE_SUBSECTION:
        return GLYPH_OFFSHORE
    return GLYPHS.get(category, "<circle cx='12' cy='12' r='7' fill='{c}'/>")


def icon_size_for(category, subsection):
    if category == "Refineries" and subsection == MEGA_SUBSECTION:
        return MEGA_ICON_SIZE
    return DEFAULT_ICON_SIZE


def color_for(category, subsection):
    c = CATEGORY_COLORS.get(category, DEFAULT_COLOR)
    if category == "Refineries" and subsection == MEGA_SUBSECTION:
        return "#5d4037"   # darker brown for mega
    return c


def category_icon_svg(category, subsection="", size=DEFAULT_ICON_SIZE, status="Operational"):
    """Inline SVG glyph with white halo. Offline/Planned/Converting get a status ring."""
    color = color_for(category, subsection)
    glyph = glyph_for(category, subsection).format(c=color)
    ring = ""
    s = (status or "Operational").lower()
    if s.startswith("off"):
        ring = "<circle cx='12' cy='12' r='11' fill='none' stroke='#b71c1c' stroke-width='1.6' stroke-dasharray='3 2'/>"
    elif s.startswith("plan"):
        ring = "<circle cx='12' cy='12' r='11' fill='none' stroke='#607d8b' stroke-width='1.4' stroke-dasharray='1.5 2.5'/>"
    elif s.startswith("conv"):
        ring = "<circle cx='12' cy='12' r='11' fill='none' stroke='#00897b' stroke-width='1.6' stroke-dasharray='4 2'/>"
    elif s.startswith("red"):
        ring = "<circle cx='12' cy='12' r='11' fill='none' stroke='#ef6c00' stroke-width='1.4'/>"
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' viewBox='0 0 24 24' "
        f"style='filter:drop-shadow(0 0 1.4px #fff) drop-shadow(0 0 1.4px #fff)'>"
        + ring + glyph + "</svg>"
    )


def marker_icon(category, subsection, status):
    size = icon_size_for(category, subsection)
    return folium.DivIcon(
        html=category_icon_svg(category, subsection, size, status),
        icon_size=(size, size),
        icon_anchor=(size // 2, size // 2),
        class_name="svg-marker",
    )


def line_swatch(color, dashed=False, casing=False):
    style = "dashed" if dashed else "solid"
    shadow = f"box-shadow:0 1.5px 0 0 {CASING_COLOR};" if casing else ""
    return (
        f"<span style='display:inline-block;width:22px;height:0;border-top:3px {style} {color};"
        f"{shadow}margin-right:8px;vertical-align:middle'></span>"
    )


# ---------------------------------------------------------------------------
# DESCRIPTION FORMATTING
# ---------------------------------------------------------------------------
DESCRIPTION_LABELS = [
    "Latitude / Longitude", "Coordinate confidence", "Connected infrastructure", "Industrial integration",
    "Storage infrastructure", "Energy-transition role", "Berths / vessel size", "Main export markets",
    "Operating history", "Recent development", "Recent operations", "Nearest settlement", "Crude-import role",
    "Renewable capacity", "Alternative name", "Pipeline capacity", "Nominal capacity", "Planned capacity",
    "Storage capacity", "Current capacity", "Main feedstocks", "Main facilities", "Main activities",
    "Main commodities", "Main functions", "Main products", "Refining cluster", "Strategic role",
    "Bunkering role", "Owner/Operator", "Classification", "Infrastructure", "Configuration", "Connectivity",
    "Connected to", "Recent data", "Main markets", "Export role", "Marine role", "Crude flows", "Operated by",
    "Integration", "Asset type", "Renewables", "Feedstocks", "Feedstock", "Logistics", "Operator", "Capacity",
    "Location", "Refinery", "Terminal", "Facility", "Markets", "Sulphur", "Used for", "Vessels", "Pricing",
    "Transit", "Handles", "Process", "Country", "Region", "Origin", "Sulfur", "Status", "Source", "Output",
    "Recent", "Crude", "Owner", "Input", "Risks", "Route", "Site", "Role", "Type", "Hub", "API",
]
_LABEL_RE = re.compile(r"\s*(?<![A-Za-z])(" + "|".join(re.escape(l) for l in DESCRIPTION_LABELS) + r")\s*:")

STATUS_BADGE = {
    "operational": ("#2e7d32", "Operational"),
    "reduced": ("#ef6c00", "Reduced"),
    "offline": ("#b71c1c", "Offline"),
    "planned": ("#607d8b", "Planned"),
    "converting": ("#00897b", "Converting"),
}


def format_description(text):
    if not text:
        return ""
    cleaned = re.sub(r"<br\s*/?>", " ", text, flags=re.I).replace("&nbsp;", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    formatted = _LABEL_RE.sub(lambda m: f"<br><b>{m.group(1)}:</b> ", cleaned)
    # drop the Status field from the body (it is rendered as a badge in the header)
    formatted = re.sub(r"<br><b>Status:</b>\s*.*?(?=<br><b>|$)", "", formatted, flags=re.S)
    return re.sub(r"^\s*<br>\s*", "", formatted).strip()


def popup_html(name, description, category="", subsection=""):
    status = normalize_status(get_field(description, "Status"))
    col, label = STATUS_BADGE.get(status.lower(), ("#2e7d32", status))
    body = format_description(description) if description else ""
    tag = f"<span style='color:#666;font-size:11px'>{category}" + (f" · {subsection}" if subsection else "") + "</span>"
    badge = (f"<span style='background:{col};color:#fff;border-radius:10px;padding:1px 8px;"
             f"font-size:11px;margin-left:6px;vertical-align:middle'>{label}</span>")
    inner = "<div style='font-family:Arial,sans-serif;font-size:13px;line-height:1.45'>"
    inner += f"<div style='font-weight:bold;font-size:14px;margin-bottom:2px'>{name}{badge}</div>"
    inner += f"<div style='margin-bottom:6px'>{tag}</div>"
    if body:
        inner += f"<div style='max-height:250px;overflow-y:auto;padding-right:6px'>{body}</div>"
    inner += "</div>"
    return inner


# ---------------------------------------------------------------------------
# DATA
# ---------------------------------------------------------------------------
kml_file, kml_warning = resolve_kml_path(KML_PATH)
if kml_file is None:
    st.error(kml_warning); st.stop()

@st.cache_data
def load_data(path, mtime):
    return parse_kml(path)

data = load_data(kml_file, os.path.getmtime(kml_file))

all_items = data["points"] + data["lines"]
for it in all_items:
    it["status"] = normalize_status(get_field(it["description"], "Status"))
    it["renewables"] = get_field(it["description"], "Renewables")

route_categories = [c for c in data["categories"] if c in ROUTE_COLORS and any(l["category"] == c for l in data["lines"])]
point_categories = [c for c in data["categories"] if any(p["category"] == c for p in data["points"])]

st.title("Global Energy Infrastructure Map")
st.caption("The oil value chain — production, gateways, corridors, storage & pricing, demand & constraints — "
           "with physical flows into the European hubs (Rotterdam / ARA).")
if kml_warning:
    st.warning(kml_warning)

# ---------------------------------------------------------------------------
# SIDEBAR — grouped by value-chain stage; glyph = legend; sub-sections indented
# ---------------------------------------------------------------------------
st.sidebar.header("Map controls")
st.sidebar.caption("Collapse this panel with the arrow at the top-left to view the map full-width.")

selected_categories = set()
route_visibility = {}
selected_subsections = {}   # category -> set of selected subsections (None = all)

def subsections_of(cat):
    subs = []
    for it in all_items:
        if it["category"] == cat and it["subsection"] and it["subsection"] not in subs:
            subs.append(it["subsection"])
    return subs

for stage in STAGE_ORDER:
    cats_in_stage = [c for c in data["categories"] if data["stages"].get(c) == stage]
    if not cats_in_stage:
        continue
    st.sidebar.subheader(STAGE_LABELS[stage])
    for cat in cats_in_stage:
        n_pts = sum(1 for p in data["points"] if p["category"] == cat)
        n_lns = sum(1 for l in data["lines"] if l["category"] == cat)
        is_route = cat in ROUTE_COLORS and n_lns > 0
        cols = st.sidebar.columns([0.13, 0.87])
        with cols[0]:
            if is_route:
                st.markdown(line_swatch(ROUTE_COLORS[cat], casing=("Pipelines" in cat)), unsafe_allow_html=True)
            else:
                st.markdown(category_icon_svg(cat, "", 18), unsafe_allow_html=True)
        with cols[1]:
            count = n_pts + n_lns
            label = f"{cat}  ({count})" if count else f"{cat}  (empty)"
            checked = st.checkbox(label, value=bool(count), key=f"cat_{cat}", disabled=not count)
        if is_route:
            route_visibility[cat] = checked
        if n_pts and checked:
            selected_categories.add(cat)
        # sub-section expander (only when a section has 2+ subsections)
        subs = subsections_of(cat)
        if checked and len(subs) >= 2:
            with st.sidebar.expander(f"   types in {cat.split(' (')[0]}", expanded=False):
                chosen = set()
                for s in subs:
                    n = sum(1 for it in all_items if it["category"] == cat and it["subsection"] == s)
                    if st.checkbox(f"{s} ({n})", value=True, key=f"sub_{cat}_{s}"):
                        chosen.add(s)
                selected_subsections[cat] = chosen

st.sidebar.divider()
st.sidebar.subheader("Filters")
status_pick = st.sidebar.multiselect("Status", STATUS_VALUES, default=STATUS_VALUES)
renew_only = st.sidebar.checkbox("Only refineries with renewables", value=False)
search = st.sidebar.text_input("Search a location by name")

def keep(it):
    if it["category"] in selected_subsections and it["subsection"] and it["subsection"] not in selected_subsections[it["category"]]:
        return False
    if it["status"] not in status_pick:
        return False
    if renew_only and it["category"] == "Refineries" and (not it["renewables"] or it["renewables"].lower().startswith("none")):
        return False
    if search and search.lower() not in it["name"].lower():
        return False
    return True

filtered_points = [p for p in data["points"] if p["category"] in selected_categories and keep(p)]
st.sidebar.markdown(f"**{len(filtered_points)}** markers shown out of {len(data['points'])} total.")

# ---------------------------------------------------------------------------
# MAP
# ---------------------------------------------------------------------------
m = folium.Map(location=[30, 15], zoom_start=3, min_zoom=2, max_bounds=True, tiles=None)
folium.TileLayer("cartodbpositron", no_wrap=True, control=False).add_to(m)
m.get_root().html.add_child(folium.Element("<style>.svg-marker{background:transparent;border:none;}</style>"))

for cat in point_categories:
    if cat not in selected_categories:
        continue
    group = folium.FeatureGroup(name=cat, show=True)
    for p in (x for x in filtered_points if x["category"] == cat):
        folium.Marker(
            location=[p["lat"], p["lon"]],
            icon=marker_icon(cat, p["subsection"], p["status"]),
            tooltip=p["name"] + (f" — {p['status']}" if p["status"] != "Operational" else ""),
            popup=folium.Popup(popup_html(p["name"], p["description"], cat, p["subsection"]), max_width=330),
        ).add_to(group)
    group.add_to(m)

for cat in route_categories:
    if not route_visibility.get(cat, True):
        continue
    base_color = ROUTE_COLORS.get(cat, DEFAULT_ROUTE_COLOR)
    is_pipeline = "Pipelines" in cat
    is_waterway = cat == "Inland Waterways"
    group = folium.FeatureGroup(name=cat, show=True)
    for line in (l for l in data["lines"] if l["category"] == cat and keep(l)):
        name = line["name"]
        status = line["status"].lower()
        dash = "8, 8" if status.startswith("off") else ("2, 6" if status.startswith("plan") else None)
        opacity = 0.55 if status.startswith("red") else (0.85 if is_waterway else 0.95)
        tooltip_text = name + (f" — {line['status']}" if line["status"] != "Operational" else "")
        geojson = {"type": "Feature", "properties": {},
                   "geometry": {"type": "LineString", "coordinates": [[lon, lat] for (lat, lon) in line["coords"]]}}
        if is_pipeline and not dash:
            folium.GeoJson(geojson, style_function=lambda _f: {"color": CASING_COLOR, "weight": 6, "opacity": 0.55},
                           control=False).add_to(group)
        style = {"color": base_color, "weight": 4.2 if is_waterway else 3.2, "opacity": opacity}
        if dash:
            style["dashArray"] = dash
        gj = folium.GeoJson(geojson, style_function=lambda _f, s=dict(style): s,
                            highlight_function=lambda _f: {"weight": 7, "opacity": 1.0})
        gj.add_child(folium.Tooltip(tooltip_text))
        gj.add_child(folium.Popup(popup_html(name, line.get("description", ""), cat, line["subsection"]), max_width=340))
        gj.add_to(group)
    group.add_to(m)

st_folium(m, width=None, height=700, returned_objects=[])
