"""
KML -> Python parser (points + routes) for the Streamlit map.

Reads a KML organised as a tree of folders up to three levels deep:
    STAGE  >  MAIN SECTION  >  SUB-SECTION  >  placemarks
Each asset gets: stage, category (= main section, used for colour/glyph),
subsection (asset type), plus name, description and geometry.

Backward-compatible: a flat file (folders directly under Document) is read as
category-only, with stage and subsection empty. A two-level file is read as
stage > category with subsection empty.
"""

import re
import xml.etree.ElementTree as ET

NS = {"kml": "http://www.opengis.net/kml/2.2"}

STAGE_RE = re.compile(r"^[A-Z]\.\s")   # "A. Production", "B. Gateways", ...


def _text(el, tag, default=""):
    node = el.find(f"kml:{tag}", NS)
    return node.text.strip() if node is not None and node.text else default


def _clean_name(raw):
    # strip an auto-generated numeric count, e.g. "Refineries (57)" -> "Refineries"
    return re.sub(r"\s*\(\d+\)\s*$", "", raw).strip()


def _emit(placemark, stage, category, subsection, points, lines):
    name = _text(placemark, "name", "(unnamed)")
    description = _text(placemark, "description", "")

    point_el = placemark.find("kml:Point", NS)
    if point_el is not None:
        coord_text = _text(point_el, "coordinates")
        if coord_text:
            lon, lat, *_ = coord_text.split(",")
            points.append({
                "name": name, "description": description,
                "lat": float(lat), "lon": float(lon),
                "category": category, "stage": stage, "subsection": subsection,
            })
        return

    line_el = placemark.find("kml:LineString", NS)
    if line_el is not None:
        coord_text = _text(line_el, "coordinates")
        if coord_text:
            coords = []
            for triplet in coord_text.split():
                lon, lat, *_ = triplet.split(",")
                coords.append((float(lat), float(lon)))
            lines.append({
                "name": name, "description": description,
                "coords": coords,
                "category": category, "stage": stage, "subsection": subsection,
            })


def _walk(folder, path, points, lines, categories, stages):
    """Recursively walk folders. `path` is the list of folder names above this one."""
    fname = _clean_name(_text(folder, "name", "Uncategorised"))
    new_path = path + [fname]

    # Determine roles from position in the tree
    if len(new_path) == 1:
        if STAGE_RE.match(fname):
            stage, category, subsection = fname, None, ""
        else:
            stage, category, subsection = "", fname, ""
    elif len(new_path) == 2:
        stage = new_path[0] if STAGE_RE.match(new_path[0]) else ""
        category = fname if stage else new_path[0]
        subsection = "" if stage else fname
    else:
        stage = new_path[0] if STAGE_RE.match(new_path[0]) else ""
        category = new_path[1] if stage else new_path[0]
        subsection = fname

    if category and category not in categories:
        categories.append(category)
        stages[category] = stage

    for pm in folder.findall("kml:Placemark", NS):
        _emit(pm, stage, category or fname, subsection, points, lines)

    for sub in folder.findall("kml:Folder", NS):
        _walk(sub, new_path, points, lines, categories, stages)


def parse_kml(path):
    """
    Returns a dict:
    {
      "points": [{name, description, lat, lon, category, stage, subsection}, ...],
      "lines":  [{name, description, coords, category, stage, subsection}, ...],
      "categories": [...],            # main sections, in file order
      "stages": {category: stage},    # which stage each main section belongs to
    }
    """
    tree = ET.parse(path)
    root = tree.getroot()
    document = root.find("kml:Document", NS)

    points, lines, categories, stages = [], [], [], {}
    for folder in document.findall("kml:Folder", NS):
        _walk(folder, [], points, lines, categories, stages)

    # also tolerate placemarks directly under Document
    for pm in document.findall("kml:Placemark", NS):
        _emit(pm, "", "Uncategorised", "", points, lines)
        if "Uncategorised" not in categories:
            categories.append("Uncategorised"); stages["Uncategorised"] = ""

    return {"points": points, "lines": lines, "categories": categories, "stages": stages}


def get_field(description, field):
    """Read a 'Field: value' line from a description (e.g. get_field(d, 'Status'))."""
    if not description:
        return ""
    m = re.search(r"(?:^|\n|<br\s*/?>)\s*" + re.escape(field) + r"\s*:\s*([^\n<]+)", description, re.I)
    return m.group(1).strip() if m else ""


if __name__ == "__main__":
    import sys
    data = parse_kml(sys.argv[1] if len(sys.argv) > 1 else "Commodities_Trading.kml")
    print("Categories:", data["categories"])
    print("Stages:", data["stages"])
    print("Points:", len(data["points"]), "Routes:", len(data["lines"]))
