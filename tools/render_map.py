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
  .cycle-map {{ position: relative; max-width: 820px; margin: 4px auto 0; }}
  /* Home fits on one screen: the footer sits close under the slideshow. */
  .cycle-map:not([hidden]) ~ footer.site-foot {{ margin-top: 14px; }}
  @media (max-width: 600px) {{ .cycle-map {{ margin-left: -32px; margin-right: -32px; }} }}
  .cycle-map[hidden] {{ display: none; }}
  /* Width is set by script so map, slideshow and footer fit one screen. */
  .m-svg {{ display: block; width: 100%; height: auto; margin: 0 auto; overflow: visible; }}
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
  .m-reel {{ --rs: .5; margin-top: 12px; display: flex; align-items: center; gap: 4px; }}
  .m-reel-toggle {{ order: 2; flex: none; min-height: 44px; min-width: 44px; padding: 0 12px; background: none; border: 0; color: var(--ink-soft); font-family: "Archivo", system-ui, sans-serif; font-size: 11px; letter-spacing: .14em; text-transform: uppercase; cursor: pointer; }}
  .m-reel-toggle:hover {{ color: var(--ink); }}
  .m-reel-toggle:focus-visible {{ outline: 2px solid var(--focus); outline-offset: 2px; color: var(--accent); }}
  .m-reel-track {{ display: flex; flex: 1; min-width: 0; overflow-x: auto; scrollbar-width: none; -webkit-overflow-scrolling: touch; -webkit-mask-image: linear-gradient(to right, transparent, #000 28px, #000 calc(100% - 28px), transparent); mask-image: linear-gradient(to right, transparent, #000 28px, #000 calc(100% - 28px), transparent); }}
  .m-reel-track::-webkit-scrollbar {{ display: none; }}
  .m-reel-list {{ display: flex; align-items: flex-start; gap: 22px; margin: 0; padding: 0 22px 0 0; list-style: none; flex: none; }}
  .m-reel-list a {{ display: block; text-decoration: none; color: var(--ink-soft); min-width: 96px; }}
  .m-reel-list img {{ display: block; margin: calc((240 - var(--h)) * var(--rs) * 1px) auto 0; width: calc(var(--w) * var(--rs) * 1px); height: calc(var(--h) * var(--rs) * 1px); }}
  .m-reel-list span {{ display: block; max-width: max(96px, calc(var(--w) * var(--rs) * 1px)); margin: 6px auto 0; font-size: 13px; line-height: 1.25; font-style: italic; text-align: center; }}
  .m-reel-list a:hover span, .m-reel-list a:focus-visible span {{ color: var(--ink); }}
  .m-reel-list a:focus-visible {{ outline: 2px solid var(--focus); outline-offset: 3px; }}
  @media (max-width: 600px) {{ .m-reel {{ --rs: .42; }} .m-reel-list {{ gap: 16px; padding-right: 16px; }} }}
  @media (prefers-reduced-motion: reduce) {{ .m-piece image {{ transition: none; }} }}
</style>
<section class="cycle-map" id="cycle-map" aria-label="Cycle I map">
{svg}
<a class="m-card" id="m-card" href="#" hidden><img alt="" width="160" height="107"><span class="m-card-title"></span><span class="m-card-go">View piece &rarr;</span></a>
<div class="m-reel" id="m-reel">
<button class="m-reel-toggle" id="m-reel-toggle" type="button">Pause</button>
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

  // Fit the homepage to one screen: the map takes whatever height is left
  // after the header, slideshow and footer (never narrower than 240px).
  function fit() {{
    if (wrap.hidden) return;
    svg.style.width = "";
    var rest = document.documentElement.scrollHeight - svg.getBoundingClientRect().height;
    var avail = window.innerHeight - rest;
    var w = Math.max(240, Math.min(wrap.clientWidth, avail * {W} / {H}));
    svg.style.width = Math.floor(w) + "px";
  }}
  function route() {{ wrap.hidden = /^#(write|piece-)/.test(window.location.hash); fit(); }}
  window.addEventListener("hashchange", route);
  window.addEventListener("resize", fit);
  document.addEventListener("DOMContentLoaded", fit);
  window.addEventListener("load", fit);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);
  route();

  function outline(code) {{ hi.setAttribute("href", code ? "#me-" + code : ""); }}
  function codeOf(a) {{ return a.querySelector(".m-edge").id.slice(3); }}

  // Three ways the card appears.
  // Mouse: the card trails just beside the pointer while it moves; once the
  // pointer rests on a country for a moment the card stays put and can be
  // clicked. Brushing past a neighbouring country on the short way to the
  // card does not switch it. Clicking the country itself also opens the piece.
  // Keyboard: it sits beside the focused country. Touch: no card; a tap
  // opens the piece directly (see below).
  var pinned = false, pinAt = null, lastMove = null, idleT = null, hideT = null, switchT = null;
  function clearTimers() {{ clearTimeout(idleT); clearTimeout(hideT); clearTimeout(switchT); }}
  function show(a, mode, e) {{
    clearTimers();
    if (current && current !== a) current.classList.remove("is-on");
    current = a;
    a.classList.add("is-on");
    outline(codeOf(a));
    if (cardImg.getAttribute("src") !== a.getAttribute("data-img")) cardImg.src = a.getAttribute("data-img");
    cardTitle.textContent = a.getAttribute("data-title");
    card.href = a.getAttribute("href");
    card.setAttribute("aria-label", a.getAttribute("data-title") + ", view piece");
    card.classList.toggle("is-follow", mode === "pointer");
    pinned = false;
    card.hidden = false;
    if (mode === "pointer") {{ place(e); restSoon(e); }}
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
    var x = e.clientX - host.left + 12, y = e.clientY - host.top + 12;
    if (x + card.offsetWidth > host.width - 4) x = e.clientX - host.left - card.offsetWidth - 12;
    if (y + card.offsetHeight > host.height - 4) y = e.clientY - host.top - card.offsetHeight - 12;
    card.style.left = Math.max(4, x) + "px";
    card.style.top = Math.max(0, y) + "px";
  }}
  // After the pointer rests briefly, the card stops trailing and takes clicks.
  function restSoon(e) {{
    clearTimeout(idleT);
    idleT = setTimeout(function () {{
      pinned = true; pinAt = {{ x: e.clientX, y: e.clientY }};
      card.classList.remove("is-follow");
    }}, 220);
  }}
  function hide() {{
    clearTimers();
    if (current) current.classList.remove("is-on");
    current = null;
    pinned = false;
    outline(null);
    card.hidden = true;
    card.classList.remove("is-follow");
    svg.classList.remove("has-focus", "is-kbd");
  }}
  function hideSoon() {{ clearTimeout(hideT); hideT = setTimeout(hide, 350); }}
  // Phones send emulated mouse events just before a tap; ignore them so the
  // hover card never flashes up on the way to the piece.
  var touchAt = 0;
  function fromTouch() {{ return Date.now() - touchAt < 800; }}

  links.forEach(function (a) {{
    a.addEventListener("mouseenter", function (e) {{
      if (fromTouch()) return;
      clearTimeout(hideT);
      lastMove = e;
      if (current === a) return;
      if (pinned && !card.hidden) {{
        // Probably passing through on the way to the card: wait before switching.
        clearTimeout(switchT);
        switchT = setTimeout(function () {{ show(a, "pointer", lastMove); }}, 300);
      }} else show(a, "pointer", e);
    }});
    a.addEventListener("mousemove", function (e) {{
      lastMove = e;
      if (current !== a || fromTouch()) return;
      if (pinned && pinAt && Math.hypot(e.clientX - pinAt.x, e.clientY - pinAt.y) > 90) {{
        // Moved well away within the same country: let the card follow again.
        pinned = false; card.classList.add("is-follow");
      }}
      if (!pinned) {{ place(e); restSoon(e); }}
    }});
    a.addEventListener("mouseleave", function () {{
      // Leaving cancels any pending switch to this country; the card or empty space comes next.
      clearTimeout(idleT); clearTimeout(switchT);
      if (!card.hidden && !card.matches(":focus")) hideSoon();
    }});
    a.addEventListener("focus", function () {{
      if (!a.matches(":focus-visible")) return;
      svg.classList.add("has-focus", "is-kbd");
      show(a, "focus");
    }});
    a.addEventListener("blur", function () {{
      setTimeout(function () {{
        // Keep it when focus moved to the card or to another country (which shows its own).
        var to = document.activeElement;
        if (to !== card && !(to && to.classList && to.classList.contains("m-piece")) && !card.matches(":hover")) hide();
      }}, 0);
    }});
  }});
  card.addEventListener("mouseenter", function () {{ clearTimers(); }});
  card.addEventListener("mouseleave", function () {{ hideSoon(); }});
  card.addEventListener("blur", function () {{ hide(); }});
  document.addEventListener("keydown", function (e) {{ if (e.key === "Escape" && !card.hidden) hide(); }});

  // Touch: a tap on a finished country opens its piece straight away. A tap
  // that lands just beside one (within about 24px, which matters for small
  // countries such as Rwanda or Lesotho) opens the nearest finished piece.
  var touched = false;
  svg.addEventListener("pointerdown", function (e) {{
    touched = e.pointerType === "touch" || e.pointerType === "pen";
    if (touched) {{ touchAt = Date.now(); hide(); }}
  }});
  svg.addEventListener("click", function (e) {{
    if (!touched) return;
    touched = false;
    var hit = e.target.closest && e.target.closest(".m-piece");
    if (hit) return; // the country's own link opens the piece
    var box = svg.getBoundingClientRect(), k = box.width / {W};
    var best = null, bestD = 24;
    links.forEach(function (a) {{
      var dx = box.left + (+a.getAttribute("data-ax") - {VX}) * k - e.clientX;
      var dy = box.top + (+a.getAttribute("data-ay") - {VY}) * k - e.clientY;
      var d = Math.sqrt(dx * dx + dy * dy);
      if (d < bestD) {{ bestD = d; best = a; }}
    }});
    if (best) window.location.href = best.getAttribute("href");
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
