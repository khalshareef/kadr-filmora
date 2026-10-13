"""Motion tracking: make a text / image / shape follow a moving object in a video, stored the way Filmora 16 does it.

What Filmora 16 saves after Video > Tracking > Motion Tracking + "Link Element" (decoded from a real saved sample,
see _work/decode_tracking.md):
  * the VIDEO clip gets an effect chain "ObjTracking" (between "Mask" and "_wes_hold_effectchain_") with one effect
    id 87289B96-239D-4740-BF86-023F54349902 "ObjectTracking", param "ObjectTrackingPtr" (paramType 7) =
    {enabled: false, visble: false, pointSet: [inPoint, outPoint] ticks,
     resultList: [{rect: [left, top, w, h] (fractions of the source picture), status: 1, time: source ticks}, ...]}
    one entry per PROJECT frame from inPoint, plus a final sentinel at outPoint with status 0 and the first rect;
  * the LINKED element gets per-frame transform keyframes Position_x / Position_y (Interpolation 1 = linear),
    value = rect centre (mapped into the frame) + a constant offset, plus clip userData
    54 = GUID of the tracked video clip, 57 = {"version":"1.0.1","x":dx,"y":dy,"w":1.0,"h":1.0} (the offset
    = element start position - box centre at the first frame). No scale/rotation keys.
The keyframes alone are what moves the element; the chain + link make Filmora's Tracking panel show the track.

API
    pts = track_points(video, src_in, duration, box=(cx, cy, w, h), fps=30, method="csrt")
          -> [(t, cx, cy)] for every output frame t = k/fps, k = 0..round(duration*fps) (t = seconds from clip start;
             cx/cy fractions of the video picture). track_points(..., return_info=True) -> (pts, info) with per-frame
             boxes (info["rects"]) and the lost-target frames (info["lost"]).
    pl  = placement(video, W, H, scale=100, x=0.5, y=0.5)            # how the clip sits in the project frame
    kf  = to_frame_keyframes(pts, pl, start_xy=(0.5, 0.5), offset=(0, 0), simplify=0.0)
          -> {"x": [[t, v], ...], "y": [[t, v], ...]}  ready for a spec clip's "keyframes" (use "ease": "linear")
    attach_tracking(video_clip, info, src_in, duration, fps)        # write Filmora's ObjTracking chain (clip dict)
    link_element(element_clip, video_clip, offset_xy)               # userData 54 / 57 on the linked clip
    patch_wfp(wfp, track_json, video_name, link_text=...)          # do both on a saved .wfp (post-build)

CLI
    python motion_track.py <video> --src-in 1.0 --duration 5 --box 0.45,0.55,0.08,0.12 --out track.json
        [--fps 30] [--method csrt|kcf|mil|template] [--smooth 1.0]
        [--frame 1920x1080 --scale 100 --x 0.5 --y 0.5 --start-xy 0.5,0.5 --offset 0,0 --simplify 0]
        [--sheet preview.jpg]
    python motion_track.py --patch "Project.wfp" --track track.json --video P4_SH03 --link-text TRACK

Limits: the video clip must play at speed 1 (no speed ramp / reverse), no rotation, no keyframes on the video clip
itself; the tracked object should stay inside the picture. Requires opencv-contrib-python(-headless) for CSRT/KCF
(falls back to template matching when they are missing).
"""
import argparse, base64, copy, json, math, os, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

TICKS = 10_000_000
TRACK_EFFECT_ID = "87289B96-239D-4740-BF86-023F54349902"
WORK_LONG_SIDE = 960          # frames are tracked at this size (long side) for speed


# ------------------------------------------------------------------ tracking
def _cv():
    import cv2
    return cv2


def _make_tracker(method):
    """CSRT / KCF / MIL from OpenCV (contrib); None -> use template matching."""
    cv2 = _cv()
    names = {"csrt": "TrackerCSRT_create", "kcf": "TrackerKCF_create", "mil": "TrackerMIL_create"}
    if method == "template":
        return None
    for mod in (cv2, getattr(cv2, "legacy", None)):
        f = getattr(mod, names.get(method, ""), None) if mod is not None else None
        if f:
            return f()
    print(f"note: OpenCV tracker '{method}' not available (pip install opencv-contrib-python-headless) "
          "-> using template matching")
    return None


