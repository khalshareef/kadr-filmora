"""Split screens for filmora_wfp / filmora_fx projects — two ways.

1. split_layout()  — the house default.  Builds the split DIRECTLY ON THE MAIN TIMELINE (no container clip):
   every part is the real video/image clip on its own track, scaled to COVER its region (centre crop like Filmora,
   or around a chosen focus point) and cut to that region by a native rect mask (filmora_mask).  Everything stays
   visible and editable on the timeline.  Layouts: 2v 2h 3v 3h 1+2 2x2 diag2 (+ gap, margin, background colour,
   rounded corners, thin divider lines as native shapes).

2. template_split() — Filmora's OWN split-screen template clip (Templates > Split Screen, must be downloaded in
   Filmora first), written exactly like Filmora 16 saves it after "Advanced Split Screen Edit" > Apply.
   NOTE: this is a CONTAINER clip (type 10) with inner timelines — the parts are only visible inside Filmora's
   split-screen editor, not on the main timeline.  Use it only when the user asks for Filmora's animated templates.

Format of the template clip (decoded from projects/samples/Sample Split Screen.wfp, Filmora 16.0.12; notes in
_work/decode_split.md):
  main timeline   video track:  clip type 10 "SplitScreenClip" {timelineId: T, splitCount: n, isSplitExtended: true,
                                 userData 12 = resource info json (res_type 5), 50 = title, 1 = 11, 2 = 1, 102 = 2}
                  its paired audio track:  clip type 6 {isAudio: 1, timelineId: T, userData 3 = SAME guid (38 bytes)}
  timeline T (type 2):  n video tracks [type 6 -> part timeline Pi], 1 track [type 9 border MaskClip maskIndex -1:
                  color/size/alpha], n audio tracks [type 6 isAudio -> Pi]; type-6 clips: inPoint 0,
                  outPoint = 3600 s + dur, speed offsetEnd = 3600 + dur (Filmora's own quirk, copied)
  part timeline Pi (type 5):  [the real media clip, whole length, Position = template CenterPoint],
                  [type 9 MaskClip {maskSchema "<folder>/<ratio>/Data/<name>.json", maskIndex i,
                  defaultPath "Montage/<ratio>/m0i.png"}], [the media's own audio clip, type 2]
  template files: <Download>/Filmora/montage/5_<slug>/<ratio>/Data/{data.xml, *.json (Lottie), *.svg}

Usage:
    from filmora_fx import FxProject
    import filmora_split as fsp
    p = FxProject("Split", 1080, 1920)
    fsp.split_layout(p, "2h", ["a.mp4", {"path": "b.mp4", "src_in": 2.0, "focus": (0.5, 0.35)}], 0, 4,
                     gap=12, background="#141413", divider=None)
    fsp.template_split(p, "Split Screen 4", ["a.mp4", "b.mp4"], 4, 8)
    p.save("out.wfp")

CLI:  python filmora_split.py layouts | templates [--online]
"""
import copy, glob, hashlib, json, math, os, re, sys, zipfile

from filmora_wfp import (TICKS, get_ud, guid, pip_buf, set_ud, speed_param, thisuid, ud, ud_guid, ud_guid64, ud_int,
                         ud_str)
import filmora_mask
import filmora_paths

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff", ".gif")
LAYOUTS = {
    "2v": "two side by side (left | right)",
    "2h": "two stacked (top / bottom)",
    "3v": "three columns",
    "3h": "three rows",
    "1+2": "one big + two small (big left on wide frames, big top on tall frames; big=, ratio=)",
    "2x2": "2 x 2 grid",
    "diag2": "two parts with a slanted divider (like Filmora's Split Screen 4; slant=)",
}
# Mask rotation direction.  ASSUMED: positive degrees = clockwise on screen (y down), like the clip transform.
# Only diag2 with diag_mask="rect" depends on it — if Filmora shows the slanted edge mirrored, set this to -1.
MASK_ROT_SIGN = 1.0


# ====================================================================== geometry (pure, no project needed)
def _rect_regions(layout, W, H, ratio=0.6, big="auto"):
    """Regions as (x0, y0, x1, y1) in px."""
    if layout == "2v":
        return [(0, 0, W / 2, H), (W / 2, 0, W, H)]
    if layout == "2h":
        return [(0, 0, W, H / 2), (0, H / 2, W, H)]
    if layout == "3v":
        return [(W * i / 3, 0, W * (i + 1) / 3, H) for i in range(3)]
    if layout == "3h":
        return [(0, H * i / 3, W, H * (i + 1) / 3) for i in range(3)]
    if layout == "2x2":
        return [(0, 0, W / 2, H / 2), (W / 2, 0, W, H / 2), (0, H / 2, W / 2, H), (W / 2, H / 2, W, H)]
    if layout == "1+2":
        side = big if big != "auto" else ("left" if W >= H else "top")
        r = float(ratio)
        if side == "left":
            a = W * r
            return [(0, 0, a, H), (a, 0, W, H / 2), (a, H / 2, W, H)]
        if side == "right":
            a = W * (1 - r)
            return [(a, 0, W, H), (0, 0, a, H / 2), (0, H / 2, a, H)]
        if side == "top":
            a = H * r
            return [(0, 0, W, a), (0, a, W / 2, H), (W / 2, a, W, H)]
        if side == "bottom":
            a = H * (1 - r)
            return [(0, a, W, H), (0, 0, W / 2, a), (W / 2, 0, W, a)]
        raise ValueError("big must be auto|left|right|top|bottom")
    raise ValueError(f"unknown layout {layout!r}; choose from {', '.join(LAYOUTS)}")


