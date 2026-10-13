"""Build an editable Filmora project from a JSON spec (format: skills/filmora-core/spec.md).

    python build_from_spec.py spec.json [--out "G:/Any Folder/Name.wfp"] [--no-register]

Writes the .wfp into the current working directory (the folder the Claude Code conversation was opened in —
any drive works) unless a project_dir preference or --out is given, validates it
(check_wfp.py) and adds it to Filmora's home-screen list with its full path.
"""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from filmora_fx import FxProject          # noqa: E402
from filmora_wfp import set_blend, portrait_cutout   # noqa: E402
from text_measure import measure          # noqa: E402
import filmora_paths                       # noqa: E402
import filmora_speed                       # noqa: E402  speed / ramps / reverse (verified in Filmora 16)
import filmora_mask                        # noqa: E402  shape, text and image masks (verified)
import filmora_text_anim                   # noqa: E402  Filmora's own text animation presets (verified)
import filmora_effect_kf                   # noqa: E402  keyframed effect params + volume (verified)
import filmora_shape                       # noqa: E402  native drawn shapes + self-drawing lines (verified)

SHAPE_OPTS = ("rotation", "scale", "opacity", "fill", "fill_opacity", "stroke", "stroke_width", "stroke_opacity", "cap",
              "join", "line_style", "corner_radius", "sides", "polygon_inner", "points", "inner_ratio", "top_offset",
              "arrow_shaft", "arrow_head", "arrow_begin", "arrow_end", "p1", "p2", "trim", "trim_preset", "trim_dur",
              "trim_delay")


def _pairs(points):
    return [(float(t), float(v)) for t, v in points]


def _apply_effect_kf(effect_clip, effect_name, kfs, ease, fps):
    """kfs = {param: [[t, v], ...]} (seconds from the clip start) on an effect that sits on effect_clip."""
    for param, pts in (kfs or {}).items():
        filmora_effect_kf.keyframe_clip_effect(effect_clip, effect_name, param, _pairs(pts),
                                               interpolation=ease or "linear", fps=fps, clamp=True)

# ---------------- animation presets -> keyframes (seconds from the clip's own start)
# values: scale %, x/y 0..1 (y down), rotation degrees, opacity 0..100


def preset_in(kind, c, d=None):
    s, x, y, o = c.get("scale", 100.0), c.get("x", 0.5), c.get("y", 0.5), c.get("opacity", 100.0)
    table = {
        "fade": lambda d: {"opacity": [(0, 0), (d, o)]},
        "pop": lambda d: {"scale": [(0, s * 0.4), (d * 0.6, s * 1.12), (d, s)], "opacity": [(0, 0), (d * 0.4, o)]},
        "punch": lambda d: {"scale": [(0, s * 1.22), (d, s)]},
        "rise": lambda d: {"y": [(0, y + 0.045), (d * 0.45, y + 0.006), (d, y)], "opacity": [(0, 0), (d * 0.5, o)]},
        "drop": lambda d: {"y": [(0, y - 0.045), (d * 0.45, y - 0.006), (d, y)], "opacity": [(0, 0), (d * 0.5, o)]},
        "slide_right": lambda d: {"x": [(0, x + 0.25), (d * 0.45, x + 0.025), (d, x)], "opacity": [(0, 0), (d * 0.4, o)]},
        "slide_left": lambda d: {"x": [(0, x - 0.25), (d * 0.45, x - 0.025), (d, x)], "opacity": [(0, 0), (d * 0.4, o)]},
        "zoom": lambda d: {"scale": [(0, s * 0.6), (d, s)], "opacity": [(0, 0), (d * 0.5, o)]},
        "spin": lambda d: {"rotation": [(0, -90), (d, 0)], "scale": [(0, s * 0.3), (d, s)], "opacity": [(0, 0), (d * 0.4, o)]},
    }
    defaults = {"fade": 0.4, "pop": 0.45, "punch": 0.2, "rise": 0.5, "drop": 0.5, "slide_right": 0.5, "slide_left": 0.5, "zoom": 0.6, "spin": 0.5}
    if kind not in table:
        raise ValueError(f"unknown in-animation '{kind}' ({', '.join(table)})")
    return table[kind](d or defaults[kind])


def preset_out(kind, c, dur, d=None):
    s, o = c.get("scale", 100.0), c.get("opacity", 100.0)
    d = d or 0.35
    if kind == "fade":
        return {"opacity": [(dur - d, o), (dur, 0)]}
    if kind == "shrink":
        return {"opacity": [(dur - d, o), (dur, 0)], "scale": [(dur - d, s), (dur, s * 0.9)]}
    if kind == "grow":
        return {"opacity": [(dur - d, o), (dur, 0)], "scale": [(dur - d, s), (dur, s * 1.25)]}
    raise ValueError(f"unknown out-animation '{kind}' (fade, shrink, grow)")


