"""
KML -> Python parser (points + routes) for the Streamlit map.

Works with a KML exported from Google Earth (web Projects or Pro), organised into
one <Folder> per category, each <Folder> holding <Placemark> elements that are
either Point (marker) or LineString (route).
"""

import re
import xml.etree.ElementTree as ET

NS = {"kml": "http://www.opengis.net/kml/2.2"}


def _text(el, tag, default=""):
    node = el.find(f"kml:{tag}", NS)
    return node.text.strip() if node is not None and node.text else default


def parse_kml(path):
    """
    Returns a dict:
    {
        "points": [{"name": str, "description": str, "lat": float, "lon": float, "category": str}, ...],
        "lines":  [{"name": str, "coords": [(lat, lon), ...], "category": str}, ...],
        "categories": [str, ...]  # in file order
    }
    """
    tree = ET.parse(path)
    root = tree.getroot()
    document = root.find("kml:Document", NS)

    points = []
    lines = []
    categories = []

    for folder in document.findall("kml:Folder", NS):
        raw_name = _text(folder, "name", "Uncategorised")
        # strip only an auto-generated numeric count, e.g. "Refineries (57)" -> "Refineries",
        # while preserving descriptive parentheses like "Ports (fuel demand sites)".
        category = re.sub(r"\s*\(\d+\)\s*$", "", raw_name).strip()
        if category not in categories:
            categories.append(category)

        for placemark in folder.findall("kml:Placemark", NS):
            name = _text(placemark, "name", "(unnamed)")
            description = _text(placemark, "description", "")

            point_el = placemark.find("kml:Point", NS)
            if point_el is not None:
                coord_text = _text(point_el, "coordinates")
                if coord_text:
                    lon, lat, *_ = coord_text.split(",")
                    points.append({
                        "name": name,
                        "description": description,
                        "lat": float(lat),
                        "lon": float(lon),
                        "category": category,
                    })
                continue

            line_el = placemark.find("kml:LineString", NS)
            if line_el is not None:
                coord_text = _text(line_el, "coordinates")
                if coord_text:
                    coords = []
                    for triplet in coord_text.split():
                        lon, lat, *_ = triplet.split(",")
                        coords.append((float(lat), float(lon)))
                    lines.append({
                        "name": name,
                        "description": description,
                        "coords": coords,
                        "category": category,
                    })

    return {"points": points, "lines": lines, "categories": categories}


if __name__ == "__main__":
    import sys
    data = parse_kml(sys.argv[1] if len(sys.argv) > 1 else "Commodities_Trading_EN.kml")
    print("Categories:", data["categories"])
    print("Points:", len(data["points"]))
    print("Routes:", len(data["lines"]))
