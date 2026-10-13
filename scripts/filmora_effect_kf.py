"""Keyframed EFFECT parameters for Filmora 16 projects: filters on a clip, effect layers (clip type 8), audio volume.

Works on the dicts that filmora_fx / filmora_wfp produce (no Filmora UI involved). Recovered from the user's own
Filmora-saved projects (Untitled 33/37/39/62 ...) and Filmora's install folder — see _work/decode_effect_kf.md.

Where it lives:  effect["paramMapList"] = [{"key": <paramType>, "keyFrame": {"parameter": "<json string>"}, "name": <param>}]
                 (same effect object that holds the static "paramList"; one map per animated param)
Time unit:       seconds on the clip's inPoint axis: _time = clip.inPoint/1e7 + seconds_from_clip_start
                 (video/audio clips: inPoint = source in-point; images & effect layers: inPoint = 3600 s; titles: 0).
                 Only the clip's pipBuf OpacityKeyFrame uses ticks instead.
Interpolation:   1 = linear (what Filmora writes for every keyframe a user adds). Eases/hold are baked into dense linear
                 keyframes (a point every 2 frames), the same approach build_from_spec uses for transform eases.
MD5:             md5(concat pack("<ddd", time, interpolation, int((value+0.0005)*1000)/1000)) — computed here from the
                 numbers exactly as written in the string, so it always re-verifies.

    import filmora_effect_kf as ekf
    fx = p.fx("Basic_Blur_196795", 1, 4)                                  # effect layer
    ekf.keyframe_clip_effect(fx, "Basic_Blur_196795", "Blur", [(0, 0), (1.5, 100), (3, 0)], fps=30)
    v = p.video_clip(path, 0, 5, filters=["Allpurpose_Glitch"])
    ekf.keyframe_clip_effect(v, "Allpurpose_Glitch", "BlockSize", [(0.5, 0), (2, 20)], interpolation="ease_out")
    a = p.audio_clip(wav, 0, 4, gain_db=-14)
    ekf.set_volume_keyframes(a, [(0, -60), (1.5, -14)], fps=30)
"""
import hashlib, json, math, os, struct, sys

TICKS = 10_000_000
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# paramType codes (paramList fxParam.paramType == paramMapList "key"), confirmed in user projects + install descriptors
PARAM_TYPE = {"bool": 1, "double": 2, "float": 3, "int": 5, "string": 6}
KEYFRAMABLE_TYPES = (2, 3, 5)

# Native Interpolation codes seen in Filmora files (see decode_effect_kf.md). Only 1 is written by default.
INTERP = {
    "linear": 1,        # every keyframe a user adds in Filmora 16 (effects, transform, opacity, volume)
}
# Easings baked into dense linear keyframes (Filmora draws straight lines between them).
EASE = {
    "linear": lambda u: u,
    "ease_in": lambda u: u ** 3,
    "ease_out": lambda u: 1 - (1 - u) ** 3,
    "ease_in_out": lambda u: 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2,
    "smooth": lambda u: 0.5 - 0.5 * math.cos(math.pi * u),            # gentle sine in-out
    "back": lambda u: 1 + 2.70158 * (u - 1) ** 3 + 1.70158 * (u - 1) ** 2,
}
ALIASES = {"in": "ease_in", "out": "ease_out", "inout": "ease_in_out", "ease": "ease_in_out", "easeinout": "ease_in_out",
           "freeze": "hold", "constant": "hold", "step": "hold"}