def preset_loop(kind, c, dur):
    s = c.get("scale", 100.0)
    if kind in ("pulse", "beat_pulse"):
        period = c.get("pulse_period", 1.2)
        amp = c.get("pulse_amount", 0.04 if kind == "pulse" else 0.08)
        pts, t = [], 0.0 if kind == "beat_pulse" else 0.6
        while t <= dur - 0.05:
            pts += [(t, s * (1 + amp)), (min(dur, t + 0.16), s)] if kind == "beat_pulse" else [(t, s * (1 + amp if len(pts) % 2 else 1 - amp))]
            t += period if kind == "beat_pulse" else period / 2
        return {"scale": pts}
    if kind == "spin":
        r0 = c.get("rotation", 0.0)
        return {"rotation": [(0, r0), (dur, r0 + c.get("spin_degrees", 90))]}
    if kind == "push":
        return {"scale": [(0, s), (dur, s * c.get("push_amount", 1.1))]}
    if kind == "shake":
        a = c.get("shake_degrees", 2.5)
        return {"rotation": [(0, -a), (0.06, a), (0.12, -a * 0.6), (0.2, 0)]}
    raise ValueError(f"unknown loop '{kind}' (pulse, beat_pulse, spin, push, shake)")


def merged_keyframes(c, fps=30):
    dur = c["end"] - c["start"]
    parts = [{k: [tuple(p) for p in v] for k, v in c.get("keyframes", {}).items()}]
    if c.get("in"):
        parts.append(preset_in(c["in"], c, c.get("in_duration")))
    if c.get("loop"):
        parts.append(preset_loop(c["loop"], c, dur))
    if c.get("out"):
        parts.append(preset_out(c["out"], c, dur, c.get("out_duration")))
    kf = {}
    for part in parts:
        for prop, pts in part.items():
            d = dict(kf.get(prop, []))
            d.update({round(max(0.0, min(dur, t)), 4): v for t, v in pts})
            kf[prop] = sorted(d.items())
    return {prop: eased(pts, c.get("ease", "out"), fps) for prop, pts in kf.items()}


EASE = {  # u in 0..1 -> progress; Filmora interpolates linearly, so curves are sampled into dense keyframes
    "linear": lambda u: u,
    "in": lambda u: u ** 3,
    "out": lambda u: 1 - (1 - u) ** 3,
    "inout": lambda u: 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2,
    "back": lambda u: 1 + 2.70158 * (u - 1) ** 3 + 1.70158 * (u - 1) ** 2,     # out with a small overshoot
}


NATIVE_EASES = ("out", "in", "inout")   # written as Filmora's own curve keys (2 editable points per move)


def eased(pts, ease="out", fps=30):
    """out / in / inout -> the same points tagged with the ease (native Filmora curves, see filmora_wfp.kf_param_curve);
    other eases (back) are densified along the curve (a point every 2 frames)."""
    if ease == "linear" or len(pts) < 2:
        return pts
    if ease in NATIVE_EASES:
        return [(t, v, ease) for t, v in pts]
    f = EASE.get(ease, EASE["out"])
    out = [pts[0]]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        n = max(1, int(round((t1 - t0) * fps / 2)))
        if v0 != v1:
            out += [(round(t0 + (t1 - t0) * i / n, 4), v0 + (v1 - v0) * f(i / n)) for i in range(1, n)]
        out.append((t1, v1))
    return out


# Role-based text sizes, calibrated on 1080-wide vertical projects in Readex Pro Bold / IBM Plex Sans Arabic SemiBold /
# Montserrat SemiBold. Any other font is scaled so the same reference line takes the same width, so a wide/big-looking
# font automatically gets a smaller number. The reference lines only measure width — don't change them without
# re-measuring the widths below. Headline/title are a starting point that follows the text's length like a designer
# would: one or two strong words big (~70), a full sentence smaller (~48) — see LENGTH_RANGE.
ROLE_REF = {"ar": "الذكاء الاصطناعي يساعد الدماغ", "en": "KADR STUDIO NEWS"}
ROLES = {  # role: (size in the calibration font, reference width of that font for the script in use)
    "hit": {"ar": (110, 13.897), "en": (96, 10.769)}, "headline": {"ar": (70, 13.897), "en": (60, 10.769)},
    "title": {"ar": (56, 13.897), "en": (48, 10.769)}, "caption": {"ar": (40, 12.183), "en": (34, 10.769)},
    "label": {"ar": (30, 12.183), "en": (24, 10.769)}, "sub": {"ar": (26, 12.183), "en": (20, 10.769)},
}


