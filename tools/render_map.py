"""Render the Cycle I map into index.html.

Usage:
  python tools/render_map.py                 # thumbs + map block in index.html
  python tools/render_map.py --proof out.png # also write a focal-crop proof sheet

Inputs:  assets/map/africa-geometry.json (tools/build_map_geometry.py),
         tools/map-pieces.json (country + focal point per piece),
         tools/map-chips.json (island-state marker positions),
         assets/art/<slug>.webp and art/<slug>/index.html (for the title).
Outputs: assets/map/thumbs/<slug>.webp (crop baked to the country's box),
         assets/map/cards/<slug>.webp (small whole piece for the card),
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
    # small whole-piece image for the hover card and touch sheet
    card = img.copy()
    card.thumbnail((360, 360), Image.LANCZOS)
    (ROOT / "assets/map/cards").mkdir(parents=True, exist_ok=True)
    card.save(ROOT / "assets/map/cards" / f"{slug}.webp", "WEBP", quality=74, method=6)
    return out, win, img.size, zoom


def rings(d):
    return [[tuple(map(float, pt.split(","))) for pt in r.split("L")] for r in re.findall(r"M([^Z]*)Z", d)]


def f1(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def build_block(entries):
    # Fit the frame to the continent and island markers, not the source canvas,
    # so the map fills its width.
    xs = [v for c in GEOM["countries"].values() for v in (c["bbox"][0], c["bbox"][2])] + [x for x, _ in CHIPS.values()]
    ys = [v for c in GEOM["countries"].values() for v in (c["bbox"][1], c["bbox"][3])] + [y for _, y in CHIPS.values()]
    VX, VY = math.floor(min(xs)) - CHIP_R - 4, math.floor(min(ys)) - CHIP_R - 4
    W, H = math.ceil(max(xs)) + CHIP_R + 4 - VX, math.ceil(max(ys)) + CHIP_R + 4 - VY
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
            f'data-title="{html.escape(e["title"])}" data-img="/assets/map/cards/{e["slug"]}.webp?v={e["v"]}" '
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
        f'<svg class="m-svg" viewBox="{VX} {VY} {W} {H}" role="group" aria-labelledby="m-title m-desc">'
        f'<title id="m-title">Cycle I: Africa</title>'
        f'<desc id="m-desc">A map of Africa. Each country that holds a piece links to it.</desc>'
        f'<defs>{"".join(defs)}</defs>'
        f'<g class="m-ground" aria-hidden="true">{"".join(ground)}</g>'
        f'<g class="m-chips" aria-hidden="true">{"".join(chips)}</g>'
        f'<g class="m-pieces">{"".join(pieces)}</g>'
        f'<use class="m-hi" id="m-hi" href="" aria-hidden="true"/>'
        f'</svg>'
    )
    reel = []
    for e in sorted(entries, key=lambda e: e["title"].lower()):
        # Same long side for every piece, so portraits stand taller than
        # landscapes and each keeps its own proportions.
        iw, ih = e["img_size"]
        w, h = (240, round(240 * ih / iw)) if iw >= ih else (round(240 * iw / ih), 240)
        reel.append(
            f'<li style="--w:{w};--h:{h}"><a href="/art/{e["slug"]}/" data-country="{e["country"]}">'
            f'<img src="/assets/map/cards/{e["slug"]}.webp?v={e["v"]}" alt="" width="{w}" height="{h}" loading="lazy" decoding="async">'
            f'<span>{html.escape(e["title"])}</span></a></li>'
        )

    return f"""<!-- MAP:START (generated by tools/render_map.py; edit tools/map-pieces.json, not this block) -->
