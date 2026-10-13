"""Native Filmora 16 drawn shapes (Drawing Tools: rectangle, ellipse, triangle, polygon, star, arrow, line) as
editable clips — fill, stroke, end shapes (arrowheads), trim path (self-drawing lines), transform keyframes.

Decoded from a project Filmora 16.0.12 saved itself + the install folder
(resources/wfx_effect/desc_service/path_*, configs/TrimPathAnimation).

A shape is a main-timeline clip of type 26, serviceType "pen" (no media, no resource, no title timeline):
  effect chain "Basic"   crop-pan-zoom + transform (Position_x/y = shape centre in 0..1 of the frame, Rotation deg)
  effect chain "graphic" path_clear, path_graphic_<kind> (geometry params + the generated path points),
                         path_stroke, path_fill, path_trim, shape_render (end shapes), inner/drop shadow (off),
                         path_render
The geometry is always drawn CENTRED at (0.5, 0.5) in frame fractions (x of width, y of height); the transform moves it.

    from filmora_fx import FxProject
    import filmora_shape as fs
    p = FxProject("Shapes", 1080, 1920)
    p.add_lane([fs.shape_clip(p, "line", 0.5, 4, x=0.5, y=0.2, w=0.7, stroke="#D97757", stroke_width=16,
                              cap="round", trim_preset="linear", trim_dur=1.0)])
    p.save("out.wfp")
"""
import json, math, sys

from filmora_wfp import TICKS, guid, kf_param, pip_buf, set_ud, thisuid, ud, ud_guid64, ud_int, ud_str

KINDS = {  # spec name -> Filmora graphic effect (UI name)
    "rect": "rect", "rectangle": "rect", "square": "rect",
    "ellipse": "circle", "circle": "circle",
    "triangle": "triangle",
    "polygon": "polygon", "hexagon": "polygon", "pentagon": "polygon",
    "star": "star",
    "arrow": "arrow",            # the filled block arrow of Drawing Tools
    "line": "line",              # open path; add arrowheads with arrow_end / arrow_begin
}
END_SHAPES = ["none", "arrow", "triangle", "circle", "diamond_arrow", "reverse_triangle"]   # shape_render index
END_ALIASES = {None: "none", "": "none", "line_arrow": "arrow", "diamond": "diamond_arrow", "reverse": "reverse_triangle"}
CAPS = {"butt": 0, "round": 1, "square": 2}        # UI: Butt / Round / Square   (index order = Skia, UNVERIFIED)
JOINS = {"miter": 0, "round": 1, "bevel": 2}       # UI: Miter / Round / Bevel   (index order = Skia, UNVERIFIED)
LINE_STYLES = {"solid": 0, "dashed": 1, "dash_dot": 2}   # lineType (UNVERIFIED order)
TRIM_PRESETS = {  # spec name -> (Filmora preset id stored in clip userData 16010, ease of the End key)
    "linear": ("linear_draw", "linear"), "ease_in": ("ease_in_draw", "in"),
    "ease_out": ("ease_out_draw", "out"), "ease_in_out": ("ease_in_out_draw", "inout"),
}
KAPPA = 0.55228475  # Bezier circle handle (Filmora's ellipse handles measure 0.5523)
EMPTY_KF = '{"Version": 3,"ParameterType": 0,"keyframeSets": [],"MD5":"d41d8cd98f00b204e9800998ecf8427e"}'
EMPTY_MASK = '{"paths": [],"horFlip": false,"verticalFlip": false}'


# ------------------------------------------------------------------ helpers
def _rgb(c):
    """'#RRGGBB' / 0xRRGGBB -> int stored by Filmora (0xRRGGBB assumed, like text colours — UNVERIFIED for shapes)."""
    if isinstance(c, int):
        return c
    return int(str(c).lstrip("#")[:6], 16)


def _eff(eid, params=None, enable=None, mask=None, extra_ud=()):
    e = {"display": eid.rsplit("/", 1)[1], "id": eid, "placeholder": False, "placeholderStatus": 0, "thisUId": thisuid(), "type": 3,
         "userData": [ud_guid64(3, guid()), ud(7, b"\x01"), *extra_ud]}
    if enable is not None:
        e["enable"] = enable
    if mask is not None:
        e["effectMask"] = {"custom_mask": mask, "path_reverse": False}
    if params:
        e["paramList"] = [{"fxParam": {"paramType": t, "unValue": v}, "name": n} for n, (t, v) in params.items()]
    return e


def _f(v):
    return round(float(v), 8)


