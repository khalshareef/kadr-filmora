"""Shape masks on video/image clips for filmora_wfp / filmora_fx projects.

Format (recovered from projects saved by Filmora 15.2, a Filmora template loaded by 16, and Filmora 16's own
resources/wfx_effect/desc_service/*Mask/description.json + configs/MaskPreset/default/*.conf):

  * a clip gets one more effect chain, {"name": "Mask", "effectList": [<mask effect>]}, placed after "Effect"
    (and "Color" if present) and before "_wes_hold_effectchain_".  One shape mask per clip.
  * the mask effect is a normal effect object: id "video/effect/<shape>mask", display "<Shape>Mask", type 3,
    userData key 3 (GUID, 64 bytes) + key 7 (b"\\x01"); params in paramList (paramType 3 = float, 1 = bool).
  * Position_x/_y are normalised to the clip's SOURCE frame (0..1, y down), not to the timeline frame;
    the clip's own transform (position/scale/rotation) moves the masked picture as a whole.
  * size: full width = Scale x Horizontal x S, full height = Scale x Vertical x S, where S = the SHORT side of the
    source frame (so Horizontal == Vertical gives a circle on any aspect ratio).
  * Rotation in degrees, Feather 0..1 (UI "blur strength" 0..100 %), InvMask bool, Radius 0..1 (corner / star inner).
  * keyframes: paramMapList [{"key": 3, "name": <param>, "keyFrame": {"parameter": kf_param(...)}}], the same
    keyframe string as transform keyframes; times are in source seconds (clip inPoint + offset), like transform.

Usage (after building the clip with FxProject.video_clip / Project.image_clip):

    import filmora_mask as fm
    c = p.video_clip("D:/a.mp4", 0, 4)
    fm.add_mask(c, "ellipse", x=0.5, y=0.5, w=0.4, feather=0.3, project=p)          # circle spotlight
    fm.add_mask(c2, "rect", x=0.25, y=0.5, w=0.5, h=1.0, project=p)                 # left half
    fm.add_mask(c3, "ellipse", w=0.6, project=p, keyframes={"scale": [(0, 0.05), (2, 1.0)]})   # grows over 2 s

x, y: centre in 0..1 of the clip's source picture.  w, h: size as a fraction of the source picture's width/height
(h=None -> same length as w, i.e. a circle/square).  Keyframes accept the friendly names x, y, w, h, scale,
rotation, feather, radius (or raw Filmora names), times in seconds from the clip start.
"""
import base64, glob, json, os, struct, uuid, warnings

from filmora_wfp import TICKS, kf_param

# shape -> (effect id, display, max Horizontal/Vertical, max Scale, params it has)
SHAPES = {
    "ellipse":     ("video/effect/ellipsemask",    "EllipseMask",    3.0, 2.0, ("Position_x", "Position_y", "Scale", "Rotation", "Horizontal", "Vertical", "Feather", "InvMask")),
    "rect":        ("video/effect/roundrectmask",  "RoundRectMask",  3.0, 2.0, ("Position_x", "Position_y", "Scale", "Rotation", "Horizontal", "Vertical", "Radius", "Feather", "InvMask")),
    "double_line": ("video/effect/doublelinemask", "DoubleLineMask", 3.0, 4.0, ("Position_x", "Position_y", "Scale", "Rotation", "Horizontal", "Feather", "InvMask")),
    "line":        ("video/effect/singlelinemask", "SingleLineMask", 0.0, 0.0, ("Position_x", "Position_y", "Rotation", "Feather", "InvMask")),
    "star":        ("video/effect/fivestarmask",   "FiveStarMask",   2.0, 4.0, ("Position_x", "Position_y", "Scale", "Rotation", "Horizontal", "Vertical", "Radius", "Feather", "InvMask")),
    "heart":       ("video/effect/heartmask",      "HeartMask",      3.0, 4.0, ("Position_x", "Position_y", "Scale", "Rotation", "Horizontal", "Vertical", "Feather", "InvMask")),
    # experimental: present in Filmora 16's effect registry, never seen in a saved project
    "text":        ("video/effect/textmask",       "TextMask",       0.0, 4.0, ("Position_x", "Position_y", "Scale", "Rotation", "CharSpace", "LineSpace", "InvMask", "DisplayMask", "CaptionJson", "MotionPath")),
    "image":       ("E9C6A2FD-10EE-474E-BD7A-2FB33AA8BD30", "imageMask", 0.0, 0.0, ("Profile", "x", "y", "width", "height", "blurStrength", "invertMask")),
}
ALIASES = {"circle": "ellipse", "oval": "ellipse", "rectangle": "rect", "roundrect": "rect", "square": "rect",
           "single_line": "line", "linear": "line", "parallel_lines": "double_line", "band": "double_line",
           "five_star": "star", "love": "heart"}
PTYPE = {"InvMask": 1, "DisplayMask": 1, "CharSpace": 5, "LineSpace": 5, "CaptionJson": 6, "MotionPath": 6,
         "Profile": 6, "x": 5, "y": 5, "width": 5, "height": 5, "invertMask": 5}
