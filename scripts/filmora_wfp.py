"""Write native, editable Wondershare Filmora (.wfp) projects directly as files — no UI automation.

Images (with keyframed scale/position/rotation/opacity), real editable text titles and audio (gain in dB).
Every non-obvious rule here was recovered from Filmora's own files/DLLs and verified on Filmora 16:
  * project_source  = md5("Filmora" + str(project_date_modify))
  * main timeline userData key 140 = md5("Filmora" + timeline_mediaId)
  * keyframe "MD5"  = md5(b"".join(pack("<ddd", time, interpolation, round3(value))))
See ../references/format.md for the full format notes.
"""
import base64, copy, hashlib, json, os, re, struct, subprocess, time, uuid, zipfile

import filmora_paths
TICKS = 10_000_000  # Filmora time unit: 100 ns


# ------------------------------------------------------------------ small encoders
def guid():
    h = uuid.uuid4().hex.upper()
    return "{%s-%s-%s-%s-%s}" % (h[:8], h[8:12], h[12:16].lower(), h[16:20], h[20:])


def thisuid():
    return str(uuid.uuid4())      # random (uuid1 would embed the PC's network address)


def ud(key, raw):
    return {"data": base64.b64encode(raw).decode(), "key": key, "size": len(raw)}


def ud_int(key, v):
    return ud(key, struct.pack("<i", v))


def ud_guid64(key, g):
    return ud(key, g.encode().ljust(64, b"\0"))


def ud_guid(key, g):
    return ud(key, g.encode())


def ud_str(key, s, nul=False):
    return ud(key, s.encode() + (b"\0" if nul else b""))


def aspect(w, h):
    from math import gcd
    g = gcd(w, h)
    return w // g, h // g


def num(v):
    v = float(v)
    return repr(v) if v == int(v) else f"{v:.8f}"


def kf_md5(points):
    b = b"".join(struct.pack("<ddd", t, float(i), int((v + 0.0005) * 1000) / 1000) for t, i, v in points)
    return hashlib.md5(b).hexdigest()


CURVE_Y = {"linear": (0.5, 0.5), "out": (1.0, 0.0), "in": (0.0, 1.0), "inout": (0.0, 0.0)}  # (A right, B left) x delta


def kf_param_curve(points, total=None):
    """points: [(time, value, ease_to_next)] -> Filmora's own Bezier keys (Interpolation 13, verified in Filmora 16):
    _left/_rightDerivative = handle x as a fraction of the segment (0.5), _left/_rightDerivativeY = handle y in value
    units along the segment (delta = steep end, 0 = flat end). out = fast start / soft stop, in = soft start, inout = S.
    Two editable points per move instead of dense linear keys."""
    pts = sorted(points, key=lambda p: p[0])
    items = []
    for n, (t, v, *_) in enumerate(pts):
        s = f'{{"_time": {num(t)},"Interpolation": 13,"_value": {num(v)}'
        if n > 0:
            v0, e0 = pts[n - 1][1], (pts[n - 1][2] if len(pts[n - 1]) > 2 else "linear")
            ly = CURVE_Y.get(e0, CURVE_Y["inout"])[1] * (v - v0)
            s += ',"_leftDerivative": 0.5' + (f',"_leftDerivativeY": {num(ly)}' if ly else "")
        if n < len(pts) - 1:
            v1, e1 = pts[n + 1][1], (pts[n][2] if len(pts[n]) > 2 else "linear")
            ry = CURVE_Y.get(e1, CURVE_Y["inout"])[0] * (v1 - v)
            s += ',"_rightDerivative": 0.5' + (f',"_rightDerivativeY": {num(ry)}' if ry else "")
        items.append(s + "}")
    md5 = kf_md5([(p[0], 13, p[1]) for p in pts])
    out = '{"Version": 3,"ParameterType": 0,"keyframeSets": [' + ",".join(items) + f'],"MD5":"{md5}"'
    if total is not None:
        out = out.replace(f',"MD5":"{md5}"', f',"MD5": "{md5}","_totalTime": {num(total)}')
    return out + "}"


