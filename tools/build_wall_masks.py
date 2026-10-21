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
  - Each outline is only a hint: OpenCV's GrabCut snaps it to the real edge between furniture and wall,
    using the colours on both sides ('soft' pieces are solid; 'wood' pieces may have wall showing through,
    e.g. under a desk). Needs: pip install opencv-python-headless (build tool only; nothing on the site).
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
               [(90, 57), (120, 66), (150, 76), (188, 88), (188, 630), (90, 640)]],   # side wall by the window, up to the corner
    "bedroom": [[(122, 0), (1536, 0), (1536, bed_sk(1536) - 2), *[(x, bed_sk(x) - 2) for x in range(1500, 121, -50)], (122, bed_sk(122) - 2)]],
    "home": [[(0, 0), (1024, 0), (1024, 1116), (0, 1116)]],
    "studio": [[(0, 0), (1024, 0), (1024, 1196), (0, 1196)]],
    "library": [[(0, 0), (1024, 0), (1024, 1262), (0, 1262)]],
    "hallway": [[(132, 0), (927, 0), (927, 1120), (132, 1120)], [(925, 0), (1024, 0), (1024, 1158), (925, 1116)]],
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
                      [(758, 950), (1018, 950), (1018, 990), (758, 990)],
                      [(877, 986), (909, 986), (907, 1146), (879, 1146)]],   # middle leg, in shadow
             "wood": [[(758, 946), (1018, 946), (1018, 1145), (758, 1145)]]},
    "studio": {"soft": [[(680, 878), (752, 878), (752, 904), (680, 904)],
                        [(105, 900), (922, 900), (975, 957), (975, 996), (43, 996), (43, 957)],
                        [(370, 838), (646, 838), (646, 901), (370, 901)]],
               "wood": [[(40, 900), (984, 900), (984, 1440), (40, 1440)]]},
    "library": {"soft": [[(0, 966), (735, 966), (735, 1093), (752, 1093), (752, 1300), (0, 1300)],
                         [(784, 872), (1024, 872), (1024, 1300), (784, 1300)]],
                "wood": []},
    "hallway": {"soft": [[(437, 754), (528, 756), (530, 762), (522, 776), (508, 786), (495, 792), (459, 792), (447, 782), (440, 770), (435, 761)],
                         [(204, 789), (832, 789), (854, 799), (854, 819), (839, 819), (839, 857), (201, 857), (201, 819), (185, 819), (185, 799)]],
                "wood": [[(186, 790), (858, 790), (858, 1262), (186, 1262)]]},
}
BAND = 16                     # px beside furniture where only clearly wood-coloured pixels are excluded
TRUST = {("hallway", "soft", 0)}   # the pale bowl is too close to the wall's colour to segment: use its traced outline
SURE = {"living": 3}     # px inside a traced outline that is certainly furniture (living: shaded sofa arm)
WOOD_TOL = {"home": 0.08, "bedroom": 0.048, "studio": 0.04, "hallway": 0.075}   # per-room hue tolerance for wall seen through wooden furniture (oak is ~0.09+ away)


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


def _box(x, r):
    """Mean over a (2r+1) square window (edges clamped)."""
    k = 2 * r + 1
    p = np.pad(np.asarray(x, np.float64), [(r + 1, r), (r + 1, r)] + [(0, 0)] * (x.ndim - 2), mode="edge")   # float64: no cancellation
    c = p.cumsum(0).cumsum(1)
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def guided_filter(I, p, r, eps):
    """Colour-guided filter (He, Sun & Tang): smooths p while following the edges of the RGB guide I."""
    mI = _box(I, r); mp = _box(p, r)
    cov = _box(I * p[..., None], r) - mI * mp[..., None]
    var = np.empty(I.shape[:2] + (3, 3), np.float64)
    for i in range(3):
        for j in range(3):
            var[..., i, j] = _box(I[..., i] * I[..., j], r) - mI[..., i] * mI[..., j]
    var += eps * np.eye(3)
    a = np.linalg.solve(var, cov[..., None])[..., 0]
    b = mp - (a * mI).sum(2)
    return (_box(a, r) * I).sum(2) + _box(b, r)