def _inset(reg, W, H, gap, margin):
    x0, y0, x1, y1 = reg
    e = 0.5
    x0 = x0 + (margin if x0 < e else gap / 2)
    y0 = y0 + (margin if y0 < e else gap / 2)
    x1 = x1 - (margin if x1 > W - e else gap / 2)
    y1 = y1 - (margin if y1 > H - e else gap / 2)
    return (x0, y0, x1, y1)


def _diag_line(W, H, slant):
    """End points (px) of Split Screen 4's slanted divider: on wide frames from the top edge (right of centre) to the
    bottom edge (left of centre) — Filmora's 16_9 polygon is (0,0) (1130.6,0) (791.9,1080) (0,1080) -> slant 0.1764 of
    the width; on tall frames turned 90 deg: from the left edge (lower) to the right edge (higher)."""
    if W >= H:
        return (W * (0.5 + slant / 2), 0.0), (W * (0.5 - slant / 2), float(H))
    return (0.0, H * (0.5 + slant / 2)), (float(W), H * (0.5 - slant / 2))


def _cover(sw, sh, rw, rh, W, H, focus=(0.5, 0.5), zoom=1.0):
    """Cover a rw x rh region with a sw x sh picture.  Returns (k = frame px per source px, Filmora Scale %,
    (ucx, vcy) = centre of the visible window in source px)."""
    fit = min(W / sw, H / sh)                         # Filmora Scale 100 % = fit to frame
    k = max(rw / sw, rh / sh) * max(1.0, float(zoom))
    ww, wh = rw / k, rh / k
    fx, fy = focus
    ucx = min(max(fx * sw, ww / 2), sw - ww / 2)
    vcy = min(max(fy * sh, wh / 2), sh - wh / 2)
    return k, 100.0 * k / fit, (ucx, vcy)


def plan_split(W, H, layout, sources, gap=0.0, margin=0.0, ratio=0.6, big="auto", slant=0.1764, bleed=None,
               radius=0.0, diag_mask="rect"):
    """Pure layout maths.  sources: [{"w": src width, "h": src height, "focus": (fx, fy), "zoom": 1.0}, ...] one per part
    (cycled if fewer).  Returns one dict per part, spec-compatible:
        {"x", "y", "scale", "mask": {shape, x, y, w, h, rotation, radius}, "region": (x0, y0, x1, y1) px,
         "polygon": [(x, y), ...] px (diag2) }
    gap / margin / bleed in px of the frame.  bleed (default 1 px when gap == 0) widens every mask so neighbouring parts
    overlap a hair and no seam shows."""
    if bleed is None:
        bleed = 1.0 if not gap else 0.0
    parts = []
    if layout == "diag2":
        P1, P2 = _diag_line(W, H, slant)
        t = (P2[0] - P1[0], P2[1] - P1[1])
        L = math.hypot(*t)
        t = (t[0] / L, t[1] / L)
        n0 = (-t[1], t[0])
        wide = W >= H
        for i in range(2):
            # part 0 = left (wide) / top (tall); n = unit normal pointing INTO the part
            probe = (0.0, 0.0) if i == 0 else (float(W), float(H))
            M = ((P1[0] + P2[0]) / 2, (P1[1] + P2[1]) / 2)
            n = n0 if (probe[0] - M[0]) * n0[0] + (probe[1] - M[1]) * n0[1] > 0 else (-n0[0], -n0[1])
            off = gap / 2 - bleed                         # move the edge into the part by half the gap
            A = (P1[0] + n[0] * off, P1[1] + n[1] * off)
            B = (P2[0] + n[0] * off, P2[1] + n[1] * off)
            if wide:
                # extend the shifted line to the top/bottom frame edges
                ax = A[0] + (0 - A[1]) * t[0] / t[1]
                bx = A[0] + (H - A[1]) * t[0] / t[1]
                poly = [(0, 0), (ax, 0), (bx, H), (0, H)] if i == 0 else [(ax, 0), (W, 0), (W, H), (bx, H)]
                reg = (0, 0, max(ax, bx), H) if i == 0 else (min(ax, bx), 0, W, H)
            else:
                ay = A[1] + (0 - A[0]) * t[1] / t[0]
                by = A[1] + (W - A[0]) * t[1] / t[0]
                poly = [(0, 0), (W, 0), (W, by), (0, ay)] if i == 0 else [(0, ay), (W, by), (W, H), (0, H)]
                reg = (0, 0, W, max(ay, by)) if i == 0 else (0, min(ay, by), W, H)
            s = sources[i % len(sources)]
            rw, rh = reg[2] - reg[0], reg[3] - reg[1]
            k, scale, (ucx, vcy) = _cover(s["w"], s["h"], rw, rh, W, H, s.get("focus", (0.5, 0.5)), s.get("zoom", 1.0))
            rcx, rcy = (reg[0] + reg[2]) / 2, (reg[1] + reg[3]) / 2
            cx, cy = rcx + (s["w"] / 2 - ucx) * k, rcy + (s["h"] / 2 - vcy) * k
            part = {"x": cx / W, "y": cy / H, "scale": scale, "region": reg, "polygon": poly, "k": k}
            if diag_mask == "image":
                part["mask"] = {"shape": "image", "x": 0.5, "y": 0.5, "w": 1.0, "h": 1.0}   # PNG made by split_layout
            else:
                # one huge rotated rectangle whose near edge lies on the (shifted) divider line
                big_len = 1.5 * math.hypot(W, H)
                D = big_len
                Mi = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
                C = (Mi[0] + n[0] * D / 2, Mi[1] + n[1] * D / 2)
                us = (C[0] - cx) / k + s["w"] / 2
                vs = (C[1] - cy) / k + s["h"] / 2
                rot = math.degrees(math.atan2(-t[0], t[1]))      # local y axis -> along the line (clockwise-positive)
                if rot > 90:
                    rot -= 180
                elif rot <= -90:
                    rot += 180
                part["mask"] = {"shape": "rect", "x": us / s["w"], "y": vs / s["h"], "w": D / k / s["w"],
                                "h": big_len / k / s["h"], "rotation": MASK_ROT_SIGN * rot}
            parts.append(part)
        return parts

    for i, reg in enumerate(_rect_regions(layout, W, H, ratio, big)):
        reg = _inset(reg, W, H, gap, margin)
        s = sources[i % len(sources)]
        rw, rh = reg[2] - reg[0], reg[3] - reg[1]
        if rw <= 2 or rh <= 2:
            raise ValueError(f"part {i} of {layout} is too small after gap/margin")
        k, scale, (ucx, vcy) = _cover(s["w"], s["h"], rw, rh, W, H, s.get("focus", (0.5, 0.5)), s.get("zoom", 1.0))
        rcx, rcy = (reg[0] + reg[2]) / 2, (reg[1] + reg[3]) / 2
        cx, cy = rcx + (s["w"] / 2 - ucx) * k, rcy + (s["h"] / 2 - vcy) * k
        m = {"shape": "rect", "x": ucx / s["w"], "y": vcy / s["h"],
             "w": (rw + 2 * bleed) / k / s["w"], "h": (rh + 2 * bleed) / k / s["h"]}
        if radius:
            m["radius"] = float(radius)
        parts.append({"x": cx / W, "y": cy / H, "scale": scale, "region": reg, "k": k, "mask": m})
    return parts


