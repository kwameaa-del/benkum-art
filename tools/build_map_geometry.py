"""Build the Cycle I Africa geometry once from Natural Earth (via world-atlas).

Usage:
  python tools/build_map_geometry.py path/to/countries-50m.json

Source: world-atlas@2.0.2 countries-50m.json (Natural Earth 1:50m, public
domain; world-atlas is ISC-licensed, see assets/map/NOTICE). The 1:110m file
is missing five island states, so always use 1:50m.

Writes assets/map/africa-geometry.json: SVG path data (pixels, 800 wide) for
the 54 UN member states plus Western Sahara, projected with an equal-area
Lambert azimuthal projection centred on Africa. Shared borders are simplified
once per arc, so neighbouring countries never gap or overlap.
"""
import json, sys, pathlib
from pyproj import Transformer
from shapely.geometry import LineString, Polygon, MultiPolygon
from shapely.ops import polylabel, unary_union

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "map" / "africa-geometry.json"
WIDTH = 800
TOLERANCE_M = 6500      # Douglas-Peucker per shared arc, in metres
MIN_RING_PX2 = 0.6      # drop specks smaller than this (island states keep all rings)

# ISO 3166 numeric -> (alpha-2, name read by screen readers)
COUNTRIES = {
    "012": ("DZ", "Algeria"), "024": ("AO", "Angola"), "204": ("BJ", "Benin"),
    "072": ("BW", "Botswana"), "854": ("BF", "Burkina Faso"), "108": ("BI", "Burundi"),
    "132": ("CV", "Cabo Verde"), "120": ("CM", "Cameroon"), "140": ("CF", "Central African Republic"),
    "148": ("TD", "Chad"), "174": ("KM", "Comoros"), "178": ("CG", "Republic of the Congo"),
    "180": ("CD", "Democratic Republic of the Congo"), "384": ("CI", "Côte d’Ivoire"),
    "262": ("DJ", "Djibouti"), "818": ("EG", "Egypt"), "226": ("GQ", "Equatorial Guinea"),
    "232": ("ER", "Eritrea"), "748": ("SZ", "Eswatini"), "231": ("ET", "Ethiopia"),
    "266": ("GA", "Gabon"), "270": ("GM", "The Gambia"), "288": ("GH", "Ghana"),
    "324": ("GN", "Guinea"), "624": ("GW", "Guinea-Bissau"), "404": ("KE", "Kenya"),
    "426": ("LS", "Lesotho"), "430": ("LR", "Liberia"), "434": ("LY", "Libya"),
    "450": ("MG", "Madagascar"), "454": ("MW", "Malawi"), "466": ("ML", "Mali"),
    "478": ("MR", "Mauritania"), "480": ("MU", "Mauritius"), "504": ("MA", "Morocco"),
    "508": ("MZ", "Mozambique"), "516": ("NA", "Namibia"), "562": ("NE", "Niger"),
    "566": ("NG", "Nigeria"), "646": ("RW", "Rwanda"), "678": ("ST", "São Tomé and Príncipe"),
    "686": ("SN", "Senegal"), "690": ("SC", "Seychelles"), "694": ("SL", "Sierra Leone"),
    "706": ("SO", "Somalia"), "710": ("ZA", "South Africa"), "728": ("SS", "South Sudan"),
    "729": ("SD", "Sudan"), "834": ("TZ", "Tanzania"), "768": ("TG", "Togo"),
    "788": ("TN", "Tunisia"), "800": ("UG", "Uganda"), "894": ("ZM", "Zambia"),
    "716": ("ZW", "Zimbabwe"),
}
WESTERN_SAHARA = "732"
ISLAND_STATES = {"CV", "ST", "KM", "MU", "SC"}
assert len(COUNTRIES) == 54