def shift_param(param, delta):
    """Move every key of a keyframe parameter string by delta (same unit), keeping each key's own fields."""
    P = json.loads(param)
    ks = P.get("keyframeSets", [])
    for k in ks:
        k["_time"] = round(k["_time"] + delta, 8)
    P["MD5"] = kf_md5([(k["_time"], k.get("Interpolation", 1), k["_value"]) for k in ks])
    return json.dumps(P, separators=(",", ":"))


def kf_param(points, interp=1, total=None):
    """points: [(time, value)] already in the param's own time unit. Points with a third element (ease to the next
    point: out | in | inout | linear) are written as native Filmora curves (kf_param_curve)."""
    if any(len(p) > 2 and p[2] != "linear" for p in points):
        return kf_param_curve(points, total)
    pts = sorted((p[0], p[1]) for p in points)
    items = []
    for n, (t, v) in enumerate(pts):
        s = f'{{"_time": {num(t)},"Interpolation": {interp},"_value": {num(v)}'
        if interp == 1 and len(pts) > 1:
            if n > 0:
                (t0, v0) = pts[n - 1]
                s += f',"_leftDerivative": {num((v - v0) / (t - t0) if t != t0 else 0)}'
            if n < len(pts) - 1:
                (t1, v1) = pts[n + 1]
                s += f',"_rightDerivative": {num((v1 - v) / (t1 - t) if t1 != t else 0)}'
        items.append(s + "}")
    md5 = kf_md5([(t, interp, v) for t, v in pts])
    out = '{"Version": 3,"ParameterType": 0,"keyframeSets": [' + ",".join(items) + f'],"MD5":"{md5}"'
    if total is not None:
        out = out.replace(f',"MD5":"{md5}"', f',"MD5": "{md5}","_totalTime": {num(total)}')
    return out + "}"


def speed_param(total_sec):
    md5 = kf_md5([(0.0, 6, 1.0), (total_sec, 6, 1.0)])
    return ('{"Version": 3,"ParameterType": 0,"keyframeSets": [{"_time": 0.0,"Interpolation": 6,"_value": 1.0},'
            f'{{"_time": {num(total_sec)},"Interpolation": 6,"_value": 1.0}}],"MD5": "{md5}","_totalTime": {num(total_sec)}}}')


BLEND_MODES = ["Normal", "Darken", "Multiply", "Color Burn", "Linear Burn", "Lighten", "Screen", "Color Dodge",
               "Linear Dodge", "Overlay", "Soft Light", "Hard Light", "Vivid Light", "Linear Light", "Pin Light",
               "Hard Mix", "Difference", "Exclusion"]   # Filmora 16 Compositing > Blend Mode, stored by name in pipBuf


def set_blend(clip, mode):
    """Blend mode of a video/image/title clip (verified: Filmora saves "BlendMode": "<name>", Normal = 0)."""
    names = {m.lower().replace(" ", ""): m for m in BLEND_MODES}
    key = str(mode).lower().replace(" ", "").replace("_", "").replace("-", "")
    if key not in names:
        raise ValueError(f"unknown blend mode {mode!r}; choose from {', '.join(BLEND_MODES)}")
    d = json.loads(clip["pipBuf"])
    d["BlendMode"] = 0 if names[key] == "Normal" else names[key]
    s = json.dumps(d, separators=(",", ":"))
    clip["pipBuf"], clip["pipBufSize"] = s, len(s.encode()) + 1
    return clip