def _frames(video, s0, s1):
    """Yield (source_seconds, BGR frame) for every native frame from s0 to s1 (inclusive, clamped to the file)."""
    cv2 = _cv()
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise FileNotFoundError(video)
    nfps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 10 ** 9
    i0 = min(n - 1, max(0, int(round(s0 * nfps))))
    i1 = min(n - 1, int(math.ceil(s1 * nfps - 1e-6)))
    if i0 > 1500:                                   # far into the file: seek; short offsets: decode exactly
        cap.set(cv2.CAP_PROP_POS_FRAMES, i0)
    else:
        for _ in range(i0):
            cap.grab()
    for i in range(i0, i1 + 1):
        ok, f = cap.read()
        if not ok:
            break
        yield i / nfps, f
    cap.release()


def _gauss_smooth(vals, good, sigma):
    """Light Gaussian smoothing over good samples only (lost samples were already interpolated)."""
    if sigma <= 0 or len(vals) < 3:
        return list(vals)
    r = max(1, int(round(sigma * 2.5)))
    w = [math.exp(-0.5 * (k / sigma) ** 2) for k in range(-r, r + 1)]
    out = []
    for i in range(len(vals)):
        num = den = 0.0
        for k in range(-r, r + 1):
            j = i + k
            if 0 <= j < len(vals) and good[j]:
                num += w[k + r] * vals[j]
                den += w[k + r]
        out.append(num / den if den else vals[i])
    return out


def _fill_lost(vals, good):
    """Linear interpolation across lost samples (hold at the ends)."""
    idx = [i for i, g in enumerate(good) if g]
    if not idx:
        return list(vals)
    out = list(vals)
    for i in range(len(vals)):
        if good[i]:
            continue
        a = max([j for j in idx if j < i], default=None)
        b = min([j for j in idx if j > i], default=None)
        if a is None:
            out[i] = vals[b]
        elif b is None:
            out[i] = vals[a]
        else:
            u = (i - a) / (b - a)
            out[i] = vals[a] + (vals[b] - vals[a]) * u
    return out


def _interp(ts, vs, t):
    if t <= ts[0]:
        return vs[0]
    if t >= ts[-1]:
        return vs[-1]
    lo, hi = 0, len(ts) - 1
    while hi - lo > 1:
        m = (lo + hi) // 2
        if ts[m] <= t:
            lo = m
        else:
            hi = m
    u = (t - ts[lo]) / (ts[hi] - ts[lo])
    return vs[lo] + (vs[hi] - vs[lo]) * u