def script(text):
    return "ar" if any("؀" <= ch <= "ۿ" for ch in text) else "en"


# headline/title: full size up to SHORT em of text (in the calibration font), shrinking to `long_factor` x at LONG em
LENGTH_RANGE = {"headline": (0.69, 5.0, 12.0), "title": (0.75, 5.0, 12.0)}   # (long_factor, SHORT, LONG)


def role_size(c, ref_width, W, H, text_width=None):
    """Font size for a text role: same visual footprint whatever the font; landscape frames get proportionally smaller
    text (sizes follow the short side). Headlines/titles also follow their length (short = big, a sentence = smaller).
    "size_scale" fine-tunes (e.g. 1.1); an explicit "size" in the spec always wins."""
    base, calib = ROLES[c["role"]][script(c["text"])]
    norm = calib / max(ref_width, 0.1)                   # this font -> calibration font
    if c["role"] in LENGTH_RANGE and text_width:
        long_f, short_em, long_em = LENGTH_RANGE[c["role"]]
        t = min(1.0, max(0.0, (text_width / norm - short_em) / (long_em - short_em)))
        base *= 1 - (1 - long_f) * t
    return round(base * norm * min(W, H) / W * c.get("size_scale", 1.0), 1)


_LH = {}


def block_height(c, W):
    """Visible height (px) of a text block: first line ~1.25 em + the font's own line pitch for every extra line
    (Filmora: 1 em = 1.5 x size x W/1920; the pitch comes from the font file - Readex Pro 1.76 em, some display fonts 2.0 em)."""
    em = 1.5 * c.get("size", 60) * W / 1920
    lines = c["text"].count("\n") + 1
    if lines == 1:
        return em * 1.25
    font = c.get("font", "Arial")
    if font not in _LH:
        from text_measure import line_height
        _LH[font] = line_height(font)
    return em * (1.25 + (lines - 1) * _LH[font])


def stack_texts(texts, W, H):
    """A text with "below": "<id of another text>" sits under that text's real block (+ "gap" px, default 0.35 em of the
    upper text), so a 2-line headline never runs into its subline."""
    by_id = {c["id"]: c for c in texts if c.get("id")}
    for c in texts:
        up = by_id.get(c.get("below"))
        if not up:
            continue
        gap = c.get("gap", 0.35 * 1.5 * up.get("size", 60) * W / 1920)
        c["y"] = round(up.get("y", 0.5) + (block_height(up, W) / 2 + gap + block_height(c, W) / 2) / H, 4)


def _luminance(rgb):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def _source_frame(path, t):
    """RGBA picture of a media file at source second t (image files: the image itself), native size."""
    import io
    from PIL import Image
    if path.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
        return Image.open(path).convert("RGBA")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", path, "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return Image.open(io.BytesIO(raw)).convert("RGBA") if raw else None


def _composite(layers, tm, W, H, cache):
    """What the frame looks like at timeline second tm: every visual layer fitted into the frame like Filmora does at
    scale 100 (letterboxed), then scaled and moved by its own scale/x/y, stacked by z over black."""
    from PIL import Image
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    for v in sorted(layers, key=lambda v: v.get("z", 0)):
        src_t = v.get("src_in", 0.0) + (tm - v["start"]) * float(v.get("speed", 1) if not isinstance(v.get("speed"), dict) else 1)
        key = (v["path"], round(src_t, 1))
        if key not in cache:
            cache[key] = _source_frame(v["path"], src_t)
        img = cache[key]
        if img is None:
            continue
        f = min(W / img.width, H / img.height) * v.get("scale", 100.0) / 100
        w, h = max(1, round(img.width * f)), max(1, round(img.height * f))
        layer = img.resize((w, h))
        canvas.paste(layer, (round(v.get("x", 0.5) * W - w / 2), round(v.get("y", 0.5) * H - h / 2)), layer)
    return canvas.convert("RGB")


