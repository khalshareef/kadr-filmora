"""Speed for Filmora (.wfp) clips: constant speed (Uniform Speed) and speed ramps (Speed Ramping curves/presets).

Decoded from Filmora 16 projects saved by Filmora itself + its install folder (see _work/decode_speed.md).

  clip["speed"] = {"offset": src_in_sec, "offsetEnd": src_out_sec, "reverse": bool, "speedParam": "<json>"}
  speedParam keyframes: _time = SOURCE seconds (whole media, 0.._totalTime), _value = speed multiplier.
    Interpolation 6 = hold (constant speed): [(0, v), (_totalTime, 1.0)]  (the last key is only an end marker)
    Interpolation 9 = speed ramp: between two keys the speed eases (smoothstep) in OUTPUT time, so a segment of
                      source length S between speeds v0 -> v1 lasts 2*S/(v0+v1) on the timeline.
  inPoint/outPoint = mapped (timeline-rate) time M(offset) / M(offsetEnd), M(t) = output time to reach source t;
  tlEnd - tlBegin = outPoint - inPoint.  Clip keyframes (transform/opacity) are based on inPoint, not on offset.

Use from the builder (after filmora_fx.FxProject.video_clip, before add_lane):
    import filmora_speed as fs
    c = p.video_clip(path, start, start + 1, src_in=2.0)          # end is replaced by apply_speed
    dur = fs.apply_speed(c, 2.0, 6.0, speed=2.0, total=fs.media_total(p, path))         # 2 s on the timeline
    dur = fs.apply_speed(c, 1.0, 7.0, preset="montage", total=fs.media_total(p, path))
    dur = fs.apply_speed(c, 1.0, 7.0, curve=[(0, 3), (0.4, 0.4), (0.6, 0.4), (1, 3)], total=...)
    next_start = (c["tlEnd"]) / TICKS
"""
import json, math, os, struct, hashlib

TICKS = 10_000_000
HOLD, RAMP = 6, 9

# Filmora 16 built-in Speed Ramping presets: configs/Speed/<name>.conf in the install folder
# ("CurvedSpeed": [{SourceNormalPos 0..100, SpeedRatio, IsFreezeFrame}]). Positions are % of the clip's source range.
PRESETS = {
    "customize":   [(0, 1.0), (25, 1.0), (50, 1.0), (75, 1.0), (100, 1.0)],
    "montage":     [(0, 0.9), (10, 0.9), (50, 6.8), (65, 0.3), (80, 1.0), (100, 1.0)],
    "hero_moment": [(0, 1.0), (5, 1.0), (35, 5.5), (45, 0.5), (55, 0.5), (65, 5.5), (95, 1.0), (100, 1.0)],
    "bullet_time": [(0, 5.2), (40, 5.2), (46, 0.5), (54, 0.5), (60, 5.2), (100, 5.2)],
    "jumper":      [(0, 0.6), (43, 0.6), (50, 6.0), (57, 0.6), (100, 0.6)],
    "flash_in":    [(0, 5.2), (40, 5.2), (60, 1.0), (100, 1.0)],
    "flash_out":   [(0, 1.0), (40, 1.0), (60, 5.2), (100, 5.2)],
}
# our own extra curves (not Filmora presets) — handy for edits
PRESETS_EXTRA = {
    "fast_slow_fast": [(0, 3.0), (35, 3.0), (45, 0.4), (55, 0.4), (65, 3.0), (100, 3.0)],
    "slow_in":        [(0, 0.4), (40, 0.4), (60, 1.0), (100, 1.0)],
    "slow_out":       [(0, 1.0), (40, 1.0), (60, 0.4), (100, 0.4)],
}
SPEED_MIN, SPEED_MAX = 0.01, 100.0       # Uniform Speed range in Filmora's UI; ramp graph is 0.1x..10x
RAMP_MIN, RAMP_MAX = 0.1, 10.0
FRAME_INTERP = {"sampling": 0, "blending": 1, "optical_flow": 2}   # clip["frameInterpType"]; values UNVERIFIED


