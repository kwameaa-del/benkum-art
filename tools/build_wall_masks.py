"""Build the wall masks for Cycle I's "In your space" rooms (cycle-i/in-your-space/rooms/<id>-wall.png).

Usage:
  python tools/build_wall_masks.py                            # all rooms
  python tools/build_wall_masks.py living --preview out_dir   # one room, plus a red overlay for checking

Cycle I only. Run it only when a room image changes; check every mask with --preview and a dark shade
in the viewer before committing.

How a mask is made:
  - REGION: the wall areas of the room, drawn from its measured lines (ceiling, skirting, corners, door frames).
  - CORE: furniture that is never tinted. 'soft' pieces (cream linen, ceramics, table tops, bookcases) are traced
    to their exact outline, because their colour is close to the wall's. 'wood' pieces are drawn loosely: wood is
    far warmer than the wall, so inside them a pixel is wall when it keeps the wall's hue (the wall under desks
    and between legs, often in shadow).
  - Next to furniture, a pixel is wall unless it is clearly wood-coloured, so the wall's contact shadows and warm
    bounced light are kept as wall.
  - The wall's own light is modelled as a smooth surface (fitted per room), and "hue" means the colour with
    brightness taken out, so shadowed wall still reads as wall.
"""
import pathlib, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROOMS = ROOT / "cycle-i" / "in-your-space" / "rooms"


def line(x0, y0, x1, y1):
    return lambda x: y0 + (y1 - y0) * (x - x0) / (x1 - x0)


liv_sk = line(1210, 678, 1530, 707)   # living: top of skirting
bed_sk = line(1290, 699, 1530, 719)   # bedroom: top of skirting
liv_top = lambda x: max(0, 81 - 0.141 * (x - 200)) + 3   # living: ceiling line

REGION = {
    "living": [[(186, liv_top(186)), *[(x, liv_top(x)) for x in range(250, 1537, 50)], (1536, liv_top(1536)), (1536, liv_sk(1536) - 2),
                *[(x, liv_sk(x) - 2) for x in range(1500, 185, -50)], (186, liv_sk(186) - 2)],
               [(92, 64), (183, 82), (183, 628), (92, 638)]],
    "bedroom": [[(122, 0), (1536, 0), (1536, bed_sk(1536) - 2), *[(x, bed_sk(x) - 2) for x in range(1500, 121, -50)], (122, bed_sk(122) - 2)]],
    "home": [[(0, 0), (1024, 0), (1024, 1116), (0, 1116)]],
    "studio": [[(0, 0), (1024, 0), (1024, 1196), (0, 1196)]],
    "library": [[(0, 0), (1024, 0), (1024, 1262), (0, 1262)]],
    "hallway": [[(132, 0), (922, 0), (922, 1120), (132, 1120)], [(930, 0), (1024, 0), (1024, 1158), (930, 1116)]],
}
CORE = {
    "living": {"soft": [[(165, 1024), (165, 548), (170, 538), (180, 533), (318, 532), (320, 472), (326, 469), (470, 468), (474, 482),
                         (735, 482), (1128, 485), (1134, 490), (1136, 540), (1150, 546), (1195, 546), (1197, 560), (1197, 1024)]],
               "wood": []},
    "bedroom": {"soft": [[(1126, 556), (1228, 556), (1228, 588), (1126, 588)],
                         [(0, 567), (378, 532), (440, 497), (490, 473), (491, 418), (496, 414), (1077, 414), (1082, 420), (1083, 600), (1083, 1024), (0, 1024)]],
                "wood": [[(1072, 560), (1282, 560), (1282, 785), (1072, 785)]]},
    "home": {"soft": [[(0, 772), (605, 768), (622, 772), (629, 790), (629, 849), (700, 857), (717, 868), (729, 884), (735, 900), (736, 1536), (0, 1536)],
                      [(912, 911), (962, 907), (977, 917), (979, 941), (965, 949), (963, 959), (913, 961), (909, 935)],
                      [(777, 951), (789, 937), (911, 941), (913, 958), (899, 967), (779, 967)],
                      [(758, 950), (1018, 950), (1018, 990), (758, 990)]],
             "wood": [[(758, 946), (1018, 946), (1018, 1145), (758, 1145)]]},
    "studio": {"soft": [[(680, 878), (752, 878), (752, 904), (680, 904)],
                        [(105, 900), (922, 900), (975, 957), (975, 996), (43, 996), (43, 957)],
                        [(370, 838), (646, 838), (646, 901), (370, 901)]],
               "wood": [[(40, 900), (984, 900), (984, 1440), (40, 1440)]]},
    "library": {"soft": [[(0, 966), (735, 966), (735, 1093), (752, 1093), (752, 1300), (0, 1300)],
                         [(784, 872), (1024, 872), (1024, 1300), (784, 1300)]],
                "wood": []},
    "hallway": {"soft": [[(440, 756), (528, 756), (528, 797), (440, 797)],
                         [(204, 789), (832, 789), (854, 799), (854, 819), (839, 819), (839, 857), (201, 857), (201, 819), (185, 819), (185, 799)]],
                "wood": [[(186, 790), (858, 790), (858, 1262), (186, 1262)]]},
}
BAND = 16                     # px beside furniture where only clearly wood-coloured pixels are excluded
WOOD_TOL = {"home": 0.08}     # deep warm shadow under the side table; its oak is ~0.1 away in hue