def snap(img_bgr, objmask, solid, pad=48, sure=9, trust=False):
    """Snap a hand-drawn furniture outline to the real edge with GrabCut. The outline is only a hint:
    inside it is 'probably furniture' (and, for solid pieces, its core is 'certainly furniture'),
    a band around it is 'probably wall', and further out is 'certainly wall'."""
    import cv2
    H, W = objmask.shape
    ys, xs = np.nonzero(objmask)
    if not len(xs):
        return objmask
    x0, x1 = max(0, xs.min() - pad), min(W, xs.max() + pad + 1)
    y0, y1 = max(0, ys.min() - pad), min(H, ys.max() + pad + 1)
    om = objmask[y0:y1, x0:x1].astype(np.uint8) * 255
    k = lambda r: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    m = np.full(om.shape, cv2.GC_BGD, np.uint8)
    m[cv2.dilate(om, k(22)) > 0] = cv2.GC_PR_BGD
    m[om > 0] = cv2.GC_PR_FGD
    if solid:
        m[(om > 0) if trust else (cv2.erode(om, k(sure)) > 0)] = cv2.GC_FGD   # trust: outline traced exactly
    bgd = np.zeros((1, 65), np.float64); fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(np.ascontiguousarray(img_bgr[y0:y1, x0:x1]), m, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    fg = ((m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD)).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, k(1))
    if solid:   # solid pieces have no wall inside them: fill any holes
        inv = (1 - fg).astype(np.uint8)
        n, lab = cv2.connectedComponents(inv)
        border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])).tolist())
        fg = np.where(np.isin(lab, list(border)), fg, 1).astype(np.uint8)
    out = np.zeros_like(objmask)
    out[y0:y1, x0:x1] = fg > 0
    return out


def build(room, preview=None):
    import cv2
    img = Image.open(ROOMS / f"{room}.webp").convert("RGB")
    bgr = np.ascontiguousarray(np.asarray(img)[:, :, ::-1])
    region = np.asarray(poly(img.size, REGION[room])) > 0
    # The wall's own colour, without brightness, so shadowed wall still matches (wood is far warmer).
    a = np.asarray(img.filter(ImageFilter.GaussianBlur(1.0))).astype(np.float32)
    model = smooth_model(a, region)
    eps = 1e-3
    hue_d = np.abs(a / (a.sum(2, keepdims=True) + eps) - model / (model.sum(2, keepdims=True) + eps)).max(2)
    wallish = (hue_d < WOOD_TOL.get(room, 0.06)) & (a.mean(2) > 0.15 * model.mean(2))
    furniture = np.zeros(region.shape, bool)
    for kind in ("soft", "wood"):
        for n, p in enumerate(CORE[room][kind]):
            fg = snap(bgr, np.asarray(poly(img.size, [p])) > 0, solid=(kind == "soft"), sure=SURE.get(room, 9),
                      trust=(room, kind, n) in TRUST)
            if kind == "wood":   # wall seen between legs and under tops stays wall
                keep = np.asarray(Image.fromarray((wallish & fg * 1).astype(np.uint8) * 255)
                                  .filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))) > 0
                fg = fg & ~keep
            furniture |= fg
    # Drop specks: tiny wall islands inside furniture and tiny furniture islands on open wall.
    wall = region & ~furniture
    for target in (True, False):
        n, lab, stats, _ = cv2.connectedComponentsWithStats((wall == target).astype(np.uint8), connectivity=8)
        small = np.isin(lab, [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] < 400])
        wall = np.where(small, not target, wall) & region
    # Edge-aware matting: a colour-guided filter snaps the mask's edge to the photo's own edges, so there is no
    # pale rim or tinted fringe where furniture meets wall. Region edges (skirting, ceiling, corners) stay hard.
    alpha = guided_filter(np.asarray(img.filter(ImageFilter.GaussianBlur(0.8))).astype(np.float32) / 255, wall.astype(np.float32), r=3, eps=4e-3)
    alpha = np.clip((alpha - 0.2) / 0.6, 0, 1)
    alpha = np.where(np.abs(alpha - wall) > 0.5, wall, alpha)   # matting may soften an edge, never flip a pixel
    inner = Image.fromarray((region * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(5))   # stay 2 px off skirting, ceiling and corners
    alpha = alpha * np.asarray(inner.filter(ImageFilter.GaussianBlur(0.9))).astype(np.float32) / 255   # anti-aliased, no stair steps
    wi = Image.fromarray((alpha * 255 + 0.5).astype(np.uint8))
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