def _key(name):
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def preset_points(name):
    """[(fraction 0..1 of the source range, speed)] for a Filmora preset or one of PRESETS_EXTRA."""
    k = _key(name)
    pts = PRESETS.get(k) or PRESETS_EXTRA.get(k)
    if pts is None:
        raise KeyError(f"unknown speed preset '{name}'. Known: {sorted(PRESETS) + sorted(PRESETS_EXTRA)}")
    return [(p / 100.0, v) for p, v in pts]


def load_installed_presets(install_dir):
    """Read the presets live from Filmora's install folder (read-only). Returns {key: [(fraction, speed, freeze)]}."""
    folder = os.path.join(install_dir, "configs", "Speed")
    out = {}
    for f in sorted(os.listdir(folder)):
        if f.endswith(".conf"):
            raw = json.load(open(os.path.join(folder, f), encoding="utf-8")).get("CurvedSpeed") or "[]"
            out[_key(f[:-5])] = [(p["SourceNormalPos"] / 100.0, p["SpeedRatio"], p.get("IsFreezeFrame", 0)) for p in json.loads(raw)]
    return out


# ------------------------------------------------------------------ time model
def mapped_time(keys, t):
    """Output (timeline-rate) seconds needed to play source 0..t. keys: [(time, value, interp)] sorted by time.
    The interpolation of a segment is the one of its left key. Past the last key the last speed holds."""
    tot = 0.0
    if t <= keys[0][0]:
        return (t - keys[0][0]) / keys[0][1]
    for (t0, v0, i0), (t1, v1, _) in zip(keys, keys[1:]):
        if t <= t0:
            break
        e = min(t, t1)
        if i0 == RAMP and v1 != v0:
            S, D = t1 - t0, 2.0 * (t1 - t0) / (v0 + v1)
            if e >= t1:
                tot += D
            else:                                   # solve s(u) = S*(t-t0)/S for u in 0..1 (smoothstep speed)
                s = e - t0
                lo, hi = 0.0, 1.0
                for _ in range(80):
                    u = (lo + hi) / 2
                    if (v0 * u + (v1 - v0) * (u ** 3 - u ** 4 / 2)) * D < s:
                        lo = u
                    else:
                        hi = u
                tot += (lo + hi) / 2 * D
        else:                                       # hold (6) or flat ramp segment
            tot += (e - t0) / v0
        if t <= t1:
            return tot
    return tot + (t - keys[-1][0]) / keys[-1][1]


def source_time(keys, tau, hi_hint=None):
    """Inverse of mapped_time: the source second reached after tau output seconds."""
    lo, hi = keys[0][0], hi_hint or keys[-1][0]
    while mapped_time(keys, hi) < tau:
        hi = hi * 2 + 1
    for _ in range(100):
        m = (lo + hi) / 2
        if mapped_time(keys, m) < tau:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


# ------------------------------------------------------------------ speedParam writer
def _num(v):
    v = float(v)
    return repr(v) if v == int(v) else f"{v:.8f}"


def _r8(v):
    return float(f"{float(v):.8f}")


def kf_md5(keys):
    b = b"".join(struct.pack("<ddd", t, float(i), int((v + 0.0005) * 1000) / 1000) for t, v, i in keys)
    return hashlib.md5(b).hexdigest()


def speed_param_json(keys, total, derivatives=False, reverse=False):
    """keys: [(time_sec, speed, interp)]. Filmora's own text layout (spacing, 8-decimal numbers, MD5, _totalTime).
    derivatives=True writes the chord slope as _left/_rightDerivative (what Filmora writes for hold keys).
    reverse=True adds Filmora's trailing "reverse": 1 — without it keyframes on a reversed clip don't play."""
    keys = [(_r8(t), _r8(v), i) for t, v, i in keys]
    items = []
    for n, (t, v, i) in enumerate(keys):
        s = f'{{"_time": {_num(t)},"Interpolation": {i},"_value": {_num(v)}'
        if derivatives:
            if n > 0:
                t0, v0, _ = keys[n - 1]
                if v != v0:
                    s += f',"_leftDerivative": {_num((v - v0) / (t - t0))}'
            if n < len(keys) - 1:
                t1, v1, _ = keys[n + 1]
                if v1 != v:
                    s += f',"_rightDerivative": {_num((v1 - v) / (t1 - t))}'
        items.append(s + "}")
    return ('{"Version": 3,"ParameterType": 0,"keyframeSets": [' + ",".join(items) +
            f'],"MD5": "{kf_md5(keys)}","_totalTime": {_num(total)}' + (',"reverse": 1' if reverse else "") + "}")