def _pt(x, y, left=None, right=None):
    p = {"type": 0, "value_x": _f(x), "value_y": _f(y), "keyframe_x": EMPTY_KF, "keyframe_y": EMPTY_KF}
    if left is not None:
        p["left_ctrl_point"] = {"type": 1, "value_x": _f(left[0]), "value_y": _f(left[1]), "keyframe_x": EMPTY_KF, "keyframe_y": EMPTY_KF}
        p["right_ctrl_point"] = {"type": 2, "value_x": _f(right[0]), "value_y": _f(right[1]), "keyframe_x": EMPTY_KF, "keyframe_y": EMPTY_KF}
    return p


def _path_json(points, closed):
    path = {"uuid": thisuid(), "enable": True, "pos_x": 0.5, "pos_y": 0.5, "horizontal": 1.0, "vertical": 1.0, "rotation": 0,
            "scale": 0.0, "feather": 0.0, "invert": False, "is_closed": closed, "opacity": 1.0, "shape": 0,
            "keyframe_feather": EMPTY_KF, "keyframe_opacity": EMPTY_KF, "keyframe_scale": EMPTY_KF, "pathname": "", "points": points}
    return json.dumps({"paths": [path], "horFlip": False, "verticalFlip": False}, separators=(",", ": "))


def _geometry(kind, w, h, corner_radius=0.0, sides=6, polygon_inner=0.0, points=5, inner_ratio=50.0, top_offset=50.0,
              shaft=50.0, head=50.0):
    """Path points + params of one shape, bbox centred at (0.5, 0.5); w, h in frame fractions."""
    x0, y0 = 0.5 - w / 2, 0.5 - h / 2
    prm = {"start_x": (3, _f(x0)), "start_y": (3, _f(y0)), "width": (3, _f(w)), "height": (3, _f(h))}
    closed = True
    if kind == "rect":
        pts = [_pt(x0, y0), _pt(x0 + w, y0), _pt(x0 + w, y0 + h), _pt(x0, y0 + h)]
        prm["corner_radius"] = (3, float(corner_radius))
    elif kind == "circle":   # top, right, bottom, left (clockwise) with left = incoming / right = outgoing handles
        rx, ry, kx, ky = w / 2, h / 2, KAPPA * w / 2, KAPPA * h / 2
        pts = [_pt(0.5, y0, (0.5 - kx, y0), (0.5 + kx, y0)),
               _pt(0.5 + rx, 0.5, (0.5 + rx, 0.5 - ky), (0.5 + rx, 0.5 + ky)),
               _pt(0.5, y0 + h, (0.5 + kx, y0 + h), (0.5 - kx, y0 + h)),
               _pt(0.5 - rx, 0.5, (0.5 - rx, 0.5 + ky), (0.5 - rx, 0.5 - ky))]
    elif kind == "triangle":
        pts = [_pt(x0 + w * top_offset / 100, y0), _pt(x0 + w, y0 + h), _pt(x0, y0 + h)]
        prm["top_offset"] = (3, float(top_offset))
    elif kind == "polygon":   # vertices from the top, clockwise, stretched to the box width (as preset_polygon.json)
        n = int(sides)
        sx = max(abs(math.sin(2 * math.pi * k / n)) for k in range(n)) or 1.0
        pts = [_pt(x0 + w * (0.5 + 0.5 * math.sin(2 * math.pi * k / n) / sx), y0 + h * (0.5 - 0.5 * math.cos(2 * math.pi * k / n)))
               for k in range(n)]
        prm["sides"] = (5, n)
        prm["inner_radius"] = (3, float(polygon_inner))
    elif kind == "star":      # outer ellipse w/2 x h/2, inner = ratio %, from the top, clockwise (matches the sample)
        n, r = int(points), inner_ratio / 100.0
        pts = []
        for k in range(2 * n):
            a, f = math.pi * k / n, (1.0 if k % 2 == 0 else r)
            pts.append(_pt(0.5 + f * w / 2 * math.sin(a), 0.5 - f * h / 2 * math.cos(a)))
        prm["points"] = (5, n)
        prm["inner_radius_ratio"] = (3, float(inner_ratio))
    elif kind == "arrow":     # shaft = shaft % of the height, head = head % of the width (sample: 50 / 50)
        s0, s1, hx = 0.5 - h * shaft / 200, 0.5 + h * shaft / 200, x0 + w * (1 - head / 100)
        pts = [_pt(x0, s0), _pt(hx, s0), _pt(hx, y0), _pt(x0 + w, 0.5), _pt(hx, y0 + h), _pt(hx, s1), _pt(x0, s1)]
        prm["rect_height"] = (3, float(shaft))
        prm["triangle_ratio"] = (3, float(head))
    elif kind == "line":      # always horizontal through the centre; direction comes from the transform rotation
        pts = [_pt(x0, 0.5), _pt(x0 + w, 0.5)]
        prm["start_y"], prm["height"] = (3, 0.5), (3, 0.0)
        closed = False
    else:
        raise ValueError(kind)
    return pts, prm, closed