def poly(size, polys):
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    for p in polys:
        d.polygon([(float(x), float(y)) for x, y in p], fill=255)
    return m


def smooth_model(a, region, deg=2, iters=4):
    """Robust low-order polynomial fit of the wall's colour over the image (its light falloff)."""
    H, W, _ = a.shape
    ys, xs = np.nonzero(region)
    sel = np.random.default_rng(0).choice(len(xs), size=min(60000, len(xs)), replace=False)
    xs, ys = xs[sel], ys[sel]

    def terms(X, Y):
        return [np.ones_like(X)] + [X ** i * Y ** j for i in range(deg + 1) for j in range(deg + 1 - i) if i + j > 0]

    A = np.stack(terms(xs / W, ys / H), 1)
    keep = np.ones(len(xs), bool)
    for _ in range(iters):
        coef = np.linalg.lstsq(A[keep], a[ys[keep], xs[keep]], rcond=None)[0]
        res = np.abs(A @ coef - a[ys, xs]).max(1)
        keep = res < np.percentile(res[keep], 60) * 2.2
    gy, gx = np.mgrid[0:H, 0:W]
    return np.tensordot(np.stack(terms(gx / W, gy / H), -1), coef, axes=([2], [0]))


def build(room, preview=None):
    img = Image.open(ROOMS / f"{room}.webp").convert("RGB")
    region = np.asarray(poly(img.size, REGION[room])) > 0
    soft = np.asarray(poly(img.size, CORE[room]["soft"])) > 0
    wood = np.asarray(poly(img.size, CORE[room]["wood"])) > 0
    core = soft | wood
    k = 2 * (BAND // 2) + 1
    zone = np.asarray(Image.fromarray((core * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(k)).filter(ImageFilter.MaxFilter(k))) > 0
    a = np.asarray(img.filter(ImageFilter.GaussianBlur(1.0))).astype(np.float32)
    model = smooth_model(a, region & ~zone)
    eps = 1e-3
    hue_d = np.abs(a / (a.sum(2, keepdims=True) + eps) - model / (model.sum(2, keepdims=True) + eps)).max(2)
    lit = a.mean(2) > 0.15 * model.mean(2)
    beside = (hue_d < 0.06) & lit                                   # wall, incl. warm bounce and contact shadow
    inwood = wood & ~soft & region & (hue_d < WOOD_TOL.get(room, 0.06)) & lit
    iw = Image.fromarray((inwood * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    wall = (region & ~core & (~zone | beside)) | ((np.asarray(iw) > 0) & wood & ~soft)
    wi = Image.fromarray((wall * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    wi = Image.fromarray((np.asarray(wi) * region).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    wi.save(ROOMS / f"{room}-wall.png", optimize=True)
    if preview:
        red = Image.new("RGB", img.size, (255, 0, 0))
        Image.composite(Image.blend(img, red, 0.5), img, wi).save(pathlib.Path(preview) / f"{room}-wall-overlay.png")
    print(room, "wall share", round(float((np.asarray(wi) > 127).mean()), 3))


if __name__ == "__main__":
    args = sys.argv[1:]
    preview = None
    if "--preview" in args:
        i = args.index("--preview"); preview = args[i + 1]; del args[i:i + 2]
    for room in (args or list(REGION)):
        build(room, preview)