def track_points(video, src_in, duration, box, fps=30, method="csrt", smooth=1.0, return_info=False, quiet=False):
    """Follow `box` = (cx, cy, w, h) (fractions of the video picture at source second src_in) for `duration` seconds.
    Returns [(t, cx, cy)] for t = k/fps, k = 0..round(duration*fps), t in seconds from the clip start, centres in
    picture fractions. Lost-target frames are re-acquired by template matching when possible, otherwise bridged by
    linear interpolation and reported."""
    cv2 = _cv()
    import numpy as np
    cx, cy, bw, bh = (float(v) for v in box)
    tracker = _make_tracker(method)
    used = method if tracker is not None else "template"
    st, rects, good = [], [], []
    tmpl = None
    sc = None
    for s, f in _frames(video, src_in, src_in + duration):
        H0, W0 = f.shape[:2]
        if sc is None:
            sc = min(1.0, WORK_LONG_SIDE / max(W0, H0))
        img = cv2.resize(f, (round(W0 * sc), round(H0 * sc)), interpolation=cv2.INTER_AREA) if sc < 1 else f
        H, W = img.shape[:2]
        if not st:                                   # first frame: initialise
            r = [int(round((cx - bw / 2) * W)), int(round((cy - bh / 2) * H)), max(4, int(round(bw * W))), max(4, int(round(bh * H)))]
            r[0], r[1] = max(0, min(W - r[2], r[0])), max(0, min(H - r[3], r[1]))
            if tracker is not None:
                tracker.init(img, tuple(r))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            tmpl = gray[r[1]:r[1] + r[3], r[0]:r[0] + r[2]].copy()
            st.append(s); rects.append((r[0] / W, r[1] / H, r[2] / W, r[3] / H)); good.append(True)
            continue
        last = rects[-1]
        ok, nr = False, None
        if tracker is not None:
            ok, nr = tracker.update(img)
            if ok:
                nx, ny, nw, nh = nr[0] / W, nr[1] / H, nr[2] / W, nr[3] / H
                jump = math.hypot(nx + nw / 2 - last[0] - last[2] / 2, ny + nh / 2 - last[1] - last[3] / 2)
                if jump > 0.6 * max(last[2], last[3]) or nw <= 0 or nh <= 0:
                    ok = False                       # implausible jump in one frame -> treat as lost
        if not ok:                                   # template search around the last box
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            th, tw = tmpl.shape[:2]
            lcx, lcy = (last[0] + last[2] / 2) * W, (last[1] + last[3] / 2) * H
            m = 1.25 if tracker is not None else 0.5     # re-acquire: wide search; plain template mode: stay near
            x0, y0 = int(max(0, lcx - tw / 2 - m * tw)), int(max(0, lcy - th / 2 - m * th))
            x1, y1 = int(min(W, lcx + tw / 2 + m * tw)), int(min(H, lcy + th / 2 + m * th))
            win = gray[y0:y1, x0:x1]
            if win.shape[0] > th and win.shape[1] > tw:
                res = cv2.matchTemplate(win, tmpl, cv2.TM_CCOEFF_NORMED)
                _, score, _, loc = cv2.minMaxLoc(res)
                if score >= (0.5 if tracker is not None else 0.3):
                    rx, ry = x0 + loc[0], y0 + loc[1]
                    nx, ny, nw, nh = rx / W, ry / H, tw / W, th / H
                    ok = True
                    if tracker is not None:          # re-seed the tracker on the re-found object
                        tracker = _make_tracker(method)
                        tracker.init(img, (rx, ry, tw, th))
                    else:                            # plain template mode: let the template follow slow changes
                        patch = gray[ry:ry + th, rx:rx + tw]
                        if patch.shape == tmpl.shape:
                            tmpl = cv2.addWeighted(tmpl, 0.7, patch, 0.3, 0)
        if ok:
            rects.append((nx, ny, nw, nh)); good.append(True)
        else:
            rects.append(last); good.append(False)
        st.append(s)
    if not st:
        raise RuntimeError(f"no frames read from {video} at {src_in}s")
    # bridge lost frames, smooth lightly, then resample at the project frame rate
    cols = list(zip(*rects))
    cols = [_gauss_smooth(_fill_lost(list(c), good), good, smooth) for c in cols]
    lost_src = [round(s - src_in, 3) for s, g in zip(st, good) if not g]
    n = int(round(duration * fps))
    pts, out_rects, lost = [], [], []
    ts_rel = [s - src_in for s in st]
    for k in range(n + 1):
        t = k / fps
        l, tp, w, h = (_interp(ts_rel, c, t) for c in cols)
        pts.append((round(t, 6), round(l + w / 2, 8), round(tp + h / 2, 8)))
        out_rects.append((round(t, 6), l, tp, w, h))
        near = min(range(len(ts_rel)), key=lambda i: abs(ts_rel[i] - t))
        if not good[near]:
            lost.append(round(t, 4))
    if not quiet:
        span = f"{len(lost)} of {n + 1} output frames" if lost else "none"
        print(f"tracked {len(st)} source frames with {used}; lost target: {span}"
              + (f" (source-relative seconds {lost_src[:12]}{' ...' if len(lost_src) > 12 else ''})" if lost else ""))
    info = {"method": used, "rects": out_rects, "lost": lost, "lost_source": lost_src, "native_frames": len(st),
            "box": [cx, cy, bw, bh], "src_in": src_in, "duration": duration, "fps": fps, "video": video}
    return (pts, info) if return_info else pts


# ------------------------------------------------------------------ picture -> project frame
def picture_size(video):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height:stream_side_data=rotation", "-of", "json", video])
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"])


def placement(video_or_size, W, H, scale=100.0, x=0.5, y=0.5):
    """How a video/image clip sits in the project frame, like Filmora: scale 100 = fit inside the frame (letterbox),
    x/y = centre of the picture in frame fractions, scale % on top of the fit."""
    pw, ph = video_or_size if isinstance(video_or_size, (tuple, list)) else picture_size(video_or_size)
    return {"W": W, "H": H, "pic_w": pw, "pic_h": ph, "scale": float(scale), "x": float(x), "y": float(y)}


