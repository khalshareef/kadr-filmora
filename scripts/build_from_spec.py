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
from text_measure import measure          # noqa: E402
import filmora_paths                       # noqa: E402

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


def eased(pts, ease="out", fps=30):
    """Densify each keyframe segment along an easing curve (a point every 2 frames)."""
    if ease == "linear" or len(pts) < 2:
        return pts
    f = EASE.get(ease, EASE["out"])
    out = [pts[0]]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        n = max(1, int(round((t1 - t0) * fps / 2)))
        if v0 != v1:
            out += [(round(t0 + (t1 - t0) * i / n, 4), v0 + (v1 - v0) * f(i / n)) for i in range(1, n)]
        out.append((t1, v1))
    return out


# Role-based text sizes. Calibrated on a 1080-wide vertical project the user approved (headline Readex Pro Bold 74,
# caption IBM Plex Sans Arabic SemiBold 40, Latin subline Montserrat SemiBold 20). Any other font is scaled so the same
# reference line takes the same width, so a wide/big-looking font automatically gets a smaller number.
ROLE_REF = {"ar": "الذكاء الاصطناعي يساعد الدماغ", "en": "FALCON ASR NEWS"}
ROLES = {  # role: (size in the calibration font, reference width of that font for the script in use)
    "hit": {"ar": (110, 13.897), "en": (96, 10.195)}, "headline": {"ar": (74, 13.897), "en": (64, 10.195)},
    "title": {"ar": (60, 13.897), "en": (52, 10.195)}, "caption": {"ar": (40, 12.183), "en": (34, 10.195)},
    "label": {"ar": (30, 12.183), "en": (24, 10.195)}, "sub": {"ar": (26, 12.183), "en": (20, 10.195)},
}


def script(text):
    return "ar" if any("؀" <= ch <= "ۿ" for ch in text) else "en"


def role_size(c, ref_width, W, H):
    """Font size for a text role: same visual footprint whatever the font; landscape frames get proportionally smaller
    text (sizes follow the short side). "size_scale" fine-tunes (e.g. 1.1)."""
    base, calib = ROLES[c["role"]][script(c["text"])]
    return round(base * calib / max(ref_width, 0.1) * min(W, H) / W * c.get("size_scale", 1.0), 1)


def block_height(c, W):
    """Visible height (px) of a text block: lines x line pitch (Filmora: 1 em = 1.5 x size x W/1920)."""
    em = 1.5 * c.get("size", 60) * W / 1920
    lines = c["text"].count("\n") + 1
    return em * (1.25 + (lines - 1) * 1.55)


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


def _frame(path, t, W, H):
    """RGB image of a media file at second t, scaled to the project frame (image files: the image)."""
    import io
    from PIL import Image
    if path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return Image.open(path).convert("RGB").resize((W, H))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", path, "-frames:v", "1", "-vf", f"scale={W}:{H}",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return Image.open(io.BytesIO(raw)).convert("RGB") if raw else None


def fix_contrast(clips, texts, W, H, need=3.0):
    """Sample what is under each text (the topmost video/image clip below it, at the text's middle moment and position)
    and switch the colour to near-white or near-black if the contrast ratio is below `need` (3:1 = large text)."""
    visuals = [c for c in clips if c["type"] in ("video", "image")]
    cache = {}
    for c in texts:
        if c.get("contrast") is False:
            continue
        tm = (c["start"] + c["end"]) / 2
        under = [v for v in visuals if v["start"] <= tm < v["end"] and v.get("z", 0) <= c.get("z", 0)]
        if not under:
            continue
        v = max(under, key=lambda v: v.get("z", 0))
        src_t = v.get("src_in", 0.0) + (tm - v["start"])
        key = (v["path"], round(src_t, 1))
        if key not in cache:
            cache[key] = _frame(v["path"], src_t, W, H)
        img = cache[key]
        if img is None:
            continue
        bh = block_height(c, W)
        box = (int(W * 0.15), int(max(0, c.get("y", 0.5) * H - bh / 2)), int(W * 0.85), int(min(H, c.get("y", 0.5) * H + bh / 2)))
        if box[3] <= box[1]:
            continue
        px = img.crop(box).resize((32, 8)).getdata()
        bg = tuple(sum(p[i] for p in px) / len(px) for i in range(3))
        col = c.get("color", "#FFFFFF").lstrip("#")
        fg = tuple(int(col[i:i + 2], 16) for i in (0, 2, 4))
        l1, l2 = _luminance(fg), _luminance(bg)
        ratio = (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)
        if ratio < need:
            new = "#FFFFFF" if _luminance(bg) < 0.35 else "#111111"
            print(f"note: text '{c['text'][:18]}' colour #{col} -> {new} (contrast {ratio:.1f}:1 on what is underneath)")
            c["color"] = new


SAFE = 0.03   # keep every text this far (fraction of the frame) from the edges