def _kf(points):
    """Keyframe parameter string; linear keys keep Filmora's own shape (no zero derivatives), eased keys -> curves."""
    s = kf_param(points)
    return s.replace(',"_leftDerivative": 0.0', "").replace(',"_rightDerivative": 0.0', "")


# ------------------------------------------------------------------ public API
def shape_clip(p, kind, start, end, x=0.5, y=0.5, w=0.3, h=None, rotation=0.0, scale=100.0, opacity=100.0,
               fill="#D9D9D9", fill_opacity=100, stroke=None, stroke_width=4, stroke_opacity=100,
               cap="round", join="round", line_style="solid",
               corner_radius=0.0, sides=6, polygon_inner=0.0, points=5, inner_ratio=50.0, top_offset=50.0,
               arrow_shaft=50.0, arrow_head=50.0, arrow_begin=None, arrow_end=None, p1=None, p2=None,
               trim=None, trim_preset=None, trim_dur=None, trim_delay=0.0,
               kf_x=None, kf_y=None, kf_rot=None, kf_scale=None, kf_opacity=None):
    """A native, editable Filmora shape clip. Add it with p.add_lane([...]) like any other clip (one lane = one track).

    kind      rect | ellipse/circle | triangle | polygon (sides) | star (points, inner_ratio %) | arrow (block) | line
    x, y      centre, 0..1 of the frame (y down) — same as image/video clips
    w, h      size as fractions of the frame WIDTH / HEIGHT; h=None -> same pixel size as w (square / circle)
    p1, p2    line only: end points (x, y) in frame fractions -> sets x, y, w and rotation
    rotation  degrees (transform Rotation)
    fill / stroke   '#RRGGBB' or None (off); stroke_width = Filmora "Weight" 0..20 (int); opacity values 0..100
    cap / join      round|butt|square / round|miter|bevel;  line_style solid|dashed|dash_dot
    corner_radius   rect, Filmora units 0..100;  arrow_shaft / arrow_head = % of height / width (default 50)
    arrow_begin / arrow_end   end shapes: none | arrow (line arrow) | triangle | circle | diamond_arrow | reverse_triangle
    trim       {"start": v|[[t,v(,ease)],..], "end": ..., "offset": ...}; values 0..100 % (offset -360..360),
               t = seconds from the clip start. Shown as "Manual" in Filmora.
    trim_preset   linear | ease_in | ease_out | ease_in_out — End 0 -> 100 (a self-drawing line), like Filmora's presets;
               trim_dur None = whole clip (Filmora's "fit clip"), else seconds; trim_delay = seconds before drawing starts
    kf_x / kf_y / kf_rot / kf_scale / kf_opacity   [(t, value[, ease])], t = seconds from the clip start
    """
    k = KINDS.get(str(kind).lower())
    if not k:
        raise ValueError(f"unknown shape {kind!r}; choose from {', '.join(sorted(KINDS))}")
    sides = {"pentagon": 5, "hexagon": 6}.get(str(kind).lower(), sides)
    if k == "line" and p1 and p2:
        dx, dy = (p2[0] - p1[0]) * p.W, (p2[1] - p1[1]) * p.H
        x, y = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        w = math.hypot(dx, dy) / p.W
        rotation = math.degrees(math.atan2(dy, dx)) % 360      # y down -> clockwise-positive (UNVERIFIED sign)
    if h is None:
        h = w * p.W / p.H
    if k == "line":
        h = 0.0
        if stroke is None:
            stroke = fill or "#FFFFFF"
        fill = None
    if not 0 < w <= 1 or not 0 <= h <= 1:
        print(f"[filmora_shape] warning: {kind} size w={w:.3f} h={h:.3f} is outside Filmora's 0..1 range", file=sys.stderr)
    sw = int(round(stroke_width))
    if sw > 20:
        print(f"[filmora_shape] stroke_width {stroke_width} > 20 (Filmora's max) -> 20", file=sys.stderr)
        sw = 20

    dur = p.ticks(end) - p.ticks(start)
    dur_s = dur / TICKS
    pts, prm, closed = _geometry(k, w, h, corner_radius, sides, polygon_inner, points, inner_ratio, top_offset, arrow_shaft, arrow_head)

    # ---- Basic chain: crop-pan-zoom + transform
    tf_params = {"dwValue": (5, 1186339), "Position_x": (3, float(x)), "Position_y": (3, float(y))}
    if rotation:
        tf_params["Rotation"] = (3, float(rotation))
    if scale != 100.0:
        tf_params["Scale_x"], tf_params["Scale_y"] = (3, float(scale)), (3, float(scale))
    tf = _eff("video/effect/transform", tf_params,
              extra_ud=(ud_str(15005, "1.0"), ud_str(36880, "1", nul=True)))
    p._keyframes(tf, 0.0, kf_scale=kf_scale, kf_x=kf_x, kf_y=kf_y, kf_rot=kf_rot)   # pen clips: inPoint 0 -> clip seconds

    # ---- graphic chain
    shape = _eff(f"graphic/effect/path_graphic_{k}", prm, mask=_path_json(pts, closed))
    if stroke:
        st = _eff("graphic/effect/path_stroke", {"color": (5, _rgb(stroke)), "alpha": (5, int(stroke_opacity)), "lineSize": (5, sw),
                                                 "lineCap": (5, CAPS[cap]), "lineJoin": (5, JOINS[join]),
                                                 "lineType": (5, LINE_STYLES[line_style])})
    else:
        st = _eff("graphic/effect/path_stroke", {"lineSize": (5, 0), "alpha": (5, 0)}, enable=False)
    if fill and k != "line":
        fl = _eff("graphic/effect/path_fill", {"fillType": (5, 0), "color": (5, _rgb(fill)), "alpha": (5, int(fill_opacity))})
    else:
        fl = _eff("graphic/effect/path_fill", {"alpha": (5, 0)}, enable=False)

    # trim path
    t_static = {"start": 0.0, "end": 100.0, "offset": 0.0}
    t_keys, preset_id = {}, None
    if trim_preset:
        preset_id, ease = TRIM_PRESETS[trim_preset]
        t0 = max(0.0, float(trim_delay))
        t1 = min(dur_s - 1.0 / p.fps, t0 + trim_dur) if trim_dur else dur_s - 1.0 / p.fps   # Filmora: last key 1 frame before the end
        t_keys = {"end": [(t0, 0.0, ease), (t1, 100.0)], "offset": [(t0, 0.0), (t1, 0.0)], "start": [(t0, 0.0), (t1, 0.0)]}
    for name, spec in (trim or {}).items():
        if isinstance(spec, (int, float)):
            t_static[name] = float(spec)
            t_keys.pop(name, None)
        else:
            t_keys[name] = [tuple(q) for q in spec]
    for name, ks in t_keys.items():
        t_static[name] = float(sorted(ks)[-1][1])
    tr_params = {"start": (3, t_static["start"]), "end": (3, t_static["end"]), "offset": (3, t_static["offset"]),
                 "ICustomMask": (14, {"custom_mask": EMPTY_MASK, "path_reverse": False})}
    trim_e = _eff("graphic/effect/path_trim", tr_params, mask=EMPTY_MASK, extra_ud=(ud(130, b"{}"),))
    if t_keys:
        trim_e["paramMapList"] = [{"key": 3, "keyFrame": {"parameter": _kf(ks)}, "name": name} for name, ks in t_keys.items()]

    rp = {}
    for side, val in (("start_shape", arrow_begin), ("end_shape", arrow_end)):
        v = END_ALIASES.get(val, val)
        if v not in END_SHAPES:
            raise ValueError(f"unknown end shape {val!r}; choose from {', '.join(END_SHAPES)}")
        if v != "none":
            rp[side] = (5, END_SHAPES.index(v))
    graphic = [_eff("graphic/effect/path_clear"), shape, st, fl, trim_e, _eff("graphic/effect/shape_render", rp or None),
               _eff("graphic/effect/path_innershadow", enable=False), _eff("graphic/effect/path_dropshadow", enable=False),
               _eff("graphic/effect/path_render")]

    c = {"componentPathLinks": {},
         "effectChainList": [{"effectList": [_eff("video/effect/crop-pan-zoom"), tf], "name": "Basic"},
                             {"effectList": graphic, "name": "graphic"},
                             {"effectList": [], "name": "Effect"},
                             {"effectList": [], "name": "_wes_hold_effectchain_"}],
         "inPoint": 0, "outPoint": dur, "placeholder": False, "placeholderStatus": 0, "serviceType": "pen",
         "thisUId": thisuid(), "tlBegin": p.ticks(start), "tlEnd": p.ticks(end), "type": 26,
         "userData": [ud_int(102, 0), ud_int(6, p.main_tl_id), ud_int(103, 16), ud_guid64(3, guid()), ud_int(1, 32), ud_int(2, 0)]}
    if preset_id:
        set_ud(c, 16010, ud_str(16010, preset_id))   # trim preset label shown in the panel (cosmetic)
    c["pipBuf"], c["pipBufSize"] = pip_buf(opacity, [(p.ticks(q[0]), *q[1:]) for q in kf_opacity] if kf_opacity else None)
    return c


def describe():
    print("shapes:", ", ".join(sorted(KINDS)))
    print("end shapes:", ", ".join(END_SHAPES), "| caps:", ", ".join(CAPS), "| joins:", ", ".join(JOINS),
          "| line styles:", ", ".join(LINE_STYLES))
    print("trim presets:", ", ".join(TRIM_PRESETS), "(+ manual trim={'start'|'end'|'offset': value or [[t, v], ...]})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(__doc__)
    describe()