def portrait_cutout(clip, feather=0.0, edge_thickness=0.0):
    """Filmora's AI Portrait Cutout (removes the background behind people). Verified: written from a file, Filmora
    computes the cutout itself when the project opens, on the PC, without AI credits."""
    for ch in clip["effectChainList"]:
        if ch["name"] == "Effect":
            ch["effectList"] = [e for e in ch["effectList"] if e.get("display") != "HumanSegmentationHairEffect"]
            ch["effectList"].append({
                "display": "HumanSegmentationHairEffect", "id": "B4CF1D0F-D10A-1613-6EF4-A4F0D0364978",
                "paramList": [{"fxParam": {"paramType": 5, "unValue": 0}, "name": "isHaveHumanSegmentationHairCache"}],
                "placeholder": False, "placeholderStatus": 0, "thisUId": thisuid(), "type": 3,
                "userData": [ud_guid64(3, guid()), ud(36880, b"0\0"), ud(7, b"\0")]})
    clip["humanseg_hair"] = {"edge_thickness": float(edge_thickness), "feather": float(feather), "mode": 0,
                             "status": 1, "version": 1.0}
    return clip


def pip_buf(opacity=100.0, opacity_kf=None):
    d = {"Algorithm": "Bilinear", "BlendMode": 0, "BlenderName": "video/blender/simple-pip", "Enable": True, "Opacity": opacity}
    if opacity_kf:
        d["OpacityKeyFrame"] = kf_param(opacity_kf)
    s = json.dumps(d, separators=(",", ":"))
    return s, len(s.encode()) + 1


def fresh_uids(obj):
    """Give every effect/clip a new thisUId and every GUID userData (key 3) a new GUID."""
    if isinstance(obj, dict):
        if "thisUId" in obj:
            obj["thisUId"] = thisuid()
        for k, v in obj.items():
            if k == "userData" and isinstance(v, list):
                for i, u in enumerate(v):
                    if u.get("key") == 3 and u.get("size") == 64:
                        v[i] = ud_guid64(3, guid())
            else:
                fresh_uids(v)
    elif isinstance(obj, list):
        for v in obj:
            fresh_uids(v)


def set_ud(clip, key, entry):
    clip["userData"] = [u for u in clip.get("userData", []) if u["key"] != key] + [entry]


def get_ud(clip, key):
    for u in clip.get("userData", []):
        if u["key"] == key:
            return base64.b64decode(u["data"])
    return None


def transform_effect(clip):
    for ch in clip["effectChainList"]:
        for e in ch["effectList"]:
            if e["id"] == "video/effect/transform":
                return e
    raise KeyError("transform")


def set_params(effect, values):
    plist = [p for p in effect.get("paramList", []) if p["name"] not in values]
    for name, (ptype, val) in values.items():
        plist.append({"fxParam": {"paramType": ptype, "unValue": val}, "name": name})
    effect["paramList"] = plist


def ffprobe(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                   "stream=sample_rate,channels,bit_rate:format=duration,bit_rate", "-of", "json", path])
    return json.loads(out)


# ------------------------------------------------------------------ templates (bundled in assets/templates.json)
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "templates.json")


class Templates:
    """Clip/track/title skeletons cloned from real Filmora projects (see extract_templates.py)."""
    def __init__(self, path=TEMPLATES):
        t = json.load(open(path, encoding="utf-8"))
        self.doc = dict(t["doc"], resources=[], timelineInfos=[])
        self.info66 = t["info"]
        self.main_tl = dict(t["main_tl"], trackInfos=[])
        self.track_audio_main = t["track_audio_main"]
        self.track_audio_pair = t["track_audio_pair"]
        self.track_video = t["track_video"]
        self.wrapper = t["wrapper"]
        self.title_tl = t["title_tl"]
        self.thumb_tl = base64.b64decode(t["thumb_tl"]) if t.get("thumb_tl") else b""
        self.func_extra = b'{"9":"3"}'
        self.img_clip, self.img_res = t["img_clip"], t["img_res"]
        self.wav_clip, self.wav_res = t["wav_clip"], t["wav_res"]