def fit_text_size(c, em_width, W, H, kf, quiet=False):
    """Shrink a text's font size until its box stays inside the frame at every keyframe (scale and position).
    Filmora renders glyphs at 1 em = 1.5 * size * W / 1920 px (title box height is twice that)."""
    size = float(c.get("size", 60))
    lines = c["text"].count("\n") + 1
    max_scale = max([v for _, v in kf.get("scale", [])] + [c.get("scale", 100.0)]) / 100
    xs = [v for _, v in kf.get("x", [])] or [c.get("x", 0.5)]
    ys = [v for _, v in kf.get("y", [])] or [c.get("y", 0.5)]
    em = 1.5 * size * W / 1920
    half_w = em_width * em * max_scale / 2 / W                     # fractions of the frame
    half_h = 1.3 * em * (1 + (lines - 1) * 1.15) * max_scale / 2 / H     # visible line ~1.3 em
    room_w = min(min(x, 1 - x) for x in xs) - SAFE                  # centre to the nearest side edge
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
    p = FxProject(spec["name"], spec.get("width", 1080), spec.get("height", 1920), spec.get("fps", 30))
    clips = spec["clips"]
    texts = [c for c in clips if c["type"] == "text"]
    lines = sorted({(ln, c.get("font", "Arial")) for c in texts for ln in c["text"].split("\n")})
    refs = sorted({(ROLE_REF[script(c["text"])], c.get("font", "Arial")) for c in texts if c.get("role") and "size" not in c})
    measured = measure(lines + refs) if lines else []
    widths = dict(zip(lines + refs, measured))
    for c in texts:                                   # role -> size, normalised to how big this font really draws
        if c.get("role") and "size" not in c:
            c["size"] = role_size(c, widths[(ROLE_REF[script(c["text"])], c.get("font", "Arial"))], p.W, p.H)
    stack_texts(texts, p.W, p.H)                      # "below": put a subline under its headline, whatever its line count
    if spec.get("contrast", True):
        fix_contrast(clips, texts, p.W, p.H)          # text colour readable on what is really underneath it

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
        elif c["type"] == "text":
            font = c.get("font", "Arial")
            w = max(widths[(ln, font)] for ln in c["text"].split("\n"))
            words = c["text"].split()
            one = fit_text_size(c, w, p.W, p.H, kf, quiet=True)
            if "\n" not in c["text"] and len(words) >= 3 and one < 0.8 * c.get("size", 60):
                cut = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
                c2 = dict(c, text=" ".join(words[:cut]) + "\n" + " ".join(words[cut:]))   # too wide: try two balanced lines
                new = [(ln, font) for ln in c2["text"].split("\n") if (ln, font) not in widths]
                widths.update(zip(new, measure(new)) if new else [])
                w2 = max(widths[(ln, font)] for ln in c2["text"].split("\n"))
                if fit_text_size(c2, w2, p.W, p.H, kf, quiet=True) > one:      # keep it only if the text ends up bigger
                    c, w = c2, w2
                    print(f"note: text '{words[0]} ...' split into two lines to fit the frame")
            size = fit_text_size(c, w, p.W, p.H, kf)
            obj = p.title_clip(c["text"].replace("\n", "\r"), c["start"], c["end"], font=font, font_size=size,
                               color=int(c.get("color", "#FFFFFF").lstrip("#")[:6], 16), text_width=w, lines=c["text"].count("\n") + 1, **common)
        elif c["type"] == "effect":
            obj = p.fx(c["name"], c["start"], c["end"])
        else:
            raise ValueError(f"unknown clip type {c['type']}")
        for f in c.get("filters", []):
            p.filter(obj, f)
        made.append((c, obj))

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

    alanes = []
    for c in sorted((c for c in clips if c["type"] == "audio"), key=lambda a: a["start"]):
        obj = p.audio_clip(c["path"], c["start"], dur=c.get("duration"), gain_db=c.get("gain_db", -10.0), fade_out=c.get("fade_out", 0.0),
                           src_in=c.get("src_in", 0.0))
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
    path, end = p.save(out)
    subprocess.run([sys.executable, os.path.join(HERE, "check_wfp.py"), path], check=True)
    if register:
        subprocess.run([sys.executable, os.path.join(HERE, "register_project.py"), path, str(round(end / 1e7 * p.fps))], check=True)
    n = lambda t: sum(1 for c in clips if c["type"] == t)
    print(f"built {path}  {end / 1e7:.2f}s  video tracks={len(lanes)} audio tracks={len(alanes)}  "
          f"video={n('video')} images={n('image')} texts={n('text')} effects={n('effect')} audio={n('audio')}")
    return path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out")
    ap.add_argument("--no-register", action="store_true")
    a = ap.parse_args()
    build(json.load(open(a.spec, encoding="utf-8")), a.out, not a.no_register)