def pic_to_frame(px, py, pl):
    f = min(pl["W"] / pl["pic_w"], pl["H"] / pl["pic_h"]) * pl.get("scale", 100.0) / 100.0
    sw, sh = pl["pic_w"] * f / pl["W"], pl["pic_h"] * f / pl["H"]       # picture size in frame fractions
    return pl.get("x", 0.5) + (px - 0.5) * sw, pl.get("y", 0.5) + (py - 0.5) * sh


def _simplify(series, tol):
    """Drop keys that linear interpolation between the kept ones reproduces within tol (Douglas-Peucker on time)."""
    if tol <= 0 or len(series) < 3:
        return series
    keep = {0, len(series) - 1}
    stack = [(0, len(series) - 1)]
    while stack:
        a, b = stack.pop()
        (ta, va), (tb, vb) = series[a], series[b]
        worst, wi = 0.0, None
        for i in range(a + 1, b):
            t, v = series[i]
            e = abs(v - (va + (vb - va) * (t - ta) / (tb - ta)))
            if e > worst:
                worst, wi = e, i
        if wi is not None and worst > tol:
            keep.add(wi)
            stack += [(a, wi), (wi, b)]
    return [series[i] for i in sorted(keep)]


def to_frame_keyframes(points, clip_placement, start_xy, offset=(0.0, 0.0), simplify=0.0):
    """Tracked picture points -> project-frame x/y keyframes for the linked element (Filmora's "Link Element"):
    the element keeps its own start position and moves exactly as the object moves on screen.
    x(t) = start_x + (object_x(t) - object_x(0)) + offset_x   (frame fractions; same for y)
    = Filmora's rect centre(t) + its stored offset (userData 57). simplify > 0 thins keys (tolerance in frame
    fractions, e.g. 0.0005 = ~1 px on 1920); 0 keeps one key per frame like Filmora."""
    fx0, fy0 = pic_to_frame(points[0][1], points[0][2], clip_placement)
    sx, sy = start_xy
    ox, oy = offset
    xs, ys = [], []
    for t, px, py in points:
        fx, fy = pic_to_frame(px, py, clip_placement)
        xs.append([round(t, 6), round(sx + fx - fx0 + ox, 8)])
        ys.append([round(t, 6), round(sy + fy - fy0 + oy, 8)])
    return {"x": _simplify(xs, simplify), "y": _simplify(ys, simplify)}


def link_offset(points, clip_placement, start_xy):
    """Filmora's userData-57 offset: element start position - box centre at the first frame (frame fractions)."""
    fx0, fy0 = pic_to_frame(points[0][1], points[0][2], clip_placement)
    return start_xy[0] - fx0, start_xy[1] - fy0


# ------------------------------------------------------------------ Filmora's own tracking data
def _ud(key, raw):
    return {"data": base64.b64encode(raw).decode(), "key": key, "size": len(raw)}


def _get_ud(clip, key):
    for u in clip.get("userData", []):
        if u["key"] == key:
            return base64.b64decode(u["data"])
    return None


def _set_ud(clip, key, entry):
    clip["userData"] = [u for u in clip.get("userData", []) if u["key"] != key] + [entry]


def tracking_chain(info, src_in, duration, fps):
    """The "ObjTracking" effect chain exactly as Filmora 16 writes it (see module doc)."""
    from filmora_wfp import guid, thisuid
    n = int(round(duration * fps))
    t_in = int(round(src_in * TICKS))
    t_out = int(round((src_in + n / fps) * TICKS))
    rl = []
    for k, (t, l, tp, w, h) in enumerate(info["rects"][:n]):
        rl.append({"rect": [round(l, 8), round(tp, 8), round(w, 8), round(h, 8)], "status": 1,
                   "time": int(round((src_in + k / fps) * TICKS))})
    first = rl[0]["rect"] if rl else [0.375, 0.375, 0.25, 0.25]
    rl.append({"rect": list(first), "status": 0, "time": t_out})   # Filmora's end sentinel (status 0, first rect)
    eff = {"display": "ObjectTracking", "id": TRACK_EFFECT_ID,
           "paramList": [{"fxParam": {"paramType": 7, "unValue": {"enabled": False, "pointSet": [t_in, t_out],
                                                                  "resultList": rl, "visble": False}},
                          "name": "ObjectTrackingPtr"}],
           "placeholder": False, "placeholderStatus": 0, "thisUId": thisuid(), "type": 3,
           "userData": [_ud(3, guid().encode().ljust(64, b"\0")), _ud(7, b"\x01")]}
    return {"effectList": [eff], "name": "ObjTracking"}