# ------------------------------------------------------------------ project builder
class Project:
    def __init__(self, name, width=1080, height=1920, fps=30):
        self.T = Templates()
        self.name, self.W, self.H, self.fps = name, width, height, fps
        self.medias = {}          # path -> dict(id, kind, res, media_json, info)
        self.layers = []          # list of lists of clips (video lanes, bottom->top)
        self.audio_lanes = []     # list of lists of audio clips
        self.title_tls = []       # title timelines
        self.clip_map = {}        # clip guid -> media id (for extra.json)
        self.next_tl_id = 10
        self.main_tl_id = 9
        self.duration = 0

    def ticks(self, sec):
        return int(round(round(sec * self.fps) * TICKS / self.fps))

    # ---------------- media registry
    def _media(self, path, kind):
        path = os.path.abspath(path).replace("\\", "/")
        if path in self.medias:
            return self.medias[path]
        mid = guid()
        src_uuid = str(uuid.uuid4())
        name = os.path.splitext(os.path.basename(path))[0]
        if kind == "image":
            from PIL import Image
            w, h = Image.open(path).size
            res = copy.deepcopy(self.T.img_res)
            res.update(filename="file:/" + path, sourceUuid=src_uuid)
            vs = res["vidStreamInfo"][0]
            vs.update(width=w, height=h, xRatio=w, yRatio=h, alphaChannel=1, bitsDepth=32)
            vs["frameRate"] = {"den": 1, "num": self.fps}
            vs["maxFrameRate"] = {"den": 1, "num": self.fps}
            mj = {"version": "1.1.7", "file_name": path, "sourceInfo": {"basicInfo": {"streamType": 5, "fourCC": res["fourCC"], "mediaLength": 0, "programCount": 0, "videoStreamCount": 1, "audioStreamCount": 0, "subPicStreamCount": 0, "bitRate": 0, "createDate": 0},
                  "vidStreamInfos": [{"vidStreamId": 0, "fourCC": 0, "streamLength": 0, "bitRate": 0, "startTimestamp": 0, "timestampOffset": 0, "videoScanType": 0, "width": w, "height": h, "frameRate": {"den": 1, "num": self.fps}, "maxFrameRate": {"den": 1, "num": self.fps}, "totalFrames": 0, "xRatio": w, "yRatio": h, "rotation": 0, "flipType": 0, "gpsLatitude": 0.0, "gpsLongitude": 0.0, "cameraMaker": "None", "cameraModel": "None", "exposureTime": 0.0, "premultiAlphaTypePhoto": -1, "transferCharacteristics": 0, "maxGopSize": -1, "lastframeRate": {"den": 1, "num": self.fps}, "alphaChannel": 1, "isDolbyVision": 0, "colorSpaceSource": 0}], "recordInfos": {}}}
            info = {"download_url": path, "id": mid, "media_type": 16, "media_length": 50000000, "name": name}
        else:
            pr = ffprobe(path)
            st = pr["streams"][0]
            dur = float(pr["format"]["duration"])
            sr, ch = int(st.get("sample_rate", 44100)), int(st.get("channels", 2))
            br = int(pr["format"].get("bit_rate", sr * ch * 16))
            res = copy.deepcopy(self.T.wav_res)
            res.update(filename="file:/" + path, sourceUuid=src_uuid, mediaLength=int(dur * TICKS), bitRate=br, createDate=int(time.time()))
            a = res["audStreamInfo"][0]
            a.update(sampleRate=sr, channels=ch, duration=dur + 1e-8, streamLength=int(dur * TICKS), bitRate=br, bytesPerSecond=br // 8)
            mj = {"version": "1.1.7", "file_name": path, "sourceInfo": {"basicInfo": {"streamType": 3, "fourCC": res["fourCC"], "mediaLength": int(dur * TICKS), "programCount": 1, "videoStreamCount": 0, "audioStreamCount": 1, "subPicStreamCount": 0, "bitRate": br, "createDate": res["createDate"]},
                  "audStreamInfos": [{"audStreamId": 0, "fourCC": a["fourCC"], "streamLength": int(dur * TICKS), "sampleRate": sr, "channels": ch, "layout": 0, "duration": dur + 1e-8, "bytesPerSecond": br // 8, "bitRate": br, "bitDepth": 16, "description": "Uncompressed PCM"}], "recordInfos": {}}}
            info = {"download_url": path, "id": mid, "media_type": 4, "media_length": int(dur * TICKS), "name": name}
        info.update({"mediaCreationInfo": "{\"creationType\":0}", "import_time": int(time.time()),
                     "src_md5": hashlib.md5(open(path, "rb").read()).hexdigest(), "stream_idx": -1 if kind == "image" else 0,
                     "mark_info_list": [{"mark_in": -1, "mark_out": -1}], "scence_info": []})
        m = dict(id=mid, kind=kind, res=res, media_json=mj, info=info, path=path, name=name)
        self.medias[path] = m
        return m

    # ---------------- clip factories
    def image_clip(self, path, start, end, x=0.5, y=0.5, scale=100.0, scale_y=None, rot=0.0, opacity=100.0,
                   kf_scale=None, kf_scale_x=None, kf_x=None, kf_y=None, kf_rot=None, kf_opacity=None):
        """x,y: centre in 0..1 (y down). scale: % of fit-to-frame. kf_* : [(sec_from_clip_start, value)]."""
        m = self._media(path, "image")
        c = copy.deepcopy(self.T.img_clip)
        fresh_uids(c)
        dur = self.ticks(end) - self.ticks(start)
        src_in = 3600 * TICKS
        c.update(filename=m["res"]["filename"], sourceUuid=m["res"]["sourceUuid"], tlBegin=self.ticks(start),
                 tlEnd=self.ticks(end), inPoint=src_in, outPoint=src_in + dur)
        c["speed"] = {"offset": 3600.0, "offsetEnd": 3600.0 + dur / TICKS, "reverse": False, "speedParam": speed_param(86400.0)}
        set_ud(c, 50, ud_str(50, m["name"]))
        set_ud(c, 10, ud_guid(10, m["id"]))
        set_ud(c, 6, ud_int(6, self.main_tl_id))
        for k in (73, 74):
            raw = get_ud(c, k)
            if raw:
                set_ud(c, k, ud(k, raw.decode().replace("PLACEHOLDER", m["path"]).encode()))
        sy = scale if scale_y is None else scale_y
        tf = transform_effect(c)
        set_params(tf, {"Scale_x": (3, float(scale)), "Scale_y": (3, float(sy)), "Position_x": (3, float(x)),
                        "Position_y": (3, float(y)), "Rotation": (3, float(rot))})
        self._keyframes(tf, src_in / TICKS, kf_scale=kf_scale, kf_scale_x=kf_scale_x, kf_x=kf_x, kf_y=kf_y, kf_rot=kf_rot)
        c["pipBuf"], c["pipBufSize"] = pip_buf(opacity, [(src_in + self.ticks(q[0]), *q[1:]) for q in kf_opacity] if kf_opacity else None)
        self.clip_map[get_ud(c, 3).rstrip(b"\0").decode()] = m["id"]
        return c

    def _keyframes(self, tf, base_sec, kf_scale=None, kf_scale_x=None, kf_x=None, kf_y=None, kf_rot=None):
        maps = []
        def add(name, pts):
            maps.append({"key": 3, "keyFrame": {"parameter": kf_param([(base_sec + self.ticks(q[0]) / TICKS, *q[1:]) for q in pts])}, "name": name})
        if kf_scale:
            add("Scale_x", kf_scale); add("Scale_y", kf_scale)
        if kf_scale_x:
            add("Scale_x", kf_scale_x)
        if kf_x:
            add("Position_x", kf_x)
        if kf_y:
            add("Position_y", kf_y)
        if kf_rot:
            add("Rotation", kf_rot)
        if maps:
            tf["paramMapList"] = maps

    def title_clip(self, text, start, end, x=0.5, y=0.5, font="Alexandria Black", font_size=60.0, color=0xFFFFFF,
                   text_width=None, lines=1, scale=100.0, opacity=100.0, kf_scale=None, kf_x=None, kf_y=None, kf_rot=None, kf_opacity=None):
        """A real, editable Filmora text. text_width: measured width of the text at 1px CSS (for the box)."""
        dur = self.ticks(end) - self.ticks(start)
        tl_id = self.next_tl_id
        self.next_tl_id += 1
        # inner title timeline
        ttl = copy.deepcopy(self.T.title_tl)
        fresh_uids(ttl)
        ttl["timelineId"] = tl_id
        ttl["frameRate"] = {"den": 1, "num": self.fps}
        ttl["resolutionWidth"], ttl["resolutionHeight"] = self.W, self.H
        ttl["aspectRatioX"], ttl["aspectRatioY"] = aspect(self.W, self.H)
        ttl["userData"] = [u for u in ttl["userData"] if u["key"] not in (11000, 3)] + [ud_guid64(11000, guid()), ud_guid64(3, guid())]
        inner = ttl["trackInfos"][0]["clipList"][0]
        inner.pop("inAnimation", None)
        for ch in inner["effectChainList"]:
            if ch["name"] == "Effect":
                ch["effectList"] = []
        inner.update(tlBegin=0, tlEnd=dur, inPoint=0, outPoint=dur)
        s = json.loads(inner["scriptBuf"])
        css_px = 3.0 * font_size * self.W / 1920   # Filmora: box height = 3 x FontSize x (frame width / 1920)
        # glyphs render at 1 em = 1.5 x FontSize x W/1920 (measured from a screenshot); box = 1.33 x the real text width,
        # the same proportion the projects confirmed by the user had (they were measured with a fallback font)
        sx = (text_width or 0.6 * len(text)) * (2.0 * font_size * self.W / 1920) / self.W
        sy = css_px * (1 + (lines - 1) * 1.15) / self.H
        s.update(Text=text, PosX=0.5, PosY=0.5, ScaleX=sx, ScaleY=sy, TextScale=font_size / 60.0, ViewSize=f"{self.W}:{self.H}")
        s["Layout"]["TextAlign"] = "center"
        b = s["TextData"][0]
        b["CharData"] = text
        bb = b["Basic"]
        bb.update(FontName=font, FontSize=font_size, FontHSize=font_size, FontVSize=font_size, FontBold=0, TextColor=[{"Color": color}])
        b["Border"]["Enable"] = 0
        b["Shadow"]["Enable"] = 0
        # the template text carried an extra stroke layer (ExternAttr: blurred 21 px border) -> clean, flat text
        for ext in s.get("ExternAttr", []):
            ext.get("Border", {})["Enable"] = 0
            ext.get("Shadow", {})["Enable"] = 0
            ext.get("Shadow", {})["InEnable"] = 0
            ext.get("Basic", {})["Enable"] = 0
        s.get("Glow", {})["enable"] = 0
        s.get("Background", {})["Enable"] = 0
        inner["scriptBuf"] = json.dumps(s, ensure_ascii=False, separators=(",", ":"))
        inner["scriptBufSize"] = len(inner["scriptBuf"].encode()) + 1
        tf = transform_effect(inner)
        set_params(tf, {"Scale_x": (3, sx * 100), "Scale_y": (3, sy * 100), "Position_x": (3, 0.5), "Position_y": (3, 0.5)})
        set_ud(inner, 6, ud_int(6, tl_id))
        set_ud(inner, 55, ud_str(55, json.dumps({"textBoundHeight": sy, "textBoundWidth": sx})))
        inner["pipBuf"], inner["pipBufSize"] = pip_buf(100.0)
        self.title_tls.append(ttl)
        # wrapper on the main timeline
        w = copy.deepcopy(self.T.wrapper)
        fresh_uids(w)
        w.update(timelineId=tl_id, tlBegin=self.ticks(start), tlEnd=self.ticks(end), inPoint=0, outPoint=dur)
        # keep the built-in title resource reference (key 10/12) from the user's project; content comes from scriptBuf
        set_ud(w, 6, ud_int(6, self.main_tl_id))
        tfw = transform_effect(w)
        set_params(tfw, {"Scale_x": (3, float(scale)), "Scale_y": (3, float(scale)), "Position_x": (3, float(x)), "Position_y": (3, float(y))})
        self._keyframes(tfw, 0.0, kf_scale=kf_scale, kf_x=kf_x, kf_y=kf_y, kf_rot=kf_rot)
        w["pipBuf"], w["pipBufSize"] = pip_buf(opacity, [(self.ticks(q[0]), *q[1:]) for q in kf_opacity] if kf_opacity else None)
        self.clip_map[get_ud(w, 3).rstrip(b"\0").decode()] = get_ud(w, 10).decode()
        return w

    def audio_clip(self, path, start, dur=None, gain_db=-10.0, fade_out=0.0, src_in=0.0):
        """src_in: seconds into the file where the clip starts (e.g. one hit out of a multi-hit SFX file)."""
        m = self._media(path, "audio")
        full = m["info"]["media_length"] / TICKS
        src_in = max(0.0, min(src_in, full - 0.02))
        d = min(full - src_in, dur or full)
        c = copy.deepcopy(self.T.wav_clip)
        fresh_uids(c)
        n, src = self.ticks(d), int(round(src_in * TICKS))
        c.update(filename=m["res"]["filename"], sourceUuid=m["res"]["sourceUuid"], tlBegin=self.ticks(start),
                 tlEnd=self.ticks(start) + n, inPoint=src, outPoint=src + n)
        c["speed"] = {"offset": src / TICKS, "offsetEnd": (src + n) / TICKS, "reverse": False, "speedParam": speed_param(round(full, 2))}
        set_ud(c, 50, ud_str(50, m["name"]))
        set_ud(c, 10, ud_guid(10, m["id"]))
        set_ud(c, 6, ud_int(6, self.main_tl_id))
        for ch in c["effectChainList"]:
            for e in ch["effectList"]:
                if e["id"] == "audio/effect/volume":
                    set_params(e, {"VolumeGain": (2, float(gain_db))})
                if e["id"] == "audio/effect/fade" and fade_out:
                    set_params(e, {"FadeOutTime": (2, float(fade_out))})
        self.clip_map[get_ud(c, 3).rstrip(b"\0").decode()] = m["id"]
        return c

    # ---------------- layout
    def add_lane(self, clips):
        self.layers.append(sorted(clips, key=lambda c: c["tlBegin"]))

    def add_audio_lane(self, clips):
        self.audio_lanes.append(sorted(clips, key=lambda c: c["tlBegin"]))

    # ---------------- write
    def save(self, out_path=None):
        T = self.T
        doc = copy.deepcopy(T.doc)
        main = copy.deepcopy(T.main_tl)
        main["frameRate"] = {"den": 1, "num": self.fps}
        main["resolutionWidth"], main["resolutionHeight"] = self.W, self.H
        main["aspectRatioX"], main["aspectRatioY"] = aspect(self.W, self.H)
        tl_uuid = guid()
        main["userData"] = [u for u in main["userData"] if u["key"] not in (11000, 30309, 30306, 3, 140)]
        main["userData"] += [ud_guid64(11000, tl_uuid), ud_guid(30309, tl_uuid), ud_guid64(3, guid()),
                             ud_str(30306, json.dumps([{"index": 0, "isActive": True, "pageIndex": 1, "timelineId": tl_uuid}], separators=(",", ":")))]
        # Stand-alone audio tracks (music/SFX) come first: trackType 2, no trackTag, userData {12000: 45}.
        # Audio tracks paired with a video track (userData key 20 = index of that video track) only hold the
        # audio that belongs to that video's clips — Filmora does not show free audio placed there.
        tracks = []
        for lane in (self.audio_lanes or [[]]):
            a = dict(copy.deepcopy(T.track_audio_main), clipList=lane, uuid=thisuid())
            a.pop("trackTag", None)
            a["userData"] = [ud_int(12000, 45)]
            tracks.append(a)
        tag = 1
        for lane in self.layers:
            a = copy.deepcopy(T.track_audio_pair)
            a.update(uuid=thisuid(), trackTag=tag, clipList=[])
            a["userData"] = [ud_int(20, len(tracks) + 1)]
            v = copy.deepcopy(T.track_video)
            v.update(uuid=thisuid(), trackTag=tag + 1, clipList=lane)
            tracks += [a, v]
            tag += 2
        main["trackInfos"] = tracks
        end = max([c["tlEnd"] for t in tracks for c in t["clipList"]] + [0])
        doc["timelineInfos"] = [main] + self.title_tls
        doc["resources"] = [m["res"] for m in self.medias.values()]
        doc["currentTimelineId"] = self.main_tl_id
        doc["serialNumber"] = self.next_tl_id
        tl_media = guid()
        now = int(time.time())
        # integrity stamps Filmora verifies on open (recovered from DataModel.dll)
        main["userData"].append(ud_str(140, hashlib.md5(("Filmora" + tl_media).encode()).hexdigest()))
        info = copy.deepcopy(T.info66)
        out_path = os.path.abspath(out_path or os.path.join(filmora_paths.project_dir(), self.name + ".wfp"))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        proj_guid = guid()
        info.update(project_file_name=self.name, project_date_create=now, project_date_modify=now,
                    project_timeline_duration=end, project_current_position=0, project_timeline_framerate=[self.fps, 1],
                    project_timeline_resolution=[self.W, self.H], project_timeline_ratio=list(aspect(self.W, self.H)), timeline_mediaId=tl_media, project_guid=proj_guid,
                    proj_zip_save_path=out_path.replace("\\", "/"),
                    proj_cover_proj_path="", project_source=hashlib.md5(f"Filmora{now}".encode()).hexdigest())
        ed, vbl = filmora_paths.installed_versions()      # stamp with the installed version (else "back up?" on every open)
        if ed:
            info.update(project_editor_create_version=ed, project_editor_modify_version=ed)
        if vbl:
            info.update(vbl_create_version=vbl, vbl_modify_version=vbl)
        # medias_info.json (Filmora uses repeated "media_item" keys -> written by hand)
        folder = "".join(f',"media_item":"{m["id"]}"' for m in self.medias.values())
        items = {m["id"]: m["info"] for m in self.medias.values()}
        items[tl_media] = {"name": "Untitle", "download_url": "", "id": tl_media, "timeline_uuid": tl_uuid, "media_type": 1048576,
                           "create_time": now, "duration": end, "enable_modify_mediaId": 0, "mark_info_list": [{"mark_in": -1, "mark_out": -1}]}
        mi = ('{"media_structure":{"visible":"true","SerializeDataOnlyProjectUsered":"false","Folder":{"visible":"true","SerializeDataOnlyProjectUsered":"false"'
              + folder + f'}},"media_item":"{tl_media}"}},"media_items":' + json.dumps(items, ensure_ascii=False, separators=(",", ":")) + "}")
        extra = {"fontNameInfo": [], "usedBizFont": [], "usedTemplateResInfo": {},
                 "mediaClipsMapInfo": {g: {"mediaId": mid, "subClips": {}} for g, mid in self.clip_map.items()},
                 "allMarkersInfo": {"beatDetectInfo": {}}, "pendingMarkersInfo": {}, "highlightInfo": {}, "TextSentence": {"TextSentence": []}}
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
            for m in self.medias.values():
                z.writestr(f"ProjectFolder/Medias/{m['id']}/media.json", json.dumps(m["media_json"], ensure_ascii=False, separators=(",", ":")))
            z.writestr(f"ProjectFolder/Medias/{tl_media}/thumbnail.png", T.thumb_tl)
            z.writestr("ProjectFolder/Anon/AppData/Windows/functionExtraData.json", T.func_extra)
            z.writestr("ProjectFolder/Medias/medias_info.json", mi)
            z.writestr(f"ProjectFolder/Medias/{tl_media}/extra.json", json.dumps(extra, ensure_ascii=False, separators=(",", ":")))
            z.writestr(f"ProjectFolder/Medias/{tl_media}/timeline.wesproj", json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
            z.writestr("ProjectFolder/project_info.json", json.dumps(info, ensure_ascii=False, indent=4))
        return out_path, end