def _contrast(fg, bg):
    l1, l2 = _luminance(fg), _luminance(bg)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def fix_contrast(clips, texts, W, H, need=3.0, text_w=None):
    """Look at what is really under each text (all video/image layers below it, fitted and placed like Filmora shows
    them, at the text's middle moment and box) and, if the colour reaches less than `need` (3:1 = large text), switch
    to whichever of white / near-black reads better there."""
    import numpy as np
    visuals = [c for c in clips if c["type"] in ("video", "image")]
    cache, checked, changed = {}, 0, 0
    for c in texts:
        if c.get("contrast") is False:
            continue
        tm = (c["start"] + c["end"]) / 2
        under = [v for v in visuals if v["start"] <= tm < v["end"] and v.get("z", 0) <= c.get("z", 0)]
        if not under:
            continue
        img = _composite(under, tm, W, H, cache)
        bh = block_height(c, W)
        half_w = (text_w or {}).get(id(c), 0) * 1.5 * c.get("size", 60) * W / 1920 / 2 or W * 0.35
        cx, cy = c.get("x", 0.5) * W, c.get("y", 0.5) * H
        box = (int(max(0, cx - half_w)), int(max(0, cy - bh / 2)), int(min(W, cx + half_w)), int(min(H, cy + bh / 2)))
        if box[3] <= box[1] or box[2] <= box[0]:
            continue
        bg = tuple(np.asarray(img.crop(box), dtype=np.float32).reshape(-1, 3).mean(0))
        col = c.get("color", "#FFFFFF").lstrip("#")
        fg = tuple(int(col[i:i + 2], 16) for i in (0, 2, 4))
        checked += 1
        ratio = _contrast(fg, bg)
        if ratio < need:
            new = max(("#FFFFFF", "#111111"), key=lambda h: _contrast(tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)), bg))
            print(f"note: text '{c['text'][:18]}' colour #{col} -> {new} (contrast {ratio:.1f}:1 on what is underneath)")
            c["color"] = new
            changed += 1
    if checked:
        print(f"contrast check: {checked} text(s) checked against the picture underneath, {changed} recoloured")



def expand_splits(spec):
    """"type": "split" -> one real video clip per part on its own track, cut by a rect mask (no container clip), plus
    optional divider lines (shapes) and a background colour. Layouts: 2v 2h 3v 3h 1+2 2x2 diag2."""
    import filmora_split
    from motion_track import picture_size
    W, H = spec.get("width", 1080), spec.get("height", 1920)
    out = []
    for n, c in enumerate(spec["clips"]):
        if c.get("type") != "split":
            out.append(c)
            continue
        srcs = c["clips"]
        info = [dict(zip(("w", "h"), picture_size(s["path"])), focus=s.get("focus", (0.5, 0.5)), zoom=s.get("zoom", 1.0))
                for s in srcs]
        parts = filmora_split.plan_split(W, H, c.get("layout", "2v"), info, gap=c.get("gap", 0), margin=c.get("margin", 0),
                                         ratio=c.get("ratio", 0.6), big=c.get("big", "auto"), radius=c.get("radius", 0))
        z0 = c.get("z", 0)
        if c.get("background"):
            out.append({"type": "shape", "kind": "rect", "x": 0.5, "y": 0.5, "w": 1.0, "h": 1.0, "fill": c["background"],
                        "stroke": None, "start": c["start"], "end": c["end"], "z": z0, "track": f"split{n}_bg"})
        for k, part in enumerate(parts):
            s = srcs[k % len(srcs)]
            v = {"type": "video", "path": s["path"], "src_in": s.get("src_in", 0.0), "start": c["start"], "end": c["end"],
                 "x": part["x"], "y": part["y"], "scale": part["scale"], "mask": dict(part["mask"]),
                 "z": z0 + 0.1 + k * 0.01, "track": f"split{n}_{k}"}
            for key in ("speed", "filters", "blend", "cutout"):
                if key in s:
                    v[key] = s[key]
            out.append(v)
        d = c.get("divider")
        if d:
            d = d if isinstance(d, dict) else {"color": d}
            for j, ((x0, y0), (x1, y1)) in enumerate(filmora_split.divider_segments(W, H, c.get("layout", "2v"),
                                                                                    c.get("ratio", 0.6), c.get("big", "auto"))):
                out.append({"type": "shape", "kind": "line", "p1": [x0 / W, y0 / H], "p2": [x1 / W, y1 / H],
                            "stroke": d.get("color", "#FFFFFF"), "stroke_width": d.get("width", 6), "fill": None,
                            "start": c["start"], "end": c["end"], "z": z0 + 0.5, "track": f"split{n}_div{j}"})
    spec["clips"] = out