# Built-in (non-downloaded) effects: name -> (min, max, paramType). From the install folder's descriptors.
VOLUME_RANGE = (-100.0, 20.0)       # FFAudioVolumeTypeDefine::minVolume / maxVolume (dB)
BUILTIN = {
    "audio/effect/volume": {"VolumeGain": (-100.0, 20.0, 2)},
    # numeric but never seen animated; ranges unknown (no range check)
    "audio/effect/fade": {"FadeInTime": (None, None, 2), "FadeOutTime": (None, None, 2)},
    "audio/effect/equalizer": {k: (None, None, 2) for k in ("31Hz", "63Hz", "125Hz", "250Hz", "500Hz", "1kHz", "2kHz", "4kHz", "8kHz", "16kHz")},
    "662E16ED-4524-4D13-AAE9-11DBA0C63E17": {k: (-100.0, 100.0, 3) for k in (         # AdjustColor (Color chain)
        "u_temperature", "u_tint", "u_exposure", "u_brightness", "u_contrast", "u_vibrance", "u_saturation",
        "u_highLight", "u_shadow", "u_whiteLevel", "u_blackLevel")},
    "616D7BAC-39DB-415A-9EEA-798678A43617": {"amount": (-100.0, 100.0, 3)},              # Sharpen
    "video/effect/doublelinemask": {"Horizontal": (0.0, 3.0, 3), "Feather": (0.0, 1.0, 3), "Scale": (0.01, 4.0, 3),
                                    "Position_x": (-1.0, 2.0, 3), "Position_y": (-1.0, 2.0, 3), "Rotation": (-9999.99, 9999.99, 3)},
}


# ------------------------------------------------------------------ number format + MD5 (Filmora's own conventions)
def _num(v):
    v = float(v)
    return repr(v) if v == int(v) and abs(v) < 1e15 else f"{v:.8f}"


def _val(v, ptype):
    return str(int(round(v))) if ptype == 5 else _num(v)


def kf_md5(points):
    """points: [(time, interpolation, value)] -> Filmora's keyframe MD5."""
    b = b"".join(struct.pack("<ddd", float(t), float(i), int((float(v) + 0.0005) * 1000) / 1000) for t, i, v in points)
    return hashlib.md5(b).hexdigest()


def verify_md5(param_string):
    """True when the MD5 inside a keyframe parameter string matches its keyframes."""
    d = json.loads(param_string)
    return kf_md5([(k["_time"], k["Interpolation"], k["_value"]) for k in d.get("keyframeSets", [])]) == d.get("MD5")


def kf_string(points, ptype=3, interp=1):
    """Build the 'parameter' JSON string exactly like Filmora 16 writes it.
    points: [(time_in_param_units, value)]; ptype 3 float / 2 double / 5 int (ints get Filmora's ParameterType 1 header)."""
    pts = sorted((float(t), float(v)) for t, v in points)
    # numbers as written, then parsed back -> the MD5 always matches what is on disk
    w = [(_num(t), _val(v, ptype)) for t, v in pts]
    f = [(float(a), float(b)) for a, b in w]
    items = []
    for n, ((ts, vs), (t, v)) in enumerate(zip(w, f)):
        s = f'{{"_time": {ts},"Interpolation": {interp},"_value": {vs}'
        if interp == 1 and len(f) > 1:          # slopes of the straight segments; Filmora omits zero slopes
            if n > 0:
                t0, v0 = f[n - 1]
                d = (v - v0) / (t - t0) if t != t0 else 0.0
                if d:
                    s += f',"_leftDerivative": {_num(d)}'
            if n < len(f) - 1:
                t1, v1 = f[n + 1]
                d = (v1 - v) / (t1 - t) if t1 != t else 0.0
                if d:
                    s += f',"_rightDerivative": {_num(d)}'
        items.append(s + "}")
    md5 = kf_md5([(t, interp, v) for t, v in f])
    head = '{"Version": 3,"ParameterType": 1,"_minVal": -100,"_maxVal": 100,"_baseRatio": 1,' if ptype == 5 \
        else '{"Version": 3,"ParameterType": 0,'
    return head + '"keyframeSets": [' + ",".join(items) + f'],"MD5":"{md5}"}}'