FRIENDLY = {"x": "Position_x", "y": "Position_y", "scale": "Scale", "rotation": "Rotation", "rot": "Rotation",
            "feather": "Feather", "radius": "Radius"}


def _guid64():
    h = uuid.uuid4().hex.upper()
    g = "{%s-%s-%s-%s-%s}" % (h[:8], h[8:12], h[12:16].lower(), h[16:20], h[20:])
    raw = g.encode().ljust(64, b"\0")
    return {"data": base64.b64encode(raw).decode(), "key": 3, "size": 64}


def _thisuid():
    return str(uuid.uuid1())


def source_size(clip, project=None):
    """(width, height) of the clip's source picture, looked up in the project's media registry."""
    if project is not None:
        for m in project.medias.values():
            if m["res"].get("filename") == clip.get("filename"):
                vs = (m["res"].get("vidStreamInfo") or [{}])[0]
                if vs.get("width") and vs.get("height"):
                    return int(vs["width"]), int(vs["height"])
    return None


def filmora_mask_images():
    """Filmora's built-in image-mask pictures (01.png .. 40.png) from the installed version, or []."""
    root = os.path.normpath(os.path.join(os.path.expandvars("%LOCALAPPDATA%"), "..", "LocalWondershare", "Wondershare Filmora"))
    hits = sorted(glob.glob(os.path.join(root, "*", "resources", "wfx_effect", "material", "Masks", "[0-9][0-9].png")))
    return [h.replace("\\", "/") for h in hits]


def _caption_json(text, font, color=-1, size=256, bold=0):
    return json.dumps({"Layout": {"TextAlign": "center", "TextAlignMode": "horizontal", "Underline": 0}, "Text": text,
                       "TextData": [{"Basic": {"Effect": 0, "Enable": 1, "FontBold": bold, "FontItalic": 0, "FontName": font,
                                               "FontSize": size, "TextAlpha": 255, "TextBlurRadius": 0, "TextColor": color},
                                     "Border": {"Alpha": 255, "BlurRadius": 0, "Color": -65536, "Enable": 0, "Size": 5},
                                     "CharData": text, "CharSpace": 0, "LineSpace": 0,
                                     "Shadow": {"Alpha": 255, "BlurRadius": 6, "Color": -65281, "Direction": 3, "Distance": 10, "Enable": 0}}]},
                      ensure_ascii=False, separators=(",", ":"))


def mask_chain(clip):
    """The clip's "Mask" effect chain, created in the right place if missing."""
    chains = clip["effectChainList"]
    for ch in chains:
        if ch["name"] == "Mask":
            return ch
    ch = {"effectList": [], "name": "Mask"}
    hold = next((i for i, c in enumerate(chains) if c["name"] == "_wes_hold_effectchain_"), len(chains))
    chains.insert(hold, ch)
    return ch


def remove_mask(clip):
    for ch in clip["effectChainList"]:
        if ch["name"] == "Mask":
            ch["effectList"] = []
    return clip