def constant_keys(speed, total):
    return [(0.0, float(speed), HOLD), (float(total), 1.0, HOLD)]


def ramp_keys(points, src_in, src_out, total, edge=1.0):
    """points: [(fraction 0..1 of the source range, speed)] -> whole-media keys. Like Filmora, the curve sits on the
    clip's source range and is framed by end markers at 0 and _totalTime (speed `edge`, Filmora keeps 1.0 there)."""
    pts = sorted(points)
    if pts[0][0] > 0:
        pts = [(0.0, pts[0][1])] + pts
    if pts[-1][0] < 1:
        pts = pts + [(1.0, pts[-1][1])]
    span = src_out - src_in
    keys = [(src_in + f * span, max(RAMP_MIN, min(RAMP_MAX, float(v))), RAMP) for f, v in pts]
    if src_in > 1e-6:
        keys = [(0.0, edge, RAMP)] + keys
    if total - src_out > 1e-6:
        keys = keys + [(float(total), edge, RAMP)]
    return keys


# ------------------------------------------------------------------ clip helpers
def media_total(project, path):
    """Source length Filmora uses for _totalTime = video frames / fps (falls back to the container duration)."""
    m = project._video_media(path) if hasattr(project, "_video_media") else project.medias[os.path.abspath(path).replace("\\", "/")]
    vs = (m["res"].get("vidStreamInfo") or [{}])[0]
    fr, n = vs.get("frameRate") or {}, vs.get("totalFrames") or 0
    if n and fr.get("num"):
        return n * fr.get("den", 1) / fr["num"]
    return round(m.get("dur") or m["res"]["mediaLength"] / TICKS, 2)


def fit_speed(src_len, tl_len):
    """Constant speed that plays src_len source seconds in tl_len timeline seconds."""
    return src_len / tl_len


def _rebase_keyframes(clip, delta_sec):
    """Clip keyframes are timed on inPoint; keep their timeline positions when inPoint moves by delta_sec."""
    if abs(delta_sec) < 1e-9:
        return
    from filmora_wfp import shift_param         # keeps each key's own interpolation and curve handles
    for ch in clip.get("effectChainList", []):
        for e in ch.get("effectList", []):
            for m in e.get("paramMapList") or []:
                try:
                    m["keyFrame"]["parameter"] = shift_param(m["keyFrame"]["parameter"], delta_sec)
                except (KeyError, TypeError, ValueError):
                    continue
    pb = clip.get("pipBuf")
    if pb and "OpacityKeyFrame" in pb:
        d = json.loads(pb)
        d["OpacityKeyFrame"] = shift_param(d["OpacityKeyFrame"], delta_sec * TICKS)
        s = json.dumps(d, separators=(",", ":"))
        clip["pipBuf"], clip["pipBufSize"] = s, len(s.encode()) + 1