def apply_follow(spec):
    """"follow": {"video": "<id of a video clip>", "box": [cx, cy, w, h]} on a text/image/shape: track that object (box =
    fractions of the video picture at the element's start) and move the element with it, like Filmora's Motion Tracking
    + Link Element. Returns [(element, video, info)] so build() can also write Filmora's own tracking data."""
    import motion_track
    W, H, fps = spec.get("width", 1080), spec.get("height", 1920), spec.get("fps", 30)
    by_id = {c["id"]: c for c in spec["clips"] if c.get("id")}
    links = []
    for c in spec["clips"]:
        f = c.get("follow")
        if not f:
            continue
        v = by_id[f["video"]]
        src = v.get("src_in", 0.0) + (c["start"] - v["start"])
        pts, info = motion_track.track_points(v["path"], src, c["end"] - c["start"], tuple(f["box"]), fps=fps,
                                              return_info=True, quiet=True)
        pl = motion_track.placement(v["path"], W, H, v.get("scale", 100.0), v.get("x", 0.5), v.get("y", 0.5))
        kf = motion_track.to_frame_keyframes(pts, pl, (c.get("x", 0.5), c.get("y", 0.5)), simplify=f.get("simplify", 0.0005))
        c.setdefault("keyframes", {}).update(kf)
        c["ease"] = "linear"
        if info.get("lost"):
            print(f"note: tracking lost the object on {len(info['lost'])} frame(s) (bridged)")
        links.append((c, v, info, motion_track.link_offset(pts, pl, (c.get("x", 0.5), c.get("y", 0.5)))))
    return links

SAFE = 0.03     # keep every text this far (fraction of the frame) from the top/bottom edges
SAFE_X = 0.07   # ...and from the side edges (Filmora can draw a few % wider than measured; reels crop the sides)
WIDE = 0.78     # a 3+ word line wider than this share of the frame is broken into two balanced lines


def fit_text_size(c, em_width, W, H, kf, quiet=False):
    """Shrink a text's font size until its box stays inside the frame at every keyframe (scale and position).
    Filmora renders glyphs at 1 em = 1.5 * size * W / 1920 px (title box height is twice that)."""
    size = float(c.get("size", 60))
    lines = c["text"].count("\n") + 1
    max_scale = max([q[1] for q in kf.get("scale", [])] + [c.get("scale", 100.0)]) / 100
    xs = [q[1] for q in kf.get("x", [])] or [c.get("x", 0.5)]
    ys = [q[1] for q in kf.get("y", [])] or [c.get("y", 0.5)]
    em = 1.5 * size * W / 1920
    half_w = em_width * em * max_scale / 2 / W                     # fractions of the frame
    half_h = 1.3 * em * (1 + (lines - 1) * 1.15) * max_scale / 2 / H     # visible line ~1.3 em
    room_w = min(min(x, 1 - x) for x in xs) - SAFE_X                # centre to the nearest side edge
    room_h = min(min(y, 1 - y) for y in ys) - SAFE
    f = min(1.0, room_w / half_w if half_w > 0 else 1.0, room_h / half_h if half_h > 0 else 1.0)
    if f < 1.0:
        new = max(8.0, round(size * max(f, 0.05), 1))
        if quiet:
            return new
        print(f"note: text '{c['text'][:20]}' size {size:g} -> {new:g} so it stays inside the frame"
              + ("" if room_w > 0 and room_h > 0 else " (its position is at the very edge - move it inward)"))
        return new
    return size


