"""Render the Cycle I map into index.html.

Usage:
  python tools/render_map.py                 # thumbs + map block in index.html
  python tools/render_map.py --proof out.png # also write a focal-crop proof sheet

Inputs:  assets/map/africa-geometry.json (tools/build_map_geometry.py),
         tools/map-pieces.json (country + focal point per piece),
         tools/map-chips.json (island-state marker positions),
         assets/art/<slug>.webp and art/<slug>/index.html (for the title).
Outputs: assets/map/thumbs/<slug>.webp (crop baked to the country's box),
         the block between <!-- MAP:START --> and <!-- MAP:END --> in index.html.

The map shows no numbers, dates or order: completed countries are listed
alphabetically by country name (that is the tab order), never by release.
"""
import hashlib, html, json, math, re, sys, pathlib
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
GEOM = json.loads((ROOT / "assets/map/africa-geometry.json").read_text(encoding="utf-8"))
PIECES = {k: v for k, v in json.loads((ROOT / "tools/map-pieces.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
CHIPS = {k: v for k, v in json.loads((ROOT / "tools/map-chips.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
THUMBS = ROOT / "assets/map/thumbs"
INDEX = ROOT / "index.html"
GROUND = "#2A2621"
DENSITY = 2          # thumb pixels per map pixel
CHIP_R = 7
TAP_MIN = 24         # px: smallest comfortable target on an 800 px map


def title_of(slug):
    page = (ROOT / "art" / slug / "index.html").read_text(encoding="utf-8")
    t = re.search(r"<title>([^<]*)</title>", page).group(1)
    return html.unescape(t.split(" — ")[0]).strip()


def validate():
    seen = {}
    for slug, p in PIECES.items():
        c = p["country"]
        if c not in GEOM["countries"] or c == "EH":
            raise SystemExit(f"{slug}: unknown country {c}")
        if c in seen:
            raise SystemExit(f"{slug}: {c} already used by {seen[c]}")
        seen[c] = slug
        fx, fy = p["focus"]
        if not (0 <= fx <= 1 and 0 <= fy <= 1):
            raise SystemExit(f"{slug}: focus must be fractions 0-1")
        for f in (ROOT / "assets/art" / f"{slug}.webp", ROOT / "art" / slug / "index.html"):
            if not f.exists():
                raise SystemExit(f"{slug}: missing {f}")


def crop_window(img_w, img_h, box_w, box_h, focus, zoom):
    """Largest window with the box's aspect, divided by zoom, centred on focus, kept inside the image."""
    a = box_w / box_h
    ww, wh = (img_h * a, img_h) if img_w / img_h > a else (img_w, img_w / a)
    ww, wh = ww / zoom, wh / zoom
    cx = min(max(focus[0] * img_w, ww / 2), img_w - ww / 2)
    cy = min(max(focus[1] * img_h, wh / 2), img_h - wh / 2)
    return (cx - ww / 2, cy - wh / 2, cx + ww / 2, cy + wh / 2)


def auto_zoom(box_w, box_h):
    # Small countries show a closer crop, so the figure's colour carries.
    return max(1.0, min(2.2, 60 / max(box_w, box_h)))


def make_thumb(slug, p, box):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    img = Image.open(ROOT / "assets/art" / f"{slug}.webp").convert("RGB")
    zoom = p.get("zoom") or auto_zoom(bw, bh)
    win = crop_window(*img.size, bw, bh, p["focus"], zoom)
    scale = max(DENSITY, 48 / max(bw, bh))
    size = (max(1, round(bw * scale)), max(1, round(bh * scale)))
    thumb = img.crop(tuple(round(v) for v in win)).resize(size, Image.LANCZOS)
    THUMBS.mkdir(parents=True, exist_ok=True)
    out = THUMBS / f"{slug}.webp"
    thumb.save(out, "WEBP", quality=72, method=6)
    return out, win, img.size, zoom


def rings(d):
    return [[tuple(map(float, pt.split(","))) for pt in r.split("L")] for r in re.findall(r"M([^Z]*)Z", d)]


def f1(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def build_block(entries):
    W, H = GEOM["width"], GEOM["height"]
    filled = {e["country"] for e in entries}
    defs, ground, pieces, chips = [], [], [], []

    for code, c in GEOM["countries"].items():
        if code not in filled:
            ground.append(f'<path d="{c["d"]}"/>')

    for e in sorted(entries, key=lambda e: GEOM["countries"][e["country"]]["name"]):
        code, c = e["country"], GEOM["countries"][e["country"]]
        x0, y0, x1, y1 = c["bbox"]
        label = f'{c["name"]}: {e["title"]}'
        defs.append(f'<clipPath id="mc-{code}"><path d="{c["d"]}"/></clipPath>')
        tap = ""
        if max(x1 - x0, y1 - y0) < TAP_MIN:
            ax, ay = c["anchor"]
            tap = f'<circle class="m-tap" cx="{f1(ax)}" cy="{f1(ay)}" r="{TAP_MIN // 2}"/>'
        pieces.append(
            f'<a class="m-piece" href="/art/{e["slug"]}/" aria-label="{html.escape(label)}" '
            f'data-title="{html.escape(e["title"])}" data-img="/assets/art/{e["slug"]}.webp" '
            f'data-ax="{f1(c["anchor"][0])}" data-ay="{f1(c["anchor"][1])}" data-x0="{f1(x0)}" data-x1="{f1(x1)}">'
            f'<image href="/assets/map/thumbs/{e["slug"]}.webp?v={e["v"]}" x="{f1(x0)}" y="{f1(y0)}" '
            f'width="{f1(x1 - x0)}" height="{f1(y1 - y0)}" preserveAspectRatio="none" '
            f'clip-path="url(#mc-{code})" decoding="async"/>'
            f'<path class="m-edge" id="me-{code}" d="{c["d"]}"/>{tap}</a>'
        )

    for code, (cx, cy) in CHIPS.items():
        if code in filled:
            continue  # a finished island state would get a linked chip; none yet
        ax, ay = GEOM["countries"][code]["anchor"]
        lead = ""
        if math.hypot(cx - ax, cy - ay) > CHIP_R + 2:
            k = CHIP_R / math.hypot(cx - ax, cy - ay)
            lead = f'<line x1="{f1(cx + (ax - cx) * k)}" y1="{f1(cy + (ay - cy) * k)}" x2="{f1(ax)}" y2="{f1(ay)}"/>'
        chips.append(f'{lead}<circle cx="{cx}" cy="{cy}" r="{CHIP_R}"/>')

    svg = (
        f'<svg class="m-svg" viewBox="0 0 {W} {H}" role="group" aria-labelledby="m-title m-desc">'
        f'<title id="m-title">Cycle I: Africa</title>'
        f'<desc id="m-desc">A map of Africa. Each country that holds a piece links to it.</desc>'
        f'<defs>{"".join(defs)}</defs>'
        f'<g class="m-ground" aria-hidden="true">{"".join(ground)}</g>'
        f'<g class="m-chips" aria-hidden="true">{"".join(chips)}</g>'
        f'<g class="m-pieces">{"".join(pieces)}</g>'
        f'<use class="m-hi" id="m-hi" href="" aria-hidden="true"/>'
        f'</svg>'
    )
    return f"""<!-- MAP:START (generated by tools/render_map.py; edit tools/map-pieces.json, not this block) -->
<style>
  .cycle-map {{ position: relative; max-width: 760px; margin: 8px auto 40px; }}
  @media (max-width: 600px) {{ .cycle-map {{ margin-left: -16px; margin-right: -16px; }} }}
  .cycle-map[hidden] {{ display: none; }}
  .m-svg {{ display: block; width: 100%; height: auto; overflow: visible; }}
  .m-ground path, .m-chips circle {{ fill: {GROUND}; stroke: var(--ink-soft); stroke-width: 0.6px; vector-effect: non-scaling-stroke; stroke-linejoin: round; }}
  .m-chips line {{ stroke: var(--ink-soft); stroke-width: 0.6px; vector-effect: non-scaling-stroke; }}
  .m-edge {{ fill: none; stroke: var(--ink-soft); stroke-width: 0.6px; vector-effect: non-scaling-stroke; stroke-linejoin: round; }}
  .m-tap {{ fill: transparent; }}
  .m-piece {{ outline: none; cursor: pointer; }}
  .m-piece image {{ transition: opacity .2s; }}
  .m-svg:hover .m-piece image, .m-svg.has-focus .m-piece image {{ opacity: .82; }}
  .m-svg .m-piece.is-on image {{ opacity: 1; }}
  .m-hi {{ fill: none; stroke: var(--focus); stroke-width: 2px; vector-effect: non-scaling-stroke; stroke-linejoin: round; pointer-events: none; }}
  .m-svg.is-kbd .m-hi {{ stroke-width: 3px; }}
  .m-card {{ position: absolute; z-index: 5; width: 180px; background: var(--bg); border: 1px solid var(--border); padding: 10px; pointer-events: none; }}
  .m-card[hidden] {{ display: none; }}
  .m-card img {{ display: block; width: 100%; height: auto; }}
  .m-card-title {{ margin: 8px 0 2px; font-size: 17px; line-height: 1.25; color: var(--ink); }}
  .m-card-link {{ font-family: "Archivo", system-ui, sans-serif; font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--accent); text-decoration: none; }}
  .m-card.is-sheet {{ position: fixed; left: 16px; right: 16px; bottom: 16px; width: auto; display: flex; gap: 12px; align-items: center; pointer-events: auto; padding: 12px; }}
  .m-card.is-sheet img {{ width: 72px; flex: none; }}
  .m-card.is-sheet .m-card-link {{ display: inline-block; padding: 12px 0; }}
  @media (prefers-reduced-motion: reduce) {{ .m-piece image {{ transition: none; }} }}
</style>
<section class="cycle-map" id="cycle-map" aria-label="Cycle I map">
{svg}
<div class="m-card" id="m-card" hidden><img alt="" width="160" height="107"><p class="m-card-title"></p><a class="m-card-link" href="#">View piece &rarr;</a></div>
</section>
<script>
(function () {{
  var wrap = document.getElementById("cycle-map");
  if (!wrap) return;
  var svg = wrap.querySelector(".m-svg"), hi = document.getElementById("m-hi");
  var card = document.getElementById("m-card"), cardImg = card.querySelector("img");
  var cardTitle = card.querySelector(".m-card-title"), cardLink = card.querySelector(".m-card-link");
  var links = Array.prototype.slice.call(svg.querySelectorAll(".m-piece"));
  var current = null;

  function route() {{ wrap.hidden = /^#(write|piece-)/.test(window.location.hash); }}
  window.addEventListener("hashchange", route);
  route();

  function show(a, asSheet) {{
    if (current && current !== a) current.classList.remove("is-on");
    current = a;
    a.classList.add("is-on");
    hi.setAttribute("href", "#" + a.querySelector(".m-edge").id);
    cardImg.src = a.getAttribute("data-img");
    cardTitle.textContent = a.getAttribute("data-title");
    cardLink.href = a.getAttribute("href");
    card.classList.toggle("is-sheet", !!asSheet);
    card.hidden = false;
    if (!asSheet) {{
      var box = svg.getBoundingClientRect(), host = wrap.getBoundingClientRect();
      var k = box.width / {W};
      var x = box.left - host.left + (+a.getAttribute("data-ax")) * k;
      var y = box.top - host.top + (+a.getAttribute("data-ay")) * k;
      var right = box.left - host.left + (+a.getAttribute("data-x1")) * k + 14;
      var leftOf = box.left - host.left + (+a.getAttribute("data-x0")) * k - card.offsetWidth - 14;
      var left = right + card.offsetWidth <= host.width - 4 ? right : (leftOf >= 4 ? leftOf : x + 18);
      card.style.left = Math.max(4, left) + "px";
      card.style.top = Math.max(0, y - card.offsetHeight / 2) + "px";
    }}
  }}
  function hide() {{
    if (current) current.classList.remove("is-on");
    current = null;
    hi.setAttribute("href", "");
    card.hidden = true;
    svg.classList.remove("has-focus", "is-kbd");
  }}

  links.forEach(function (a) {{
    a.addEventListener("mouseenter", function () {{ if (!card.classList.contains("is-sheet") || card.hidden) show(a, false); }});
    a.addEventListener("mouseleave", function () {{ if (!card.classList.contains("is-sheet")) hide(); }});
    a.addEventListener("focus", function () {{ svg.classList.add("has-focus"); if (a.matches(":focus-visible")) svg.classList.add("is-kbd"); show(a, false); }});
    a.addEventListener("blur", function () {{ if (!card.classList.contains("is-sheet")) hide(); }});
  }});
  document.addEventListener("keydown", function (e) {{ if (e.key === "Escape" && !card.hidden) hide(); }});

  // Touch: the first tap picks the nearest finished country within about
  // 24px of the finger and opens a bottom sheet; the sheet's link opens it.
  var touched = false;
  svg.addEventListener("pointerdown", function (e) {{ touched = e.pointerType === "touch" || e.pointerType === "pen"; }});
  svg.addEventListener("click", function (e) {{
    if (!touched) return;
    e.preventDefault();
    var box = svg.getBoundingClientRect(), k = box.width / {W};
    var best = null, bestD = 24;
    links.forEach(function (a) {{
      var dx = box.left + (+a.getAttribute("data-ax")) * k - e.clientX;
      var dy = box.top + (+a.getAttribute("data-ay")) * k - e.clientY;
      var d = Math.sqrt(dx * dx + dy * dy);
      if (d < bestD) {{ bestD = d; best = a; }}
    }});
    var hit = e.target.closest && e.target.closest(".m-piece");
    var pick = hit || best;
    if (pick) show(pick, true); else hide();
  }});
  document.addEventListener("click", function (e) {{
    if (card.classList.contains("is-sheet") && !card.hidden && !wrap.contains(e.target)) hide();
  }});
}})();
</script>
<!-- MAP:END -->"""


def proof_sheet(entries, out):
    cols, cw, ch = 3, 520, 300
    rows = math.ceil(len(entries) / cols)
    sheet = Image.new("RGB", (cols * cw, rows * ch), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for i, e in enumerate(sorted(entries, key=lambda e: e["slug"])):
        ox, oy = (i % cols) * cw + 12, (i // cols) * ch + 28
        d.text((ox, oy - 20), f'{e["title"]}  ->  {GEOM["countries"][e["country"]]["name"]}  focus {e["focus"]}  zoom {e["zoom"]:.2f}', fill=(237, 234, 226))
        img = Image.open(ROOT / "assets/art" / f'{e["slug"]}.webp').convert("RGB")
        img.thumbnail((300, 250))
        s = img.size[0] / e["img_size"][0]
        sheet.paste(img, (ox, oy))
        x0, y0, x1, y1 = (v * s for v in e["win"])
        d.rectangle((ox + x0, oy + y0, ox + x1, oy + y1), outline=(234, 174, 69), width=2)
        fx, fy = ox + e["focus"][0] * img.size[0], oy + e["focus"][1] * img.size[1]
        d.line((fx - 6, fy, fx + 6, fy), fill=(234, 174, 69), width=2); d.line((fx, fy - 6, fx, fy + 6), fill=(234, 174, 69), width=2)
        # the country as it will render, enlarged
        c = GEOM["countries"][e["country"]]
        bx0, by0, bx1, by1 = c["bbox"]
        k = min(180 / (bx1 - bx0), 230 / (by1 - by0))
        w, h = max(1, round((bx1 - bx0) * k)), max(1, round((by1 - by0) * k))
        mask = Image.new("L", (w, h), 0)
        for r in rings(c["d"]):
            layer = Image.new("L", (w, h), 0)
            ImageDraw.Draw(layer).polygon([((x - bx0) * k, (y - by0) * k) for x, y in r], fill=255)
            mask = Image.frombytes("L", (w, h), bytes(a ^ b for a, b in zip(mask.tobytes(), layer.tobytes())))
        thumb = Image.open(THUMBS / f'{e["slug"]}.webp').convert("RGB").resize((w, h), Image.LANCZOS)
        tile = Image.new("RGB", (w, h), (20, 20, 20)); tile.paste(thumb, (0, 0), mask)
        sheet.paste(tile, (ox + 315, oy))
    sheet.save(out)


def main():
    validate()
    entries = []
    for slug, p in PIECES.items():
        c = GEOM["countries"][p["country"]]
        out, win, size, zoom = make_thumb(slug, p, c["bbox"])
        v = hashlib.md5(out.read_bytes()).hexdigest()[:8]
        entries.append({"slug": slug, "title": title_of(slug), "v": v, "win": win, "img_size": size, "zoom": zoom, **p})

    block = build_block(entries)
    text = INDEX.read_text(encoding="utf-8")
    if "<!-- MAP:START" in text:
        text = re.sub(r"<!-- MAP:START.*?<!-- MAP:END -->", lambda m: block, text, flags=re.S)
    else:
        text = text.replace('  <main id="view-root">', block + '\n  <main id="view-root">', 1)
    INDEX.write_text(text, encoding="utf-8", newline="\n")
    kb = sum((THUMBS / f'{e["slug"]}.webp').stat().st_size for e in entries) / 1024
    print(f"{len(entries)} pieces on the map; thumbs {kb:.0f} KB; block {len(block)/1024:.1f} KB")

    if "--proof" in sys.argv:
        proof_sheet(entries, sys.argv[sys.argv.index("--proof") + 1])


if __name__ == "__main__":
    main()