def apply_speed(clip, src_in, src_out=None, *, speed=None, curve=None, preset=None, total, duration=None,
                reverse=False, pair=None, maintain_pitch=None, frame_interp=None, rebase=True):
    """Give a clip (video, or its paired audio) a constant speed or a ramp. Sets speed/inPoint/outPoint/tlEnd
    (tlBegin is kept) and returns the new timeline duration in ticks.

    src_in, src_out : source seconds played by the clip. Give `duration` (timeline seconds) instead of src_out to
                      solve how much source the speed/curve consumes in that time.
    speed           : constant multiplier (0.5 = slow-mo, 2 = double speed).
    curve / preset  : ramp points [(fraction 0..1 of the source range, speed 0.1..10)] or a preset name
                      (PRESETS: montage, hero_moment, bullet_time, jumper, flash_in, flash_out, customize; or PRESETS_EXTRA).
    total           : media source length in seconds (media_total(project, path)).
    pair            : the clip's own audio clip (same media) — receives the identical speed and timing.
    maintain_pitch  : audio clips only: True/False -> "speedWithPitch" (Filmora's Maintain Pitch switch). Unverified.
    frame_interp    : video only: "sampling" | "blending" | "optical_flow" -> "frameInterpType". Unverified.
    reverse         : Filmora's Reverse Speed flag; inPoint/outPoint (and all keyframes) move to the mirrored axis.
    """
    if sum(x is not None for x in (speed, curve, preset)) != 1:
        raise ValueError("give exactly one of speed=, curve=, preset=")
    if speed is not None:
        if not SPEED_MIN <= speed <= SPEED_MAX:
            raise ValueError(f"speed {speed} outside {SPEED_MIN}..{SPEED_MAX}")
        keys = constant_keys(speed, total)
        if src_out is None:
            src_out = src_in + duration * speed
    else:
        pts = preset_points(preset) if preset is not None else [(float(f), float(v)) for f, v in curve]
        if src_out is None:                      # the curve is stretched over the source range -> solve the range
            lo, hi = src_in + 1e-3, total
            for _ in range(60):
                mid = (lo + hi) / 2
                k = ramp_keys(pts, src_in, mid, total)
                if mapped_time(k, mid) - mapped_time(k, src_in) < duration:
                    lo = mid
                else:
                    hi = mid
            src_out = (lo + hi) / 2
        keys = ramp_keys(pts, src_in, src_out, total)
    if not 0 <= src_in < src_out <= total + 1e-6:
        raise ValueError(f"source range {src_in}..{src_out} outside media 0..{total}")
    a, b = mapped_time(keys, src_in), mapped_time(keys, src_out)
    sp = speed_param_json(keys, total, derivatives=(speed is not None), reverse=bool(reverse))
    dur = int(round(b * TICKS)) - int(round(a * TICKS))
    if reverse:
        # Filmora counts a reversed clip from the END of the media: inPoint = mapped(total) - mapped(src_out)
        # (verified on a Filmora-saved sample: media 8 s, source 1..4 at 1x -> inPoint 4.0, outPoint 7.0), and every
        # keyframe of the clip sits on that axis. offset/offsetEnd keep the forward source range.
        a = mapped_time(keys, total) - b
    for c in [clip] + ([pair] if pair is not None else []):
        old_in = c.get("inPoint", 0)
        c["speed"] = {"offset": float(src_in), "offsetEnd": float(src_out), "reverse": bool(reverse), "speedParam": sp}
        c["inPoint"], c["outPoint"] = int(round(a * TICKS)), int(round(a * TICKS)) + dur
        c["tlEnd"] = c["tlBegin"] + dur
        if rebase:
            _rebase_keyframes(c, (c["inPoint"] - old_in) / TICKS)
    if maintain_pitch is not None and pair is not None:
        pair["speedWithPitch"] = bool(maintain_pitch)
    if frame_interp is not None:
        clip["frameInterpType"] = FRAME_INTERP[frame_interp] if isinstance(frame_interp, str) else int(frame_interp)
    return dur


def describe(clip):
    """Read back a clip's speed: dict(kind, keys, offset, offsetEnd, predicted/actual duration)."""
    sp = clip["speed"]
    P = json.loads(sp["speedParam"])
    keys = [(k["_time"], k["_value"], k["Interpolation"]) for k in P["keyframeSets"]]
    a, b = mapped_time(keys, sp["offset"]), mapped_time(keys, sp["offsetEnd"])
    kind = "1x" if all(k[1] == 1 for k in keys) else ("ramp" if any(k[2] == RAMP for k in keys) else "constant")
    return dict(kind=kind, keys=keys, offset=sp["offset"], offsetEnd=sp["offsetEnd"], reverse=sp["reverse"],
                pred_in=a, pred_out=b, pred_dur=b - a, inPoint=clip["inPoint"] / TICKS, outPoint=clip["outPoint"] / TICKS,
                dur=(clip["tlEnd"] - clip["tlBegin"]) / TICKS, md5_ok=kf_md5(keys) == P.get("MD5"))