# ------------------------------------------------------------------ easing / timing
def bake(points, interpolation="linear", fps=30, step_frames=2):
    """[(t_rel, v)] -> [(t_rel, v)] with eases/hold sampled into linear keyframes; times snapped to frames."""
    mode = ALIASES.get(str(interpolation).lower().replace("-", "_").replace(" ", "_"), str(interpolation).lower())
    snap = (lambda t: round(round(t * fps) / fps, 6)) if fps else (lambda t: t)
    pts = sorted((snap(t), float(v)) for t, v in points)
    if len(pts) < 2 or mode == "linear":
        return pts
    out = [pts[0]]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if mode == "hold":                         # keep v0 until one frame before the next key, then jump
            tj = snap(t1 - 1.0 / (fps or 30))
            if tj > t0 and v0 != v1:
                out.append((tj, v0))
        elif v0 != v1:
            f = EASE.get(mode)
            if f is None:
                raise ValueError(f"unknown interpolation '{interpolation}' (use {sorted(set(EASE) | {'hold'})})")
            n = max(1, int(round((t1 - t0) * (fps or 30) / step_frames)))
            out += [(snap(t0 + (t1 - t0) * i / n), v0 + (v1 - v0) * f(i / n)) for i in range(1, n)]
        out.append((t1, v1))
    dedup = {}
    for t, v in out:
        dedup[t] = v
    return sorted(dedup.items())


def time_base_of(clip):
    """Seconds added to clip-relative times: the clip's inPoint on Filmora's keyframe axis."""
    return clip.get("inPoint", 0) / TICKS


# ------------------------------------------------------------------ catalog validation
def _catalog_entry(effect):
    try:
        import catalog_filmora
        for c in catalog_filmora.load():
            if c.get("guid", "").upper() == str(effect.get("id", "")).upper():
                return c
    except Exception:
        pass
    return None


def param_spec(effect, name):
    """(min, max, paramType) for a param of this effect, or None when unknown (no catalog / not listed)."""
    b = BUILTIN.get(effect.get("id")) or BUILTIN.get(str(effect.get("id", "")).upper())
    if b and name in b:
        return b[name]
    c = _catalog_entry(effect)
    if c:
        for p in c.get("params", []):
            if p["name"] == name:
                return (p.get("min"), p.get("max"), PARAM_TYPE.get(str(p.get("type", "float")).lower(), 3))
        names = [p["name"] for p in c.get("params", [])]
        raise KeyError(f"'{name}' is not a parameter of {c.get('slug')} (has: {names})")
    if b:
        raise KeyError(f"'{name}' is not a known parameter of {effect.get('id')} (has: {sorted(b)})")
    return None


# ------------------------------------------------------------------ public API
def set_effect_keyframes(effect, param_name, points, interpolation="linear", time_base=0.0, fps=30,
                         ptype=None, clamp=False, static=None, native_code=None, step_frames=2):
    """Animate one parameter of an effect/filter dict (an entry of a clip's effectList).

    points       [(seconds_from_clip_start, value), ...]  (>= 1 point)
    interpolation linear | ease_in | ease_out | ease_in_out | smooth | back | hold   (eases are baked, see bake())
    time_base    seconds added to every time = clip inPoint (pass the clip dict itself, or use keyframe_clip_effect)
    ptype        2 double / 3 float / 5 int; default from the catalog (float when unknown)
    clamp        clamp values to the catalog range instead of raising
    static       value for the static paramList entry (default: the first keyframe value)
    native_code  EXPERIMENTAL: write this raw Interpolation code on unbaked points instead of 1 (see decode_effect_kf.md)
    Returns the parameter string written."""
    if isinstance(time_base, dict):
        time_base = time_base_of(time_base)
    spec = param_spec(effect, param_name)
    lo, hi, cat_type = spec if spec else (None, None, 3)
    ptype = ptype or cat_type or 3
    if ptype not in KEYFRAMABLE_TYPES:
        raise ValueError(f"'{param_name}' has paramType {ptype} (string/bool) — not keyframable")
    pts = []
    for t, v in points:
        v = float(v)
        if lo is not None and hi is not None and not (lo - 1e-9 <= v <= hi + 1e-9):
            if not clamp:
                raise ValueError(f"{param_name}={v} outside {lo}..{hi} (pass clamp=True to clamp)")
            v = min(max(v, lo), hi)
        pts.append((float(t), v))
    if not pts:
        raise ValueError("no keyframes")
    curve = {"ease_out": "out", "ease_in": "in", "ease_in_out": "inout", "smooth": "inout"}.get(interpolation)
    if native_code is None and curve and ptype in (2, 3) and len(pts) > 1:
        # Filmora's own Bezier keys (Interpolation 13, verified on transforms): 2 editable points per move
        from filmora_wfp import kf_param_curve
        baked = sorted(pts)
        s = kf_param_curve([(round(time_base + t, 8), v, curve) for t, v in baked])
    elif native_code is not None:
        baked, code = sorted(pts), int(native_code)
        s = kf_string([(round(time_base + t, 8), v) for t, v in baked], ptype, code)
    else:
        baked, code = bake(pts, interpolation, fps, step_frames), INTERP["linear"]
        s = kf_string([(round(time_base + t, 8), v) for t, v in baked], ptype, code)
    maps = [m for m in effect.get("paramMapList", []) or [] if m.get("name") != param_name]
    maps.append({"key": ptype, "keyFrame": {"parameter": s}, "name": param_name})
    effect["paramMapList"] = maps
    sv = baked[0][1] if static is None else static
    plist = [p for p in effect.get("paramList", []) or [] if p.get("name") != param_name]
    plist.append({"fxParam": {"paramType": ptype, "unValue": int(round(sv)) if ptype == 5 else float(sv)}, "name": param_name})
    effect["paramList"] = plist
    return s