def add_mask(clip, shape="ellipse", x=0.5, y=0.5, w=0.5, h=None, rotation=0.0, feather=0.0, invert=False,
             opacity=1.0, radius=None, keyframes=None, project=None, src_size=None,
             text="TEXT", font=None, text_color=-1, image=None):
    """Insert a mask effect into clip (a dict from Project.image_clip / FxProject.video_clip). Returns the effect.

    shape: ellipse|rect|double_line|line|star|heart (+ experimental text|image); aliases circle, rectangle, ...
    x, y : centre, 0..1 of the source picture (y down).    w, h: fractions of the source width / height
           (h=None -> square/circle).  double_line: band thickness = h (fraction of source height) if given,
           else w (fraction of source width); use rotation to turn the band (orientation at 0 deg unverified).
           line: only x, y, rotation, feather, invert (one straight edge through x, y).
    rotation degrees; feather 0..1; invert -> keep the outside; radius 0..1 (rect corners / star inner radius).
    opacity: Filmora's shape masks have no opacity parameter (only the new multi-mask system has) -> must be 1.
    keyframes: {name: [(sec_from_clip_start, value)]}; names x, y, w, h, scale, rotation, feather, radius or raw
           Filmora param names.  w/h keyframe values use the same units as w/h; scale multiplies the base size.
    project / src_size: needed to convert w/h for non-square sources (src_size=(width, height) wins).
    text mask: text, font (required: the user's chosen font), text_color (ARGB int, -1 = white).
    image mask: image = path to a white-on-transparent PNG or an int 1..40 (Filmora's built-in shapes).
    """
    shape = ALIASES.get(shape, shape)
    if shape not in SHAPES:
        raise ValueError(f"unknown mask shape {shape!r}; choose from {sorted(SHAPES)}")
    if abs(float(opacity) - 1.0) > 1e-6:
        warnings.warn("Filmora shape masks have no opacity parameter; opacity ignored (use the clip opacity instead)")
    eid, display, hv_max, s_max, names = SHAPES[shape]
    sw, sh = src_size or source_size(clip, project) or (1, 1)
    short = float(min(sw, sh))
    fw, fh = sw / short, sh / short            # source width/height in short-side units

    def hv(wv, hvv):                            # fractions of source -> (Horizontal, Vertical) at Scale 1
        return wv * fw, (hvv if hvv is not None else wv * fw / fh) * fh

    vals = {}
    scale = 1.0
    if shape == "image":
        imgs = filmora_mask_images()
        if image is None or isinstance(image, int):
            n = image or 2
            pick = [p for p in imgs if os.path.basename(p) == f"{n:02d}.png"]
            if not pick:
                raise FileNotFoundError("Filmora's built-in mask images not found; pass image='path.png'")
            image = pick[0]
        # x, y: offset of the picture centre in % (-1000..1000, 0 = centred); width/height: % of the clip (0..400)
        vals = {"Profile": "file:/" + os.path.abspath(image).replace("\\", "/"), "x": int(round((x - 0.5) * 100)),
                "y": int(round((y - 0.5) * 100)), "width": int(round(w * 100)), "height": int(round((h if h is not None else w) * 100)),
                "blurStrength": float(feather) * 100.0, "invertMask": 1 if invert else 0}
    elif shape == "text":
        if not font:
            raise ValueError("text masks need font= (the user's chosen font)")
        vals = {"Position_x": float(x), "Position_y": float(y), "Scale": float(w if w is not None else 1.0),
                "Rotation": float(rotation) % 360.0, "CharSpace": 0, "LineSpace": 0, "InvMask": bool(invert),
                "DisplayMask": False, "CaptionJson": _caption_json(text, font, text_color), "MotionPath": ""}
    else:
        vals = {"Position_x": float(x), "Position_y": float(y), "Rotation": float(rotation),
                "Feather": max(0.0, min(1.0, float(feather))), "InvMask": bool(invert)}
        if shape in ("ellipse", "rect", "star", "heart"):
            H, V = hv(w, h)
            big = max(H, V)
            if big > hv_max:                     # keep Horizontal/Vertical in range by raising Scale
                scale = min(s_max, big / hv_max)
                H, V = H / scale, V / scale
            vals.update(Scale=scale, Horizontal=H, Vertical=V)
            if shape == "rect":
                vals["Radius"] = float(radius if radius is not None else 0.0)
            if shape == "star":
                vals["Radius"] = float(radius if radius is not None else 0.5)
        elif shape == "double_line":
            t = (h * fh) if h is not None else (w * fw)
            if t > hv_max:
                scale = min(s_max, t / hv_max)
                t = t / scale
            vals.update(Scale=scale, Horizontal=t)

    eff = {"display": display, "id": eid,
           "paramList": [{"fxParam": {"paramType": PTYPE.get(n, 3), "unValue": vals[n]}, "name": n} for n in names if n in vals],
           "placeholder": False, "placeholderStatus": 0, "thisUId": _thisuid(), "type": 3,
           "userData": [_guid64(), {"data": base64.b64encode(b"\x01").decode(), "key": 7, "size": 1}]}

    if keyframes:
        base = clip.get("inPoint", 0) / TICKS        # keyframe times are source seconds, like transform keyframes
        maps = {}
        for name, pts in keyframes.items():
            n = FRIENDLY.get(name, name)
            if name in ("w", "h"):
                if shape not in ("ellipse", "rect", "star", "heart", "double_line"):
                    raise ValueError(f"{shape} has no size to keyframe")
                if shape == "double_line":
                    n, conv = "Horizontal", (lambda v, name=name: (v * (fh if name == "h" else fw)) / scale)
                elif name == "w":
                    n, conv = "Horizontal", (lambda v: v * fw / scale)
                else:
                    n, conv = "Vertical", (lambda v: v * fh / scale)
            else:
                conv = float
            if n not in names:
                raise ValueError(f"{shape} mask has no parameter {name!r}")
            maps[n] = {"key": 3, "keyFrame": {"parameter": kf_param([(base + float(t), conv(v)) for t, v in pts])}, "name": n}
            if n in vals:                            # static value = first keyframe (what Filmora shows off-keyframe)
                for p in eff["paramList"]:
                    if p["name"] == n:
                        p["fxParam"]["unValue"] = conv(sorted(pts)[0][1])
        eff["paramMapList"] = list(maps.values())

    ch = mask_chain(clip)
    ch["effectList"] = [eff]                         # one shape mask per clip
    # clip userData 13003 = which preset the Mask panel highlights (UI state only; seen for these two shapes)
    ui = {"rect": "Mask_Rectangle_Default", "double_line": "Mask_Double line_Default"}.get(shape)
    if ui:
        raw = ui.encode()
        clip["userData"] = [u for u in clip.get("userData", []) if u["key"] != 13003] + \
                           [{"data": base64.b64encode(raw).decode(), "key": 13003, "size": len(raw)}]
    return eff