def decode_arcs(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx; y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    return arcs


def main(src):
    topo = json.loads(pathlib.Path(src).read_text(encoding="utf-8"))
    geoms = topo["objects"]["countries"]["geometries"]
    arcs = decode_arcs(topo)

    # Pick features: the 54, Western Sahara, and Somaliland (folded into Somalia).
    wanted = {}
    for g in geoms:
        gid = g.get("id")
        name = (g.get("properties") or {}).get("name", "")
        if name == "Somaliland":
            gid = "706"
        if gid in COUNTRIES:
            code = COUNTRIES[gid][0]
        elif gid == WESTERN_SAHARA:
            code = "EH"
        else:
            continue
        wanted.setdefault(code, []).append(g)
    missing = {c for c, _ in COUNTRIES.values()} - set(wanted)
    if missing:
        raise SystemExit(f"missing countries: {sorted(missing)}")

    proj = Transformer.from_crs("EPSG:4326", "+proj=laea +lat_0=2 +lon_0=17 +datum=WGS84 +units=m", always_xy=True)

    # Project + simplify each used arc once, so shared borders stay identical.
    used = set()
    for gs in wanted.values():
        for g in gs:
            polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
            for poly in polys:
                for ring in poly:
                    for a in ring:
                        used.add(a if a >= 0 else ~a)
    simple = {}
    for i in used:
        xs, ys = proj.transform([p[0] for p in arcs[i]], [p[1] for p in arcs[i]])
        line = list(zip(xs, ys))
        s = LineString(line).simplify(TOLERANCE_M, preserve_topology=False)
        coords = list(s.coords)
        if len(coords) < 4 and line[0] == line[-1]:      # closed island ring collapsed: keep a lighter touch
            coords = list(LineString(line).simplify(TOLERANCE_M / 8).coords)
        simple[i] = coords

    def ring_coords(ring):
        pts = []
        for a in ring:
            seg = simple[a] if a >= 0 else simple[~a][::-1]
            pts.extend(seg if not pts else seg[1:])
        return pts

    # South Africa's Prince Edward Islands (~47°S) would stretch the canvas far
    # below the continent; leave out anything south of 40°S.
    y_cut = proj.transform(20, -40)[1]

    shapes = {}
    for code, gs in wanted.items():
        parts = []
        for g in gs:
            polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
            for poly in polys:
                rings = [ring_coords(r) for r in poly]
                if len(rings[0]) < 4:
                    continue
                part = Polygon(rings[0], [r for r in rings[1:] if len(r) >= 4])
                if part.centroid.y < y_cut:
                    continue
                parts.append(part)
        shapes[code] = parts

    # Fit to WIDTH px (y down).
    allb = unary_union([p for ps in shapes.values() for p in ps]).bounds
    minx, miny, maxx, maxy = allb
    pad = 0.06 * (maxx - minx)          # room for island chips offshore
    minx -= pad; maxx += pad; miny -= pad * 0.4; maxy += pad * 0.4
    k = WIDTH / (maxx - minx)
    height = round((maxy - miny) * k)
    px = lambda x, y: ((x - minx) * k, (maxy - y) * k)

    out = {"width": WIDTH, "height": height, "countries": {}}
    for code, parts in shapes.items():
        d = []
        kept = []
        for poly in parts:
            area_px = poly.area * k * k
            if area_px < MIN_RING_PX2 and code not in ISLAND_STATES and len(parts) > 1:
                continue
            kept.append(poly)
            for ring in [poly.exterior, *poly.interiors]:
                pts = [px(x, y) for x, y in ring.coords[:-1]]
                d.append("M" + "L".join(f"{x:.1f},{y:.1f}".replace(".0,", ",").replace(".0L", "L") for x, y in pts) + "Z")
        biggest = max(kept, key=lambda p: p.area)
        ax, ay = px(*polylabel(biggest, tolerance=1000).coords[0])
        bx0, by0 = px(*MultiPolygon(kept).bounds[:2])
        bx1, by1 = px(*MultiPolygon(kept).bounds[2:])
        name = "Western Sahara" if code == "EH" else next(n for c, n in COUNTRIES.values() if c == code)
        out["countries"][code] = {
            "name": name,
            "d": "".join(d),
            "anchor": [round(ax, 1), round(ay, 1)],
            "bbox": [round(bx0, 1), round(by1, 1), round(bx1, 1), round(by0, 1)],
            "island": code in ISLAND_STATES,
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    total = sum(len(c["d"]) for c in out["countries"].values())
    print(f"{len(out['countries'])} shapes, {WIDTH}x{height}px, path data {total/1024:.1f} KB -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