def find_effect(clip, name_or_id):
    """The effect dict on a clip whose id/GUID, display name or catalog slug/title matches."""
    key = str(name_or_id).lower()
    guid = None
    try:
        import catalog_filmora
        guid = catalog_filmora.find(name_or_id)["guid"].lower()
    except Exception:
        pass
    for ch in clip.get("effectChainList", []):
        for e in ch.get("effectList", []):
            if str(e.get("id", "")).lower() in (key, guid) or str(e.get("display", "")).lower() == key:
                return e
    raise KeyError(f"no effect '{name_or_id}' on this clip")


def keyframe_clip_effect(clip, effect_name, param_name, points, **kw):
    """Animate a param of an effect that sits on `clip` (filter on a video/image/title clip, or the effect of an
    effect layer from FxProject.fx). Times are seconds from the clip's start."""
    return set_effect_keyframes(find_effect(clip, effect_name), param_name, points, time_base=time_base_of(clip), **kw)


def set_volume_keyframes(audio_clip, points_db, interpolation="linear", fps=30, clamp=True):
    """Volume automation on an audio clip (or a video clip's paired audio): points_db = [(seconds_from_clip_start, dB)].
    dB range -100..+20 (Filmora's slider). Linear in dB, so a fade-in from -60 dB sounds even."""
    return keyframe_clip_effect(audio_clip, "audio/effect/volume", "VolumeGain", points_db,
                                interpolation=interpolation, fps=fps, ptype=2, clamp=clamp)


def read_keyframes(effect, param_name):
    """[(time, value, interpolation)] of an animated param (empty if none)."""
    for m in effect.get("paramMapList", []) or []:
        if m.get("name") == param_name:
            d = json.loads(m["keyFrame"]["parameter"])
            return [(k["_time"], k["_value"], k["Interpolation"]) for k in d.get("keyframeSets", [])]
    return []


if __name__ == "__main__":   # self-test against the strings Filmora itself wrote (Untitled 62 / 33)
    ok = kf_string([(0.0, 0.0), (2.0, 1.0), (3.31428, 0.0)]).split('"MD5":"')[1][:32] == "bbed07098c1be42bd13db42a76babadd"
    ok2 = kf_string([(7.64, 0.0), (10.0, 18.78)], ptype=2).split('"MD5":"')[1][:32] == "832bfc6fa2ec6164de373f98ccbd3ebb"
    ok3 = kf_string([(0.0, 0), (0.56, 0), (0.6, 70)], ptype=5).split('"MD5":"')[1][:32] == "1a4b779bdcc109d51e8148b4031512a9"
    print("glitch MD5", ok, "| volume MD5", ok2, "| int MD5", ok3)