def divider_segments(W, H, layout, ratio=0.6, big="auto", slant=0.1764):
    """Internal edges of a layout as ((x0, y0), (x1, y1)) in px — where thin divider lines go."""
    if layout == "diag2":
        return [_diag_line(W, H, slant)]
    regs = _rect_regions(layout, W, H, ratio, big)
    segs = set()
    e = 0.5
    for x0, y0, x1, y1 in regs:
        for (a, b) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x0, y1), (x1, y1)), ((x0, y0), (x0, y1))):
            on_border = (a[0] < e and b[0] < e) or (a[0] > W - e and b[0] > W - e) or \
                        (a[1] < e and b[1] < e) or (a[1] > H - e and b[1] > H - e)
            if not on_border:
                segs.add((tuple(round(v, 3) for v in a), tuple(round(v, 3) for v in b)))
    # merge collinear touching segments (e.g. the middle line of a 2x2 grid)
    segs = sorted(segs)
    merged = True
    while merged:
        merged = False
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                (a, b), (c, d) = segs[i], segs[j]
                if a[0] == b[0] == c[0] == d[0] and max(a[1], c[1]) <= min(b[1], d[1]):        # same x, touching/overlap
                    segs[i] = ((a[0], min(a[1], c[1])), (a[0], max(b[1], d[1])))
                elif a[1] == b[1] == c[1] == d[1] and max(a[0], c[0]) <= min(b[0], d[0]):
                    segs[i] = ((min(a[0], c[0]), a[1]), (max(b[0], d[0]), a[1]))
                else:
                    continue
                del segs[j]
                merged = True
                break
            if merged:
                break
    return segs


# ====================================================================== project helpers
def _src(item):
    return {"path": item} if isinstance(item, str) else dict(item)


def _is_image(path):
    return os.path.splitext(path)[1].lower() in IMAGE_EXT


def _media_size(project, path):
    if _is_image(path):
        from PIL import Image
        return Image.open(path).size
    m = project._video_media(path)
    vs = m["res"]["vidStreamInfo"][0]
    return int(vs["width"]), int(vs["height"])


def _make_clip(project, src, start, end, x, y, scale):
    path = src["path"]
    if _is_image(path):
        return project.image_clip(path, start, end, x=x, y=y, scale=scale)
    return project.video_clip(path, start, end, src_in=float(src.get("src_in", 0.0)), x=x, y=y, scale=scale)


def place_on_lanes(project, clips, first_lane=0):
    """Put clips on the main timeline, each on its own track above the previous one (lowest free tracks >= first_lane).
    Returns the lane indices used."""
    used, floor = [], first_lane
    for c in clips:
        L = floor
        while L < len(project.layers) and any(o["tlBegin"] < c["tlEnd"] and c["tlBegin"] < o["tlEnd"] for o in project.layers[L]):
            L += 1
        while L >= len(project.layers):
            project.layers.append([])
        project.layers[L].append(c)
        project.layers[L].sort(key=lambda o: o["tlBegin"])
        used.append(L)
        floor = L + 1
    return used


