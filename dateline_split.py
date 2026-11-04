"""
Splits a route's coordinate list wherever it crosses the 180/-180 meridian,
so the map draws it as two separate segments instead of one line jumping
straight across the whole map. On a map that shows the full -180..180 range,
this makes the route visually "wrap": it exits at one edge and continues
from the opposite edge, instead of drawing a long incorrect line through the
middle of the map.

This does NOT change where the route goes -- only how it's split into pieces
for drawing. Use alongside correct great-circle waypoints, not instead of them.
"""


def split_at_antimeridian(coords):
    """
    coords: list of (lat, lon) tuples, in route order.
    Returns a list of coordinate-list segments. Most routes return a single
    segment (the original list, unchanged). A route that crosses the dateline
    returns two or more segments, split exactly at +180/-180.
    """
    if len(coords) < 2:
        return [coords]

    segments = []
    current = [coords[0]]

    for i in range(1, len(coords)):
        lat1, lon1 = current[-1]
        lat2, lon2 = coords[i]
        diff = lon2 - lon1

        if diff > 180:
            # short path actually heads toward -180 (wraps west)
            lon2_adj = lon2 - 360
            t = (-180 - lon1) / (lon2_adj - lon1)
            lat_cross = lat1 + t * (lat2 - lat1)
            current.append((lat_cross, -180.0))
            segments.append(current)
            current = [(lat_cross, 180.0), (lat2, lon2)]
        elif diff < -180:
            # short path actually heads toward +180 (wraps east)
            lon2_adj = lon2 + 360
            t = (180 - lon1) / (lon2_adj - lon1)
            lat_cross = lat1 + t * (lat2 - lat1)
            current.append((lat_cross, 180.0))
            segments.append(current)
            current = [(lat_cross, -180.0), (lat2, lon2)]
        else:
            current.append((lat2, lon2))

    segments.append(current)
    return segments


if __name__ == "__main__":
    coords = [
        (49.2926, -122.9503), (51.6799, -128.1922), (53.8088, -133.9837),
        (55.6305, -140.3472), (57.0928, -147.2660), (58.1456, -154.6695),
        (58.7471, -162.4242), (58.8707, -170.3418), (58.5109, -178.2057),
        (57.6839, 174.1911), (56.4245, 167.0123), (54.7796, 160.3604),
        (52.8010, 154.2779), (50.5396, 148.7603), (48.0421, 143.7721),
        (45.3491, 139.2623), (42.4951, 135.1738), (39.5086, 131.4500),
        (36.4133, 128.0387), (33.2284, 124.8925), (29.9700, 121.9700),
    ]
    segs = split_at_antimeridian(coords)
    print(f"{len(segs)} segment(s):")
    for seg in segs:
        print(f"  {len(seg)} points, {seg[0]} -> {seg[-1]}")