def attach_tracking(video_clip, info, src_in, duration, fps):
    """Insert (or replace) the ObjTracking chain on a video clip dict, before "_wes_hold_effectchain_"."""
    chains = [c for c in video_clip["effectChainList"] if c.get("name") != "ObjTracking"]
    hold = next((i for i, c in enumerate(chains) if c.get("name") == "_wes_hold_effectchain_"), len(chains))
    chains.insert(hold, tracking_chain(info, src_in, duration, fps))
    video_clip["effectChainList"] = chains
    return video_clip


def link_element(element_clip, video_clip, offset_xy):
    """Mark element_clip (text wrapper / image / shape on the main timeline) as linked to the tracked video clip."""
    g = _get_ud(video_clip, 3)
    if not g:
        raise ValueError("video clip has no GUID (userData 3)")
    g = g.rstrip(b"\0")
    _set_ud(element_clip, 54, _ud(54, g))
    off = json.dumps({"version": "1.0.1", "x": float(offset_xy[0]), "y": float(offset_xy[1]), "w": 1.0, "h": 1.0},
                     separators=(",", ":"))
    _set_ud(element_clip, 57, _ud(57, off.encode()))
    return element_clip


def patch_wfp(wfp, track, video_name, link_text=None, link_image=None, start_xy=None):
    """Post-build: add Filmora's tracking chain to the video clip whose file name contains `video_name`, and link the
    text whose content is `link_text` (or the image whose file name contains `link_image`). `track` = the dict
    written by the CLI (--out) or {"info": ..., "placement": ..., "start_xy": ...}. Rewrites the .wfp in place."""
    info, pl = track["info"], track["placement"]
    sxy = start_xy or track.get("start_xy") or (0.5, 0.5)
    z = zipfile.ZipFile(wfp)
    files = {n: z.read(n) for n in z.namelist()}
    order = [i for i in z.infolist()]
    z.close()
    pi = json.loads(files["ProjectFolder/project_info.json"])
    tl_name = f"ProjectFolder/Medias/{pi['timeline_mediaId']}/timeline.wesproj"
    d = json.loads(files[tl_name])
    main = d["timelineInfos"][0]
    clips = [c for tr in main["trackInfos"] for c in tr.get("clipList", [])]
    vids = [c for c in clips if video_name in os.path.basename(c.get("filename", "")) and c.get("type") != 7]
    if not vids:
        raise ValueError(f"no clip for video '{video_name}'")
    vid = vids[0]
    attach_tracking(vid, info, info["src_in"], info["duration"], info["fps"])
    pts = [(t, l + w / 2, tp + h / 2) for t, l, tp, w, h in info["rects"]]
    off = link_offset(pts, pl, sxy)
    linked = []
    if link_text is not None:
        titles = {t["timelineId"]: t for t in d["timelineInfos"][1:]}
        for c in clips:
            if c.get("type") == 7 and c.get("timelineId") in titles:
                inner = titles[c["timelineId"]]["trackInfos"][0]["clipList"][0]
                txt = json.loads(inner["scriptBuf"]).get("Text", "")
                if txt.replace("\r", "\n") == link_text:
                    link_element(c, vid, off)
                    linked.append(f"text '{link_text}'")
    if link_image is not None:
        for c in clips:
            if c is not vid and link_image in os.path.basename(c.get("filename", "")):
                link_element(c, vid, off)
                linked.append(f"image '{link_image}'")
    files[tl_name] = json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode()
    tmp = wfp + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for i in order:
            zo.writestr(i.filename, files[i.filename])
    os.replace(tmp, wfp)
    print(f"patched {os.path.basename(wfp)}: ObjTracking chain on '{os.path.basename(vid['filename'])}' "
          f"({len(info['rects'][:int(round(info['duration'] * info['fps']))])} boxes), linked: {', '.join(linked) or 'none'}")
    return wfp