def _solid_png(color, W, H, folder):
    from PIL import Image
    os.makedirs(folder, exist_ok=True)
    rgb = str(color).lstrip("#")[:6]
    path = os.path.join(folder, f"split_bg_{rgb}_{W}x{H}.png")
    if not os.path.exists(path):
        Image.new("RGB", (16 * W // math.gcd(W, H), 16 * H // math.gcd(W, H)), "#" + rgb).save(path)
    return path


def _poly_mask_png(poly_src, sw, sh, folder, name):
    """White polygon on transparent, same aspect as the source picture (poly in source px)."""
    from PIL import Image, ImageDraw
    os.makedirs(folder, exist_ok=True)
    f = min(1.0, 1280.0 / max(sw, sh))
    im = Image.new("RGBA", (max(1, round(sw * f)), max(1, round(sh * f))), (255, 255, 255, 0))
    ImageDraw.Draw(im).polygon([(u * f, v * f) for u, v in poly_src], fill=(255, 255, 255, 255))
    path = os.path.join(folder, name)
    im.save(path)
    return path


# ====================================================================== 1. split on the main timeline
def split_layout(project, layout, clips, start, end, gap=0.0, margin=0.0, ratio=0.6, big="auto", slant=0.1764,
                 radius=0.0, background=None, divider=None, diag_mask="rect", first_lane=0, assets_dir=None,
                 bleed=None, place=True):
    """Build a split screen from plain clips on the main timeline (no container).

    layout    2v | 2h | 3v | 3h | 1+2 | 2x2 | diag2
    clips     paths or dicts {"path", "src_in" (s), "focus": (fx, fy) 0..1 of the source = what to keep in view,
              "zoom": >= 1 extra push-in}; cycled if fewer than the parts
    gap       px between parts (frame pixels); margin = px around the outside (rect layouts only)
    radius    rounded part corners (mask Radius 0..1)
    background  '#RRGGBB' (a solid picture is written to assets_dir) or a picture/video path, under the parts —
              only needed with gap/margin (else the frame is fully covered)
    divider   None or {"color": "#FFFFFF", "width": 8 (px), "opacity": 100} -> thin native shape lines on the internal
              edges (straight layouts: thin filled rectangles; diag2: a line shape, rotation sign UNVERIFIED)
    diag_mask "rect" (editable rotated rect mask; rotation sign assumed, see MASK_ROT_SIGN) | "image" (exact PNG
              polygon as an image mask; sign-free)
    first_lane  lowest main-timeline track index to use (0 = bottom video track)
    Returns {"parts": [clip, ...], "background": clip|None, "dividers": [clip, ...], "lanes": [...], "plan": [...]}.
    With place=False nothing is added to the timeline (caller places the clips)."""
    W, H = project.W, project.H
    srcs = [_src(c) for c in clips]
    if not srcs:
        raise ValueError("split_layout needs at least one clip")
    for s in srcs:
        s["w"], s["h"] = _media_size(project, s["path"])
    plan = plan_split(W, H, layout, srcs, gap, margin, ratio, big, slant, bleed, radius, diag_mask)
    assets_dir = assets_dir or os.path.join(filmora_paths.project_dir(), "split_assets")
    out = {"parts": [], "background": None, "dividers": [], "lanes": [], "plan": plan}
    order = []
    if background:
        bg = background if os.path.exists(str(background)) else _solid_png(background, W, H, assets_dir)
        bs = {"path": bg}
        bw, bh = _media_size(project, bg)
        k, sc, _ = _cover(bw, bh, W, H, W, H)
        out["background"] = _make_clip(project, bs, start, end, 0.5, 0.5, sc)
        order.append(out["background"])
    for i, part in enumerate(plan):
        s = srcs[i % len(srcs)]
        c = _make_clip(project, s, start, end, part["x"], part["y"], part["scale"])
        m = dict(part["mask"])
        shape = m.pop("shape")
        if shape == "image":
            k = part["k"]
            cx, cy = part["x"] * W, part["y"] * H
            poly = [((px - cx) / k + s["w"] / 2, (py - cy) / k + s["h"] / 2) for px, py in part["polygon"]]
            tag = hashlib.md5(repr((s["path"], s["w"], s["h"], [tuple(round(v, 1) for v in q) for q in poly])).encode()).hexdigest()[:8]
            m["image"] = _poly_mask_png(poly, s["w"], s["h"], assets_dir, f"split_{layout}_{i}_{tag}.png")
        filmora_mask.add_mask(c, shape, project=project, src_size=(s["w"], s["h"]), **m)
        out["parts"].append(c)
        order.append(c)
    if divider:
        import filmora_shape
        col, wpx, op = divider.get("color", "#FFFFFF"), float(divider.get("width", 8)), divider.get("opacity", 100)
        for (a, b) in divider_segments(W, H, layout, ratio, big, slant):
            if layout == "diag2":
                # shape sizes must stay within 0..1 of the frame width -> draw it shorter and scale the clip up
                f = max(1.0, math.hypot(b[0] - a[0], b[1] - a[1]) / W / 0.95)
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                q1 = ((mx + (a[0] - mx) / f) / W, (my + (a[1] - my) / f) / H)
                q2 = ((mx + (b[0] - mx) / f) / W, (my + (b[1] - my) / f) / H)
                d = filmora_shape.shape_clip(project, "line", start, end, p1=q1, p2=q2, scale=100.0 * f,
                                             stroke=col, stroke_width=min(20, max(1, wpx / 2 / f)), cap="butt", opacity=op)
            elif a[0] == b[0]:          # vertical edge
                d = filmora_shape.shape_clip(project, "rect", start, end, x=a[0] / W, y=(a[1] + b[1]) / 2 / H,
                                             w=wpx / W, h=abs(b[1] - a[1]) / H, fill=col, stroke=None, opacity=op)
            else:                       # horizontal edge
                d = filmora_shape.shape_clip(project, "rect", start, end, x=(a[0] + b[0]) / 2 / W, y=a[1] / H,
                                             w=abs(b[0] - a[0]) / W, h=wpx / H, fill=col, stroke=None, opacity=op)
            out["dividers"].append(d)
    if place:
        out["lanes"] = place_on_lanes(project, order, first_lane)
        if out["dividers"]:                               # above the parts, one track each (they play at the same time)
            out["lanes"] += place_on_lanes(project, out["dividers"], max(out["lanes"]) + 1)
    return out


# ====================================================================== 2. Filmora's own template clip
RATIOS = {"16_9": 16 / 9, "9_16": 9 / 16, "1_1": 1.0, "4_3": 4 / 3, "3_4": 3 / 4, "21_9": 21 / 9}


def montage_dir():
    return os.path.join(filmora_paths.download_dir(), "montage")


def _parse_svg(path):
    s = open(path, encoding="utf-8").read()
    vb = re.search(r'viewBox="([\d.\s-]+)"', s)
    vw, vh = (float(v) for v in vb.group(1).split()[2:4]) if vb else (1920.0, 1080.0)
    boxes = {}
    for tag in re.findall(r"<(?:rect|polygon)[^>]*>", s):
        cls = re.search(r'class="Mask_(\d+)"', tag)
        if not cls:
            continue
        i = int(cls.group(1)) - 1
        if tag.startswith("<rect"):
            g = lambda k, d=0.0: float(re.search(rf'\b{k}="([\d.-]+)"', tag).group(1)) if re.search(rf'\b{k}="', tag) else d
            x, y, w, h = g("x"), g("y"), g("width"), g("height")
            pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        else:
            nums = [float(v) for v in re.findall(r"[\d.]+", re.search(r'points="([^"]+)"', tag).group(1))]
            pts = list(zip(nums[0::2], nums[1::2]))
        boxes[i] = [(px / vw, py / vh) for px, py in pts]
    return boxes


def _template_info(folder):
    rj = json.load(open(os.path.join(folder, "resinfo.json"), encoding="utf-8"))
    ratios = sorted(r for r in RATIOS if os.path.isdir(os.path.join(folder, r)))
    info = {"folder": folder, "dir_name": os.path.basename(folder), "id": rj.get("id"), "slug": rj.get("slug"),
            "title": rj.get("titles", {}).get("en", rj.get("slug")), "title_ar": rj.get("titles", {}).get("ae", ""),
            "res_type": rj.get("type", 5), "source": rj.get("source", 1), "sale_mode": rj.get("sale_mode", 0),
            "resourceRate": rj.get("resourceRate", 4), "ratios": ratios, "parts": None}
    if ratios:
        r = "16_9" if "16_9" in ratios else ratios[0]
        info["parts"] = len(_ratio_data(folder, r)["parts"])
    return info


def _ratio_data(folder, ratio):
    data = os.path.join(folder, ratio, "Data")
    xml = open(os.path.join(data, "data.xml"), encoding="utf-8").read()
    schema = re.search(r'key="Schema.File"[^>]*value="%TemplatePath%/([^"]+)"', xml).group(1)
    anim = re.search(r'key="SplitScreen.AnimationEnabled"[^>]*value="(\d+)"', xml)
    parts = []
    for blk in re.findall(r"<TimeLine>\s*<Properties.*?</Properties>\s*</TimeLine>", xml, re.S):
        fp = re.search(r'key="Absolute.FilePath"[^>]*value="([^"]+)"', blk)
        cp = re.search(r'key="Transform.CenterPoint"[^>]*value="x:([\d.-]+), y:([\d.-]+)"', blk)
        lv = re.search(r'key="Level"[^>]*value="(\d+)"', blk)
        if fp and cp:
            parts.append({"path": fp.group(1), "x": float(cp.group(1)), "y": float(cp.group(2)), "level": int(lv.group(1)) if lv else len(parts)})
    parts.sort(key=lambda p: p["level"])
    lot = json.load(open(os.path.join(data, schema), encoding="utf-8"))
    stroke = None
    for layer in lot.get("layers", []):
        if layer.get("nm", "").lower().startswith("stroke"):
            for grp in layer.get("shapes", []):
                for it in grp.get("it", []):
                    if it.get("ty") == "st":
                        c = it["c"]["k"]
                        stroke = {"size": int(round(it["w"]["k"])), "color": (int(c[0] * 255) << 16) | (int(c[1] * 255) << 8) | int(c[2] * 255)}
    svgs = glob.glob(os.path.join(data, "*.svg"))
    boxes = _parse_svg(svgs[0]) if svgs else {}
    return {"schema": schema, "parts": parts, "stroke": stroke, "animation": None if not anim else int(anim.group(1)),
            "polys": boxes, "w": lot.get("w"), "h": lot.get("h")}


def installed_templates():
    root = montage_dir()
    out = []
    for f in sorted(glob.glob(os.path.join(root, "*"))):
        if os.path.isfile(os.path.join(f, "resinfo.json")):
            try:
                out.append(_template_info(f))
            except Exception as e:                      # a broken download should not hide the others
                out.append({"folder": f, "dir_name": os.path.basename(f), "error": str(e)})
    return out


def online_templates():
    """Split-screen templates Filmora knows about online (resInfo.db, res_type 5) — they must be downloaded in
    Filmora (Templates > Split Screen) before template_split can use them."""
    import sqlite3
    db = os.path.join(os.path.dirname(filmora_paths.library_xml()), "resInfo.db")
    if not os.path.exists(db):
        return []
    con = sqlite3.connect(db)
    rows = con.execute("select res_id, res_slug, res_sale_mode, res_titles, res_info_json from onlineCloudResourceInfo "
                       "where res_type = 5").fetchall()
    con.close()
    have = {t.get("slug") for t in installed_templates()}
    out = []
    for rid, slug, sale, titles, js in rows:
        try:
            cats = [c.get("name") for c in json.loads(js).get("categories", [])]
        except Exception:
            cats = []
        out.append({"id": rid, "slug": slug, "title": json.loads(titles).get("en", slug), "paid": bool(sale),
                    "categories": sorted(set(cats)), "installed": slug in have})
    return sorted(out, key=lambda t: t["slug"])


def find_template(name):
    key = str(name).lower().replace("_", " ").strip()
    tpl = [t for t in installed_templates() if "error" not in t]
    for t in tpl:
        cands = {str(t.get(k, "")).lower().replace("_", " ") for k in ("title", "slug", "dir_name", "title_ar")}
        if key in cands:
            return t
    raise KeyError(f"split-screen template {name!r} is not downloaded in Filmora. Installed: "
                   + ", ".join(f"{t['title']} ({t['parts']} parts)" for t in tpl)
                   + ". Download it in Filmora: Templates > Split Screen, then try again.")


def _ratio_for(project, ratios):
    a = project.W / project.H
    return min(ratios, key=lambda r: abs(math.log(RATIOS[r] / a)))


def _chain(ud3=True, ud7=False, transform_params=None):
    def eff(display):
        e = {"display": display, "id": f"video/effect/{display}", "placeholder": False, "placeholderStatus": 0,
             "thisUId": thisuid(), "type": 3}
        if ud3:
            e["userData"] = [ud_guid64(3, guid())] + ([ud(7, b"\x01")] if ud7 else [])
        return e
    cpz, tf = eff("crop-pan-zoom"), eff("transform")
    if transform_params is not None:
        tf["paramList"] = [{"fxParam": {"paramType": 5, "unValue": 1186339}, "name": "dwValue"}]
        tf["userData"] = [ud_str(15005, "1.0"), ud_guid64(3, guid()), ud(7, b"\x01"), ud_str(36880, "1", nul=True)]
    return [{"effectList": [cpz, tf], "name": "Basic"}, {"effectList": [], "name": "Effect"},
            {"effectList": [], "name": "_wes_hold_effectchain_"}]


def _pip():
    return pip_buf(100.0)


def _timeline(project, tl_id, tl_type, tracks, bus):
    from filmora_wfp import aspect
    ax, ay = aspect(project.W, project.H)
    return {"aspectRatioX": ax, "aspectRatioY": ay, "audioBusInfos": [{"balance": 0.5, "busUid": bus, "gain": 0.0}],
            "channels": 2, "format": "f32", "frameRate": {"den": 1, "num": project.fps}, "hdrMode": 0,
            "hdrMode_force_16bit": 0, "resolutionHeight": project.H, "resolutionWidth": project.W, "sampleRate": 44100,
            "timelineId": tl_id, "trackInfos": tracks, "type": tl_type,
            "userData": [ud_guid64(11000, guid()), ud_guid64(3, guid())]}


def _mask_clip(dur, schema, index, path, tl_id=None, size=0, color=0, alpha=0.0, freeze=False):
    pb, pbs = _pip()
    c = {"alpha": float(alpha), "color": int(color), "defaultAlpha": float(alpha), "defaultColor": int(color),
         "defaultPath": path, "defaultSize": int(size), "effectChainList": _chain(ud3=False), "freeze": bool(freeze),
         "inPoint": 0, "maskIndex": index, "maskSchema": schema, "outPoint": dur, "pipBuf": pb, "pipBufSize": pbs,
         "placeholder": False, "placeholderStatus": 0, "size": int(size), "thisUId": thisuid(), "tlBegin": 0,
         "tlEnd": dur, "type": 9, "userData": [ud_guid64(3, guid())]}
    if tl_id is not None:
        c["userData"].append(ud_int(6, tl_id))
    return c


def _ref_clip(tl_id, dur, is_audio, inner=True, owner=None, main_id=None, begin=0):
    """type-6 clip that plays another timeline (inside the split timeline, or the split's audio on the main one)."""
    pb, pbs = _pip()
    d_s = dur / TICKS
    c = {"effectChainList": _chain(), "inPoint": 0, "isAudio": 1 if is_audio else 0, "pipBuf": pb, "pipBufSize": pbs,
         "placeholder": False, "placeholderStatus": 0, "thisUId": thisuid(), "timelineId": tl_id,
         "tlBegin": begin, "tlEnd": begin + dur, "type": 6}
    if inner:
        c["outPoint"] = int(round((3600 + d_s) * TICKS))
        c["speed"] = {"offset": 0.0, "offsetEnd": round(3600 + d_s, 7), "reverse": False, "speedParam": speed_param(86400.0)}
        c["userData"] = [ud_int(102, 2), ud_int(103, 9 if is_audio else 13), ud_guid64(3, guid()), ud_int(1, 25 if is_audio else 24),
                         ud_int(2, 1)] + ([] if is_audio else [ud_int(125, 0)])
    else:
        c["outPoint"] = dur
        c["speed"] = {"offset": 0.0, "offsetEnd": round(d_s, 7), "reverse": False, "speedParam": speed_param(86400.0)}
        c["userData"] = [ud_int(102, 0), ud_int(6, main_id), ud_int(103, 14), ud_guid(3, owner), ud_int(1, 25), ud_int(2, 1)]
    return c


def _own_audio_clip(project, media, video_clip, tl_id):
    """The media's own sound inside a part timeline (Filmora links it to the video by the same key-3 guid)."""
    def eff(name, enable=None):
        e = {"display": name, "id": f"audio/effect/{name}", "placeholder": False, "placeholderStatus": 0,
             "thisUId": thisuid(), "type": 3, "userData": [ud_guid64(3, guid()), ud(7, b"\x01")]}
        if enable is not None:
            e["enable"] = enable
        return e
    empty = '{"Version": 3,"ParameterType": 0,"keyframeSets": [],"MD5":"d41d8cd98f00b204e9800998ecf8427e"}'
    vg = get_ud(video_clip, 3).rstrip(b"\0").decode()
    return {"audioDuckingframe": {"parameter": empty}, "denoiseV3Strength": 50.0,
            "effectChainList": [{"effectList": [], "name": "Basic"},
                                {"effectList": [eff("change_channel"), eff("volume"), eff("ducking", False), eff("fade")], "name": "BasicFollow"},
                                {"effectList": [], "name": "Effect"}, {"effectList": [], "name": "_wes_hold_effectchain_"}],
            "filename": video_clip["filename"], "inPoint": video_clip["inPoint"], "outPoint": video_clip["outPoint"],
            "placeholder": False, "placeholderStatus": 0, "sourceUuid": video_clip["sourceUuid"],
            "speed": copy.deepcopy(video_clip["speed"]), "streamId": 1, "thisUId": thisuid(),
            "tlBegin": video_clip["tlBegin"], "tlEnd": video_clip["tlEnd"], "type": 2,
            "userData": [ud_int(102, 0), ud_int(6, tl_id), ud_int(103, 4), ud_guid(10, media["id"]), ud_int(2, 0),
                         ud_guid(3, vg), ud_int(1, 2)],
            "volumeKeyframe": {"parameter": empty}}


def template_split(project, template, clips, start, end, border=None, animation=True, first_lane=None, place=True):
    """Filmora's own split-screen template as ONE container clip (type 10) — like dropping it on the timeline and
    filling every part in "Advanced Split Screen Edit".  The template must be downloaded in Filmora.

    template   title ("Split Screen 4"), slug ("Split_Screen_4_ws") or folder name; see installed_templates()
    clips      one per part (paths or {"path", "src_in"}), cycled if fewer
    border     None = the template's own stroke, or {"color": "#FFFFFF", "size": 15, "alpha": 100} (size 0 = none)
    animation  the "Split Screen Animation" switch — ASSUMED to be MaskClip.freeze = not animation (unverified)
    Returns the type-10 clip (its audio partner + inner timelines are written at save time)."""
    t = find_template(template)
    ratio = _ratio_for(project, t["ratios"])
    rd = _ratio_data(t["folder"], ratio)
    schema = f"{t['dir_name']}/{ratio}/Data/{rd['schema']}"
    n = len(rd["parts"])
    srcs = [_src(c) for c in clips] or []
    if not srcs:
        raise ValueError("template_split needs at least one clip")
    dur = project.ticks(end) - project.ticks(start)
    split_id = project.next_tl_id
    part_ids = list(range(split_id + 1, split_id + 1 + n))
    project.next_tl_id = split_id + 1 + n
    W, H = project.W, project.H
    sub = {}
    timelines = []
    for i, part in enumerate(rd["parts"]):
        s = srcs[i % len(srcs)]
        path = s["path"]
        sw, sh = _media_size(project, path)
        # Filmora keeps fit-to-frame (Scale 100) at the template's centre point; raise it only if a picture of
        # another shape would leave a hole in the part's area
        poly = rd["polys"].get(i)
        sc = 100.0
        if poly:
            xs, ys = [p[0] * W for p in poly], [p[1] * H for p in poly]
            fit = min(W / sw, H / sh)
            cx, cy = part["x"] * W, part["y"] * H
            need = max(2 * max(cx - min(xs), max(xs) - cx) / sw, 2 * max(cy - min(ys), max(ys) - cy) / sh)
            sc = max(100.0, 100.0 * need / fit)
        if _is_image(path):
            vc = project.image_clip(path, 0, dur / TICKS, x=part["x"], y=part["y"], scale=sc)
            media = None
        else:
            media = project._video_media(path)
            src_in = float(s.get("src_in", 0.0))
            length = max(dur / TICKS, media["dur"] - src_in)
            vc = project.video_clip(path, 0, length, src_in=src_in, x=part["x"], y=part["y"], scale=sc)
        g = get_ud(vc, 3).rstrip(b"\0").decode()
        mid = project.clip_map.pop(g, None)
        sub[g] = mid
        set_ud(vc, 6, ud_int(6, part_ids[i]))
        tracks = [{"clipList": [vc], "trackType": 1, "uuid": thisuid()},
                  {"clipList": [_mask_clip(dur, schema, i, part["path"], tl_id=part_ids[i], freeze=not animation)],
                   "trackType": 1, "uuid": thisuid()}]
        bus = thisuid()
        if media and media["res"].get("audStreamInfo"):
            tracks.append({"busUuids": [bus], "clipList": [_own_audio_clip(project, media, vc, part_ids[i])],
                           "trackType": 2, "uuid": thisuid()})
        timelines.append(_timeline(project, part_ids[i], 5, tracks, bus))
    st = rd["stroke"] or {"size": 0, "color": 0xFFFFFF}
    b = dict(size=st["size"], color=st["color"], alpha=100.0)
    if border:
        if "color" in border:
            b["color"] = int(str(border["color"]).lstrip("#")[:6], 16) if not isinstance(border["color"], int) else border["color"]
        if "size" in border:
            b["size"] = int(border["size"])
        if "alpha" in border:
            b["alpha"] = float(border["alpha"])
    bus = thisuid()
    tracks = [{"clipList": [_ref_clip(pid, dur, False)], "trackType": 1, "uuid": thisuid()} for pid in part_ids]
    border_clip = _mask_clip(dur, schema, -1, "", size=b["size"], color=b["color"], alpha=b["alpha"], freeze=not animation)
    border_clip["defaultSize"], border_clip["defaultColor"], border_clip["defaultAlpha"] = st["size"], st["color"], 100.0
    tracks.append({"clipList": [border_clip], "trackType": 1, "uuid": thisuid()})
    tracks += [{"busUuids": [bus], "clipList": [_ref_clip(pid, dur, True)], "trackType": 2, "uuid": thisuid()} for pid in part_ids]
    timelines.insert(0, _timeline(project, split_id, 2, tracks, bus))
    project.title_tls.extend(timelines)              # every timeline in title_tls is written by Project.save

    # the container clip on the main timeline
    pb, pbs = _pip()
    sg = guid()
    resinfo = json.dumps({"id": t["id"], "infoType": 7, "is_custom": 0, "smart_resource": 0, "resourceRate": t["resourceRate"],
                          "sale_mode": t["sale_mode"], "source": t["source"], "res_sub_type": 0, "res_type": t["res_type"],
                          "smart_res_relative_path": "", "related_slug": "", "name": t["slug"], "user_string": {}},
                         separators=(",", ":"))
    c = {"effectChainList": _chain(ud7=True, transform_params={}), "inPoint": 0, "isAudio": 0, "isSplitExtended": True,
         "outPoint": dur, "pipBuf": pb, "pipBufSize": pbs, "placeholder": False, "placeholderStatus": 0,
         "splitCount": n, "thisUId": thisuid(), "timelineId": split_id, "tlBegin": project.ticks(start),
         "tlEnd": project.ticks(end), "type": 10,
         "userData": [ud_int(6, project.main_tl_id), ud_int(102, 2), ud_int(103, 0), ud(12, resinfo.encode()), ud_int(1, 11),
                      ud_int(2, 1), ud_str(50, t["title"]), ud_guid64(3, sg), ud(13003, b"\x00")]}
    audio = _ref_clip(split_id, dur, True, inner=False, owner=sg, main_id=project.main_tl_id, begin=project.ticks(start))
    project.clip_map[sg] = t["slug"]
    _hook_save(project)
    project._split_templates.append({"clip": c, "audio": audio, "guid": sg, "slug": t["slug"], "sub": sub})
    if place:
        if first_lane is None:
            first_lane = len(project.layers)
        place_on_lanes(project, [c], first_lane)
    return c


def _hook_save(project):
    """Project.save writes paired audio tracks empty and flat clip maps; after it has written the file, put each split
    template's audio partner on its paired audio track and nest the part clips in extra.json (as Filmora does)."""
    if getattr(project, "_split_templates", None) is not None:
        return
    project._split_templates = []
    orig = project.save

    def save(out_path=None):
        path, end = orig(out_path)
        if project._split_templates:
            _postprocess(path, project._split_templates)
        return path, end
    project.save = save


def _postprocess(path, splits):
    z = zipfile.ZipFile(path)
    files = {n: z.read(n) for n in z.namelist()}
    z.close()
    info = json.loads(files["ProjectFolder/project_info.json"])
    mid = info["timeline_mediaId"]
    tl_name = f"ProjectFolder/Medias/{mid}/timeline.wesproj"
    ex_name = f"ProjectFolder/Medias/{mid}/extra.json"
    doc = json.loads(files[tl_name])
    tracks = doc["timelineInfos"][0]["trackInfos"]
    for s in splits:
        uid = s["clip"]["thisUId"]
        idx = next(i for i, t in enumerate(tracks) if any(c.get("thisUId") == uid for c in t.get("clipList", [])))
        pair = tracks[idx - 1]
        if pair.get("trackType") != 2:
            raise RuntimeError("split template: paired audio track not found")
        pair["clipList"].append(s["audio"])
        pair["clipList"].sort(key=lambda c: c["tlBegin"])
    files[tl_name] = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode()
    ex = json.loads(files[ex_name])
    m = ex.setdefault("mediaClipsMapInfo", {})
    for s in splits:
        m[s["guid"]] = {"mediaId": s["slug"], "subClips": {g: {"mediaId": v, "subClips": {}} for g, v in s["sub"].items()}}
    files[ex_name] = json.dumps(ex, ensure_ascii=False, separators=(",", ":")).encode()
    fx = "ProjectFolder/Anon/AppData/Windows/functionExtraData.json"
    try:
        d = json.loads(files.get(fx, b"{}"))
        d.setdefault("10", "3")                       # Filmora wrote {"10":"3","9":"3"} after a split screen was used
        files[fx] = json.dumps(dict(sorted(d.items())), separators=(",", ":")).encode()
    except Exception:
        pass
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, data in files.items():
            z.writestr(n, data)


# ====================================================================== CLI
def _main(argv):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    if argv[0] == "layouts":
        for k, v in LAYOUTS.items():
            print(f"{k:6} {v}")
    elif argv[0] == "templates":
        print("Downloaded (usable with template_split):")
        for t in installed_templates():
            if "error" in t:
                print(f"  {t['dir_name']}: unreadable ({t['error']})")
            else:
                print(f"  {t['title']:<18} {t['title_ar']:<18} parts={t['parts']}  slug={t['slug']}  ratios={','.join(t['ratios'])}")
        if "--online" in argv:
            on = online_templates()
            print(f"\nKnown online ({len(on)}; download in Filmora: Templates > Split Screen):")
            for t in on:
                print(f"  {'*' if t['installed'] else ' '} {t['title']:<44} {'PAID' if t['paid'] else 'free'}  {'/'.join(t['categories'])}")
    else:
        print(__doc__)


if __name__ == "__main__":
    _main(sys.argv[1:])