def build(spec, out=None, register=True):
    if any(c.get("type") == "split" for c in spec["clips"]):
        expand_splits(spec)
    links = apply_follow(spec) if any(c.get("follow") for c in spec["clips"]) else []
    p = FxProject(spec["name"], spec.get("width", 1080), spec.get("height", 1920), spec.get("fps", 30))
    clips = spec["clips"]
    texts = [c for c in clips if c["type"] == "text"]
    lines = sorted({(ln, c.get("font", "Arial")) for c in texts for ln in c["text"].split("\n")})
    refs = sorted({(ROLE_REF[script(c["text"])], c.get("font", "Arial")) for c in texts if c.get("role") and "size" not in c})
    measured = measure(lines + refs) if lines else []
    widths = dict(zip(lines + refs, measured))
    for c in texts:                                   # role -> size, normalised to how big this font really draws
        if c.get("role") and "size" not in c:
            font = c.get("font", "Arial")
            c["size"] = role_size(c, widths[(ROLE_REF[script(c["text"])], font)], p.W, p.H,
                                  max(widths[(ln, font)] for ln in c["text"].split("\n")))
    text_w = {}                                       # too wide -> two balanced lines, then shrink to the safe area
    for c in texts:                                   # (before stacking, so a subline goes under the real block)
        font = c.get("font", "Arial")
        kf = merged_keyframes(c, p.fps)
        w = max(widths[(ln, font)] for ln in c["text"].split("\n"))
        words = c["text"].split()
        one = fit_text_size(c, w, p.W, p.H, kf, quiet=True)
        fill = w * 1.5 * one / 1920                                   # share of the frame width the line takes
        if "\n" not in c["text"] and len(words) >= 3 and (one < 0.8 * c.get("size", 60) or fill > WIDE):
            cut = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
            two = " ".join(words[:cut]) + "\n" + " ".join(words[cut:])
            new = [(ln, font) for ln in two.split("\n") if (ln, font) not in widths]
            widths.update(zip(new, measure(new)) if new else [])
            w2 = max(widths[(ln, font)] for ln in two.split("\n"))
            if fit_text_size(dict(c, text=two), w2, p.W, p.H, kf, quiet=True) >= one:   # unless it ends up smaller
                grow = block_height(dict(c, text=two), p.W) - block_height(c, p.W)
                c["text"], w = two, w2
                c["y"] = round(c.get("y", 0.5) + grow / 2 / p.H, 4)        # grow downward: keep the top edge in place
                print(f"note: text '{words[0]} ...' split into two lines to fit the frame")
        c["size"] = fit_text_size(c, w, p.W, p.H, kf)
        text_w[id(c)] = w
    sizes = sorted({(c.get("role", "-"), c.get("font", "Arial"), c["size"]) for c in texts})
    if sizes:
        print("text sizes: " + ", ".join(f"{r} {f} {s:g}" for r, f, s in sizes))
    stack_texts(texts, p.W, p.H)                      # "below": put a subline under its headline, whatever its line count
    if spec.get("contrast", True):
        fix_contrast(clips, texts, p.W, p.H, text_w=text_w)   # text colour readable on what is really underneath it

    made = []
    for c in clips:
        if c["type"] == "audio":
            continue
        kf = merged_keyframes(c, p.fps) if c["type"] != "effect" else {}
        common = dict(x=c.get("x", 0.5), y=c.get("y", 0.5), scale=c.get("scale", 100.0), opacity=c.get("opacity", 100.0),
                      kf_scale=kf.get("scale"), kf_x=kf.get("x"), kf_y=kf.get("y"), kf_rot=kf.get("rotation"), kf_opacity=kf.get("opacity"))
        if c["type"] == "image":
            obj = p.image_clip(c["path"], c["start"], c["end"], rot=c.get("rotation", 0.0), kf_scale_x=kf.get("scale_x"), **common)
        elif c["type"] == "video":
            obj = p.video_clip(c["path"], c["start"], c["end"], src_in=c.get("src_in", 0.0), rot=c.get("rotation", 0.0), **common)
            sp = c.get("speed")
            if sp is not None or c.get("reverse") or c.get("frame_interp"):
                kw = dict(sp) if isinstance(sp, dict) else {"speed": float(sp if sp is not None else 1.0)}
                if "curve" in kw:
                    kw["curve"] = _pairs(kw["curve"])
                filmora_speed.apply_speed(obj, c.get("src_in", 0.0), total=filmora_speed.media_total(p, c["path"]),
                                          duration=c["end"] - c["start"], reverse=bool(c.get("reverse")),
                                          frame_interp=c.get("frame_interp"), **kw)
        elif c["type"] == "text":
            font, w = c.get("font", "Arial"), text_w[id(c)]
            size = fit_text_size(c, w, p.W, p.H, kf)
            obj = p.title_clip(c["text"].replace("\n", "\r"), c["start"], c["end"], font=font, font_size=size,
                               color=int(c.get("color", "#FFFFFF").lstrip("#")[:6], 16), text_width=w, lines=c["text"].count("\n") + 1, **common)
            if c.get("anim_in") or c.get("anim_out") or c.get("anim_loop"):    # Filmora's own text animation presets
                filmora_text_anim.apply_text_animation(
                    obj, filmora_text_anim.inner_clip_of(p, obj), in_=c.get("anim_in"), out=c.get("anim_out"),
                    loop=c.get("anim_loop"), in_dur=c.get("anim_in_dur"), out_dur=c.get("anim_out_dur"),
                    loop_dur=c.get("anim_loop_dur"))
        elif c["type"] == "shape":                      # rect, ellipse, triangle, polygon, star, arrow, line
            obj = filmora_shape.shape_clip(p, c.get("kind", "rect"), c["start"], c["end"], x=c.get("x", 0.5),
                                           y=c.get("y", 0.5), w=c.get("w", 0.3), h=c.get("h"),
                                           kf_x=kf.get("x"), kf_y=kf.get("y"), kf_rot=kf.get("rotation"),
                                           kf_scale=kf.get("scale"), kf_opacity=kf.get("opacity"),
                                           **{k: c[k] for k in SHAPE_OPTS if k in c})
        elif c["type"] == "effect":
            obj = p.fx(c["name"], c["start"], c["end"], params=c.get("params"))
            _apply_effect_kf(obj, c["name"], c.get("keyframes"), c.get("ease"), p.fps)
        else:
            raise ValueError(f"unknown clip type {c['type']}")
        for f in c.get("filters", []):                  # "Name" or {"name", "params", "keyframes", "ease"}
            f = {"name": f} if isinstance(f, str) else f
            p.filter(obj, f["name"], f.get("params"))
            _apply_effect_kf(obj, f["name"], f.get("keyframes"), f.get("ease"), p.fps)
        if c.get("cutout") and c["type"] in ("image", "video"):   # AI Portrait Cutout (computed by Filmora, no credits)
            cut = c["cutout"] if isinstance(c["cutout"], dict) else {}
            portrait_cutout(obj, feather=cut.get("feather", 0.0), edge_thickness=cut.get("edge", 0.0))
        if c.get("blend") and c["type"] in ("image", "video", "text", "shape"):
            set_blend(obj, c["blend"])                  # Screen, Multiply, Overlay, Soft Light, ... (18 modes)
        if c.get("masks") and c["type"] in ("image", "video"):   # several masks: add / subtract / intersect
            ms = []
            for m in c["masks"]:
                m = dict(m)
                if m.get("keyframes"):
                    m["keyframes"] = {k: _pairs(v) for k, v in m["keyframes"].items()}
                ms.append(m)
            filmora_mask.add_masks(obj, ms, project=p)
        if c.get("mask") and c["type"] in ("image", "video"):
            m = dict(c["mask"])
            if m.get("keyframes"):
                m["keyframes"] = {k: _pairs(v) for k, v in m["keyframes"].items()}
            filmora_mask.add_mask(obj, m.pop("shape", "ellipse"), project=p, **m)
        made.append((c, obj))

    if links:                                         # Filmora's own tracking data + "Link Element" (panel shows it)
        import motion_track
        objs = {id(c): o for c, o in made}
        for el, v, info, off in links:
            if id(v) in objs and id(el) in objs:
                motion_track.attach_tracking(objs[id(v)], info, info["src_in"], info["duration"], info["fps"])
                motion_track.link_element(objs[id(el)], objs[id(v)], off)
    # named tracks keep their clips together (needed for transitions); everything else is packed automatically
    named, free = {}, []
    for c, obj in made:
        (named.setdefault(c["track"], []) if c.get("track") else free).append((c, obj))
    lanes = []
    for name, items in sorted(named.items(), key=lambda kv: min(c.get("z", 0) for c, _ in kv[1])):
        items.sort(key=lambda m: m[1]["tlBegin"])
        # planned transition length on each cut; a clip must hold half of its incoming + outgoing transition plus a
        # frame, otherwise Filmora rejects the overlap (log: ErrInvalidTransitionTime) -> shrink both proportionally
        tr = []
        for (c, obj), (_, nxt) in zip(items, items[1:] + [(None, None)]):
            t = c.get("transition_out")
            ok = t and nxt is not None and nxt["tlBegin"] == obj["tlEnd"]
            tr.append(((t["name"] if isinstance(t, dict) else t), (t.get("duration", 0.4) if isinstance(t, dict) else 0.4)) if ok else None)
        frame = 1.0 / p.fps
        for _ in range(3):
            for k, (c, obj) in enumerate(items):
                avail = (obj["tlEnd"] - obj["tlBegin"]) / 1e7 - frame
                prev, cur = (tr[k - 1] if k else None), tr[k]
                need = (prev[1] if prev else 0) / 2 + (cur[1] if cur else 0) / 2
                if need > avail > 0:
                    f = avail / need
                    if prev:
                        tr[k - 1] = (prev[0], prev[1] * f)
                    if cur:
                        tr[k] = (cur[0], cur[1] * f)
        for (c, obj), t in zip(items, tr):
            if t and t[1] >= 2 * frame:
                p.transition(obj, t[0], round(t[1], 4))
            elif t:
                print(f"note: transition '{t[0]}' at {obj['tlEnd'] / 1e7:.2f}s dropped (clips too short)")
        lanes.append(([c for c, _ in items], [o for _, o in items], min(c.get("z", 0) for c, _ in items)))
    order = sorted(free, key=lambda m: (m[0].get("z", 0), m[0]["start"]))
    packed, lane_of = [], {}
    for i, (c, obj) in enumerate(order):
        a0, a1 = obj["tlBegin"], obj["tlEnd"]
        floor = max([lane_of[j] + 1 for j in range(i) if order[j][1]["tlBegin"] < a1 and a0 < order[j][1]["tlEnd"]] or [0])
        L = floor
        while L < len(packed) and any(o["tlBegin"] < a1 and a0 < o["tlEnd"] for _, o in packed[L]):
            L += 1
        if L == len(packed):
            packed.append([])
        packed[L].append((c, obj))
        lane_of[i] = L
    for lane in packed:
        lanes.append(([c for c, _ in lane], [o for _, o in lane], min(c.get("z", 0) for c, _ in lane)))
    for _, objs, _z in sorted(lanes, key=lambda l: l[2]):
        p.add_lane(sorted(objs, key=lambda o: o["tlBegin"]))

    sub = spec.get("subtitles")                       # Filmora's native subtitle track (editable, exports SRT)
    if sub:
        import filmora_subtitle
        cues = sub.get("cues")
        if sub.get("srt"):
            cues = filmora_subtitle.from_srt(sub["srt"])
        words = [tuple(w) for w in sub["words"]] if sub.get("words") else None
        if not sub.get("font") or not sub.get("size"):
            raise ValueError("subtitles need the user's chosen font and a size")
        kw = {k: sub[k] for k in ("color", "y", "x", "max_width", "align", "box") if k in sub}
        if sub.get("dynamic"):                        # spoken-word highlight like Filmora's Dynamic Caption
            kw["dynamic"], kw["words"] = sub["dynamic"], words
        filmora_subtitle.subtitle_track(p, [tuple(c) for c in cues] if cues else None, font=sub["font"], size=sub["size"],
                                        **kw)
    alanes = []
    for c in sorted((c for c in clips if c["type"] == "audio"), key=lambda a: a["start"]):
        obj = p.audio_clip(c["path"], c["start"], dur=c.get("duration"), gain_db=c.get("gain_db", -10.0), fade_out=c.get("fade_out", 0.0),
                           src_in=c.get("src_in", 0.0))
        if c.get("volume_kf"):                          # [[seconds_from_clip_start, dB], ...]
            filmora_effect_kf.set_volume_keyframes(obj, _pairs(c["volume_kf"]), interpolation=c.get("ease", "linear"), fps=p.fps)
        for lane in alanes:
            if lane[-1]["tlEnd"] <= obj["tlBegin"]:
                lane.append(obj)
                break
        else:
            alanes.append([obj])
    for lane in alanes:
        p.add_audio_lane(lane)

    # Default: save next to the conversation — the folder Claude Code was opened in (current working directory).
    # A saved preference (filmora_paths.py set project_dir ...) wins; --out wins over both.
    if not out:
        cfg_dir = filmora_paths._config().get("project_dir")
        out = os.path.join(cfg_dir or os.getcwd(), spec["name"] + ".wfp")
    plugin_root = os.path.dirname(HERE)
    if os.path.normcase(os.path.abspath(out)).startswith(os.path.normcase(plugin_root) + os.sep):
        print(f"WARNING: saving inside the plugin folder ({plugin_root}) — run from the project folder or pass --out")
    path, end = p.save(out)
    subprocess.run([sys.executable, os.path.join(HERE, "check_wfp.py"), path], check=True)
    if register:
        subprocess.run([sys.executable, os.path.join(HERE, "register_project.py"), path, str(round(end / 1e7 * p.fps))], check=True)
    n = lambda t: sum(1 for c in clips if c["type"] == t)
    print(f"built {path}  {end / 1e7:.2f}s  video tracks={len(lanes)} audio tracks={len(alanes)}  "
          f"video={n('video')} images={n('image')} texts={n('text')} shapes={n('shape')} effects={n('effect')} "
          f"audio={n('audio')}" + (f"  subtitles={len(sub.get('cues') or sub.get('words') or []) or 'srt'}" if sub else ""))
    return path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out")
    ap.add_argument("--no-register", action="store_true")
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    out = a.out
    plugin_root = os.path.normcase(os.path.dirname(HERE)) + os.sep
    if not out and not filmora_paths._config().get("project_dir") and \
            os.path.normcase(os.getcwd() + os.sep).startswith(plugin_root):
        # run from inside the plugin folder by mistake -> save next to the spec instead of inside the plugin
        out = os.path.join(os.path.dirname(os.path.abspath(a.spec)), spec["name"] + ".wfp")
    build(spec, out, not a.no_register)