<style>
  .cycle-map {{ position: relative; max-width: 820px; margin: 8px auto 40px; }}
  @media (max-width: 600px) {{ .cycle-map {{ margin-left: -32px; margin-right: -32px; }} }}
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
  .m-card {{ position: absolute; z-index: 5; width: 180px; background: var(--bg); border: 1px solid var(--border); padding: 10px; color: var(--ink); text-decoration: none; }}
  .m-card[hidden] {{ display: none; }}
  .m-card.is-follow {{ pointer-events: none; }}
  .m-card img {{ display: block; width: 100%; height: auto; }}
  .m-card-title {{ display: block; margin: 8px 0 2px; font-size: 17px; line-height: 1.25; }}
  .m-card-go {{ font-family: "Archivo", system-ui, sans-serif; font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--accent); }}
  .m-card:hover .m-card-go, .m-card:focus-visible .m-card-go {{ text-decoration: underline; }}
  .m-card:focus-visible {{ outline: 2px solid var(--focus); outline-offset: 2px; }}
  .m-card.is-sheet {{ position: fixed; left: 16px; right: 16px; bottom: 16px; width: auto; display: flex; gap: 12px; align-items: center; padding: 12px; }}
  .m-card.is-sheet img {{ width: 72px; flex: none; }}
  .m-card.is-sheet .m-card-title {{ margin-top: 0; }}
  .m-card.is-sheet .m-card-go {{ display: inline-block; padding: 8px 0; }}
  .m-reel {{ margin-top: 28px; }}
  .m-reel-bar {{ display: flex; justify-content: flex-end; }}
  .m-reel-toggle {{ min-height: 44px; min-width: 44px; padding: 0 12px; background: none; border: 0; color: var(--ink-soft); font-family: "Archivo", system-ui, sans-serif; font-size: 11px; letter-spacing: .14em; text-transform: uppercase; cursor: pointer; }}
  .m-reel-toggle:hover {{ color: var(--ink); }}
  .m-reel-toggle:focus-visible {{ outline: 2px solid var(--focus); outline-offset: 2px; color: var(--accent); }}
  .m-reel-track {{ display: flex; overflow-x: auto; scrollbar-width: none; -webkit-overflow-scrolling: touch; -webkit-mask-image: linear-gradient(to right, transparent, #000 28px, #000 calc(100% - 28px), transparent); mask-image: linear-gradient(to right, transparent, #000 28px, #000 calc(100% - 28px), transparent); }}
  .m-reel-track::-webkit-scrollbar {{ display: none; }}
  .m-reel-list {{ display: flex; align-items: flex-start; gap: 28px; margin: 0; padding: 0 28px 0 0; list-style: none; flex: none; }}
  .m-reel-list a {{ display: block; text-decoration: none; color: var(--ink-soft); }}
  .m-reel-list img {{ display: block; width: calc(var(--w) * 1px); height: calc(var(--h) * 1px); margin-top: calc((240 - var(--h)) * 1px); }}
  .m-reel-list span {{ display: block; width: calc(var(--w) * 1px); margin-top: 8px; font-size: 15px; line-height: 1.3; font-style: italic; }}
  .m-reel-list a:hover span, .m-reel-list a:focus-visible span {{ color: var(--ink); }}
  .m-reel-list a:focus-visible {{ outline: 2px solid var(--focus); outline-offset: 3px; }}
  @media (max-width: 600px) {{ .m-reel-list {{ gap: 20px; padding-right: 20px; }} .m-reel-list img {{ width: calc(var(--w) * 0.7px); height: calc(var(--h) * 0.7px); margin-top: calc((240 - var(--h)) * 0.7px); }} .m-reel-list span {{ width: calc(var(--w) * 0.7px); font-size: 14px; }} }}
  @media (prefers-reduced-motion: reduce) {{ .m-piece image {{ transition: none; }} }}
</style>
<section class="cycle-map" id="cycle-map" aria-label="Cycle I map">
{svg}
<a class="m-card" id="m-card" href="#" hidden><img alt="" width="160" height="107"><span class="m-card-title"></span><span class="m-card-go">View piece &rarr;</span></a>
<div class="m-reel" id="m-reel">
<div class="m-reel-bar"><button class="m-reel-toggle" id="m-reel-toggle" type="button">Pause</button></div>
<div class="m-reel-track" id="m-reel-track"><ul class="m-reel-list" aria-label="Pieces">{"".join(reel)}</ul></div>
</div>
</section>
<script>
(function () {{
  var wrap = document.getElementById("cycle-map");
  if (!wrap) return;
  var svg = wrap.querySelector(".m-svg"), hi = document.getElementById("m-hi");
  var card = document.getElementById("m-card"), cardImg = card.querySelector("img");
  var cardTitle = card.querySelector(".m-card-title");
  var links = Array.prototype.slice.call(svg.querySelectorAll(".m-piece"));
  var current = null;

  function route() {{ wrap.hidden = /^#(write|piece-)/.test(window.location.hash); }}
  window.addEventListener("hashchange", route);
  route();

  function outline(code) {{ hi.setAttribute("href", code ? "#me-" + code : ""); }}
  function codeOf(a) {{ return a.querySelector(".m-edge").id.slice(3); }}

  // Three ways the card appears. Mouse: it follows the pointer, so it never
  // vanishes on the way to a click, and clicking the country opens the piece.
  // Keyboard: it sits beside the focused country. Touch: a bottom sheet.
  function show(a, mode, e) {{
    if (current && current !== a) current.classList.remove("is-on");
    current = a;
    a.classList.add("is-on");
    outline(codeOf(a));
    if (cardImg.getAttribute("src") !== a.getAttribute("data-img")) cardImg.src = a.getAttribute("data-img");
    cardTitle.textContent = a.getAttribute("data-title");
    card.href = a.getAttribute("href");
    card.setAttribute("aria-label", a.getAttribute("data-title") + ", view piece");
    card.classList.toggle("is-sheet", mode === "sheet");
    card.classList.toggle("is-follow", mode === "pointer");
    card.hidden = false;
    if (mode === "pointer") place(e);
    else if (mode === "focus") {{
      var box = svg.getBoundingClientRect(), host = wrap.getBoundingClientRect();
      var k = box.width / {W};
      var x = box.left - host.left + (+a.getAttribute("data-ax") - {VX}) * k;
      var y = box.top - host.top + (+a.getAttribute("data-ay") - {VY}) * k;
      var right = box.left - host.left + (+a.getAttribute("data-x1") - {VX}) * k + 14;
      var leftOf = box.left - host.left + (+a.getAttribute("data-x0") - {VX}) * k - card.offsetWidth - 14;
      var left = right + card.offsetWidth <= host.width - 4 ? right : (leftOf >= 4 ? leftOf : x + 18);
      card.style.left = Math.max(4, left) + "px";
      card.style.top = Math.max(0, y - card.offsetHeight / 2) + "px";
    }}
  }}
  function place(e) {{
    var host = wrap.getBoundingClientRect();
    var x = e.clientX - host.left + 18, y = e.clientY - host.top + 18;
    if (x + card.offsetWidth > host.width - 4) x = e.clientX - host.left - card.offsetWidth - 18;
    if (y + card.offsetHeight > host.height - 4) y = e.clientY - host.top - card.offsetHeight - 18;
    card.style.left = Math.max(4, x) + "px";
    card.style.top = Math.max(0, y) + "px";
  }}
  function hide() {{
    if (current) current.classList.remove("is-on");
    current = null;
    outline(null);
    card.hidden = true;
    card.classList.remove("is-follow", "is-sheet");
    svg.classList.remove("has-focus", "is-kbd");
  }}
  function sheetOpen() {{ return card.classList.contains("is-sheet") && !card.hidden; }}

  links.forEach(function (a) {{
    a.addEventListener("mouseenter", function (e) {{ if (!sheetOpen()) show(a, "pointer", e); }});
    a.addEventListener("mousemove", function (e) {{ if (current === a && card.classList.contains("is-follow")) place(e); }});
    a.addEventListener("mouseleave", function () {{ if (card.classList.contains("is-follow")) hide(); }});
    a.addEventListener("focus", function () {{
      if (!a.matches(":focus-visible")) return;
      svg.classList.add("has-focus", "is-kbd");
      show(a, "focus");
    }});
    a.addEventListener("blur", function () {{ if (!sheetOpen()) setTimeout(function () {{ if (document.activeElement !== card) hide(); }}, 0); }});
  }});
  card.addEventListener("blur", function () {{ if (!sheetOpen()) hide(); }});
  document.addEventListener("keydown", function (e) {{ if (e.key === "Escape" && !card.hidden) hide(); }});

  // Touch: there is no hover, so the first tap picks the nearest finished
  // country within about 24px of the finger and opens a bottom sheet. The
  // whole sheet is the link to the piece; tapping anywhere else closes it.
  var touched = false;
  svg.addEventListener("pointerdown", function (e) {{ touched = e.pointerType === "touch" || e.pointerType === "pen"; }});
  svg.addEventListener("click", function (e) {{
    if (!touched) return;
    touched = false;
    var hit = e.target.closest && e.target.closest(".m-piece");
    if (hit && hit === current && card.classList.contains("is-sheet") && !card.hidden) return;
    e.preventDefault();
    var box = svg.getBoundingClientRect(), k = box.width / {W};
    var best = null, bestD = 24;
    links.forEach(function (a) {{
      var dx = box.left + (+a.getAttribute("data-ax") - {VX}) * k - e.clientX;
      var dy = box.top + (+a.getAttribute("data-ay") - {VY}) * k - e.clientY;
      var d = Math.sqrt(dx * dx + dy * dy);
      if (d < bestD) {{ bestD = d; best = a; }}
    }});
    var pick = hit || best;
    if (pick) show(pick, "sheet"); else hide();
  }});
  document.addEventListener("click", function (e) {{
    if (card.classList.contains("is-sheet") && !card.hidden && !svg.contains(e.target) && !card.contains(e.target)) hide();
  }});

  // The slideshow: a slow, shuffled drift with a Pause/Play button.
  // Hover and focus pause it for a moment; the button's pause stays until
  // Play. When paused it is an ordinary list you can swipe or scroll.
  var track = document.getElementById("m-reel-track"), list = track.querySelector(".m-reel-list");
  var toggle = document.getElementById("m-reel-toggle");
  var items = Array.prototype.slice.call(list.children);
  for (var i = items.length - 1; i > 0; i--) {{
    var j = Math.floor(Math.random() * (i + 1)), t = items[i]; items[i] = items[j]; items[j] = t;
  }}
  items.forEach(function (li) {{ list.appendChild(li); }});
  var copy = list.cloneNode(true);
  copy.setAttribute("aria-hidden", "true");
  copy.removeAttribute("aria-label");
  copy.inert = true;
  Array.prototype.forEach.call(copy.querySelectorAll("a"), function (a) {{ a.tabIndex = -1; }});
  track.appendChild(copy);

  var SPEED = 28; // px per second, measured in time so fast screens don't speed it up
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  var saved = null;
  try {{ saved = localStorage.getItem("benkum-reel"); }} catch (e) {{}}
  var userPaused = saved ? saved === "paused" : reduce.matches;
  var held = 0, visible = true, last = null, pos = 0;

  function label() {{ toggle.textContent = userPaused ? "Play" : "Pause"; }}
  function running() {{ return !userPaused && !held && visible && !document.hidden; }}
  function step(ts) {{
    if (last !== null && running()) {{
      var loop = list.offsetWidth;
      pos = (pos + SPEED * (ts - last) / 1000) % loop;
      track.scrollLeft = pos;
    }} else {{
      pos = track.scrollLeft % (list.offsetWidth || 1);
    }}
    last = ts;
    requestAnimationFrame(step);
  }}
  toggle.addEventListener("click", function () {{
    userPaused = !userPaused;
    try {{ localStorage.setItem("benkum-reel", userPaused ? "paused" : "playing"); }} catch (e) {{}}
    label();
  }});
  reduce.addEventListener && reduce.addEventListener("change", function () {{ if (reduce.matches) {{ userPaused = true; label(); }} }});
  [track].forEach(function (el) {{
    el.addEventListener("mouseenter", function () {{ held++; }});
    el.addEventListener("mouseleave", function () {{ held = Math.max(0, held - 1); }});
    el.addEventListener("focusin", function () {{ held++; }});
    el.addEventListener("focusout", function () {{ held = Math.max(0, held - 1); }});
    el.addEventListener("touchstart", function () {{ held++; }}, {{ passive: true }});
    el.addEventListener("touchend", function () {{ setTimeout(function () {{ held = Math.max(0, held - 1); }}, 1500); }});
  }});
  if ("IntersectionObserver" in window) {{
    new IntersectionObserver(function (es) {{ visible = es[0].isIntersecting; }}).observe(track);
  }}
  // Hovering or focusing a piece in the slideshow outlines its country.
  list.addEventListener("mouseover", function (e) {{ var a = e.target.closest("a"); if (a && !current) outline(a.getAttribute("data-country")); }});
  list.addEventListener("mouseout", function () {{ if (!current) outline(null); }});
  list.addEventListener("focusin", function (e) {{ var a = e.target.closest("a"); if (a) outline(a.getAttribute("data-country")); }});
  list.addEventListener("focusout", function () {{ if (!current) outline(null); }});
  label();
  requestAnimationFrame(step);
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