# ------------------------------------------------------------------ preview
def contact_sheet(video, info, out, n=6):
    """A few source frames with the tracked box drawn (orange), for a quick visual check."""
    cv2 = _cv()
    import numpy as np
    cap = cv2.VideoCapture(video)
    rects = info["rects"]
    picks = [rects[round(i * (len(rects) - 1) / (n - 1))] for i in range(n)]
    tiles = []
    for t, l, tp, w, h in picks:
        cap.set(cv2.CAP_PROP_POS_MSEC, (info["src_in"] + t) * 1000)
        ok, f = cap.read()
        if not ok:
            continue
        H, W = f.shape[:2]
        cv2.rectangle(f, (int(l * W), int(tp * H)), (int((l + w) * W), int((tp + h) * H)), (0, 140, 255), 4)
        cv2.circle(f, (int((l + w / 2) * W), int((tp + h / 2) * H)), 8, (0, 140, 255), -1)
        cv2.putText(f, f"{t:.2f}s", (30, 80), 0, 2.5, (255, 255, 255), 5)
        tiles.append(cv2.resize(f, (640, round(640 * H / W))))
    while len(tiles) % 3:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles), 3)]
    cv2.imwrite(out, np.vstack(rows))
    return out


# ------------------------------------------------------------------ CLI
def _floats(s, n):
    v = [float(x) for x in s.split(",")]
    if len(v) != n:
        raise argparse.ArgumentTypeError(f"expected {n} comma-separated numbers")
    return v


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("video", nargs="?")
    ap.add_argument("--src-in", type=float, default=0.0, help="source second where the clip starts")
    ap.add_argument("--duration", type=float, help="clip length in seconds")
    ap.add_argument("--box", help="cx,cy,w,h of the object at src-in (fractions of the video picture)")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--method", default="csrt", choices=["csrt", "kcf", "mil", "template"])
    ap.add_argument("--smooth", type=float, default=1.0, help="Gaussian sigma in source frames (0 = off)")
    ap.add_argument("--frame", default="1920x1080", help="project frame WxH (for the keyframes)")
    ap.add_argument("--scale", type=float, default=100.0, help="video clip scale %% (100 = fit)")
    ap.add_argument("--x", type=float, default=0.5, help="video clip centre x in the frame")
    ap.add_argument("--y", type=float, default=0.5, help="video clip centre y in the frame")
    ap.add_argument("--start-xy", default="0.5,0.5", help="element start position (frame fractions)")
    ap.add_argument("--offset", default="0,0", help="extra constant offset added to the element (frame fractions)")
    ap.add_argument("--simplify", type=float, default=0.0, help="thin keys within this tolerance (0 = every frame)")
    ap.add_argument("--out", help="write points / boxes / keyframes JSON here")
    ap.add_argument("--sheet", help="write a contact sheet JPG with the tracked box")
    ap.add_argument("--patch", help="post-build: .wfp to add Filmora's tracking chain + link to")
    ap.add_argument("--track", help="track JSON (from --out) for --patch")
    ap.add_argument("--video-name", help="--patch: part of the tracked video's file name")
    ap.add_argument("--link-text", help="--patch: text content of the element to link")
    ap.add_argument("--link-image", help="--patch: part of the file name of an image to link")
    a = ap.parse_args()
    if a.patch:
        tr = json.load(open(a.track, encoding="utf-8"))
        patch_wfp(a.patch, tr, a.video_name or os.path.splitext(os.path.basename(tr["info"]["video"]))[0],
                  link_text=a.link_text, link_image=a.link_image)
        return
    if not (a.video and a.duration and a.box):
        ap.error("video, --duration and --box are required")
    pts, info = track_points(a.video, a.src_in, a.duration, _floats(a.box, 4), fps=a.fps, method=a.method,
                             smooth=a.smooth, return_info=True)
    W, H = (int(v) for v in a.frame.lower().split("x"))
    pl = placement(a.video, W, H, a.scale, a.x, a.y)
    sxy, off = _floats(a.start_xy, 2), _floats(a.offset, 2)
    kf = to_frame_keyframes(pts, pl, sxy, off, a.simplify)
    res = {"points": pts, "keyframes": kf, "placement": pl, "start_xy": sxy, "offset": off,
           "link_offset": link_offset(pts, pl, sxy), "info": info}
    if a.out:
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"wrote {a.out}: {len(kf['x'])} x / {len(kf['y'])} y keys")
    if a.sheet:
        print("sheet", contact_sheet(a.video, info, a.sheet))
    if not a.out:
        print(json.dumps({"keyframes": kf, "lost": info["lost"]})[:2000])


if __name__ == "__main__":
    main()
