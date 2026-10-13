"""Video clips, effect layers, clip filters and transitions for filmora_wfp.Project.

Effects/filters/transitions are built from the catalog of what is installed on THIS machine
(catalog_filmora.py). Any catalog entry works with an empty paramList (= Filmora defaults).
"""
import copy, json, os, subprocess, time, uuid

from filmora_wfp import (TICKS, Project, Templates, fresh_uids, get_ud, guid, pip_buf, set_params, set_ud, speed_param,
                         thisuid, transform_effect, ud, ud_guid, ud_guid64, ud_int, ud_str)
import catalog_filmora

_T = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "templates.json"), encoding="utf-8"))


def probe_video(path):
    out = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_tag_string,pix_fmt,width,height,r_frame_rate,nb_frames,bit_rate,sample_rate,channels:format=duration,bit_rate",
         "-of", "json", path]))
    v = next(s for s in out["streams"] if s["codec_type"] == "video")
    a = next((s for s in out["streams"] if s["codec_type"] == "audio"), None)
    num, den = map(int, v["r_frame_rate"].split("/"))
    return dict(w=int(v["width"]), h=int(v["height"]), fps=(num, den), dur=float(out["format"]["duration"]),
                frames=int(v.get("nb_frames", 0) or 0), vbr=int(v.get("bit_rate", 0) or 0), br=int(out["format"].get("bit_rate", 0) or 0), audio=a,
                alpha=any(k in v.get("pix_fmt", "") for k in ("yuva", "rgba", "argb", "bgra", "abgr", "gbrap", "ya")),
                tag=v.get("codec_tag_string", ""))


def res_info(c):
    return json.dumps({"id": c["res_id"], "infoType": 7, "is_custom": 0, "smart_resource": 0, "sale_mode": c["sale_mode"],
                       "source": c["source"], "res_sub_type": 0, "res_type": c["res_type"], "smart_res_relative_path": "",
                       "related_slug": "", "name": c["slug"], "user_string": {}, "resourceRate": -1}, separators=(",", ":"))


def effect_entry(name, params=None):
    """An effect/filter object for a clip's 'Effect' chain. params: {name: (paramType, value)} or None for defaults."""
    c = catalog_filmora.find(name)
    e = {"display": c["name"], "id": c["guid"], "placeholder": False, "placeholderStatus": 0, "thisUId": thisuid(), "type": 3,
         "userData": [ud_guid64(3, guid()), ud(7, b"\x00"), ud(12, res_info(c).encode()), ud_str(50, c["name"])]}
    if params:
        e["paramList"] = [{"fxParam": {"paramType": t, "unValue": v}, "name": n} for n, (t, v) in params.items()]
    return e


class FxProject(Project):
    def _video_media(self, path):
        path = os.path.abspath(path).replace("\\", "/")
        if path in self.medias:
            return self.medias[path]
        pr = probe_video(path)
        mid, ticks = guid(), int(pr["dur"] * TICKS)
        name = os.path.splitext(os.path.basename(path))[0]
        res = copy.deepcopy(_T["video_res"])
        now = int(time.time())
        res.update(filename="file:/" + path, sourceUuid=str(uuid.uuid4()), mediaLength=ticks, bitRate=pr["br"], createDate=now, modifyDate=now)
        vs = res["vidStreamInfo"][0]
        vs.update(width=pr["w"], height=pr["h"], xRatio=pr["w"], yRatio=pr["h"], streamLength=ticks, totalFrames=pr["frames"], bitRate=pr["vbr"])
        vs["frameRate"] = {"den": pr["fps"][1], "num": pr["fps"][0]}
        if len(pr["tag"]) == 4 and pr["tag"].isascii() and pr["tag"].isalnum():
            vs["fourCC"] = int.from_bytes(pr["tag"].encode(), "little")      # real codec (e.g. ap4h = ProRes 4444)
        if pr["alpha"]:                                                       # transparent layer (straight alpha)
            vs["alphaChannel"], res["alphaPremultiply"] = 1, 0
        vs["maxFrameRate"] = {"den": 1000 * pr["fps"][1], "num": 1000 * pr["fps"][0]}
        if pr["audio"]:
            a = res["audStreamInfo"][0]
            a.update(sampleRate=int(pr["audio"].get("sample_rate", 48000)), channels=int(pr["audio"].get("channels", 2)), duration=pr["dur"] + 1e-8, streamLength=ticks)
        else:
            res["audStreamInfo"], res["audioStreamCount"] = [], 0
        vsi = {"vidStreamId": 0, "fourCC": vs["fourCC"], "streamLength": ticks, "bitRate": pr["vbr"], "startTimestamp": 0, "timestampOffset": 0,
               "videoScanType": 2, "width": pr["w"], "height": pr["h"], "frameRate": vs["frameRate"], "maxFrameRate": vs["maxFrameRate"],
               "totalFrames": pr["frames"], "xRatio": pr["w"], "yRatio": pr["h"], "rotation": 0, "flipType": 0, "gpsLatitude": 0.0, "gpsLongitude": 0.0,
               "cameraMaker": "None", "cameraModel": "None", "exposureTime": 0.0, "premultiAlphaTypePhoto": -1, "transferCharacteristics": 0,
               "maxGopSize": 250, "lastframeRate": vs["frameRate"], "alphaChannel": 1 if pr["alpha"] else 0, "isDolbyVision": 0, "colorSpaceSource": 1}
        asi = [{"audStreamId": 1, "fourCC": 541278529, "streamLength": ticks, "sampleRate": res["audStreamInfo"][0]["sampleRate"],
                "channels": res["audStreamInfo"][0]["channels"], "layout": 0, "duration": pr["dur"] + 1e-8, "bytesPerSecond": 17500,
                "bitRate": 128000, "bitDepth": 16, "description": "Advanced Audio Codec"}] if pr["audio"] else []
        mj = {"version": "1.1.7", "file_name": path, "sourceInfo": {"basicInfo": {"streamType": 2, "fourCC": res["fourCC"], "mediaLength": ticks,
              "programCount": 1, "videoStreamCount": 1, "audioStreamCount": res["audioStreamCount"], "subPicStreamCount": 0, "bitRate": pr["br"],
              "createDate": now}, "vidStreamInfos": [vsi], "audStreamInfos": asi, "recordInfos": {}}}
        info = {"download_url": path, "id": mid, "media_type": 8, "media_length": ticks, "name": name, "mediaCreationInfo": "{\"creationType\":0}",
                "import_time": now, "src_md5": uuid.uuid4().hex, "stream_idx": 0, "mark_info_list": [{"mark_in": -1, "mark_out": -1}], "scence_info": []}
        m = dict(id=mid, kind="video", res=res, media_json=mj, info=info, path=path, name=name, dur=pr["dur"])
        self.medias[path] = m
        return m

    def video_clip(self, path, start, end, src_in=0.0, scale=100.0, x=0.5, y=0.5, rot=0.0, opacity=100.0,
                   kf_scale=None, kf_x=None, kf_y=None, kf_rot=None, kf_opacity=None, filters=()):
        """Muted video clip (its own sound is not placed). src_in: seconds into the source; kf_* times from clip start."""
        m = self._video_media(path)
        c = copy.deepcopy(_T["video_clip"])
        fresh_uids(c)
        dur = self.ticks(end) - self.ticks(start)
        src = int(round(src_in * TICKS))
        c.update(filename=m["res"]["filename"], sourceUuid=m["res"]["sourceUuid"], tlBegin=self.ticks(start), tlEnd=self.ticks(end),
                 inPoint=src, outPoint=src + dur)
        c["speed"] = {"offset": src / TICKS, "offsetEnd": (src + dur) / TICKS, "reverse": False, "speedParam": speed_param(round(m["dur"], 2))}
        set_ud(c, 50, ud_str(50, m["name"]))
        set_ud(c, 10, ud_guid(10, m["id"]))
        set_ud(c, 6, ud_int(6, self.main_tl_id))
        tf = transform_effect(c)
        set_params(tf, {"Scale_x": (3, float(scale)), "Scale_y": (3, float(scale)), "Position_x": (3, float(x)),
                        "Position_y": (3, float(y)), "Rotation": (3, float(rot))})
        self._keyframes(tf, src / TICKS, kf_scale=kf_scale, kf_x=kf_x, kf_y=kf_y, kf_rot=kf_rot)
        c["pipBuf"], c["pipBufSize"] = pip_buf(opacity, [(src + self.ticks(t), v) for t, v in kf_opacity] if kf_opacity else None)
        for f in filters:
            self.filter(c, f)
        self.clip_map[get_ud(c, 3).rstrip(b"\0").decode()] = m["id"]
        return c

    def fx(self, name, start, end, params=None):
        """Effect layer (clip type 8): applies to everything below it during [start, end]."""
        c = copy.deepcopy(_T["fx_clip"])
        fresh_uids(c)
        cat = catalog_filmora.find(name)
        for ch in c["effectChainList"]:
            if ch["name"] == "Effect":
                ch["effectList"] = [effect_entry(name, params)]
        dur = self.ticks(end) - self.ticks(start)
        c.update(tlBegin=self.ticks(start), tlEnd=self.ticks(end), inPoint=3600 * TICKS, outPoint=3600 * TICKS + dur)
        set_ud(c, 6, ud_int(6, self.main_tl_id))
        set_ud(c, 10, ud(10, cat["slug"].encode()))
        self.clip_map[get_ud(c, 3).rstrip(b"\0").decode()] = cat["slug"]
        return c

    def filter(self, clip, name, params=None):
        """Attach an installed filter/effect to one clip (video, image or title)."""
        e = effect_entry(name, params)
        for ch in clip["effectChainList"]:
            if ch["name"] == "Effect":
                ch["effectList"].append(e)
                return clip
        clip["effectChainList"].insert(1, {"effectList": [e], "name": "Effect"})
        return clip

    def transition(self, clip_a, name, dur=0.4):
        """Centred transition on the cut after clip_a. The next clip must start exactly at clip_a's end on the same
        track, and both clips need dur/2 of spare source footage beyond the cut (handles)."""
        c = catalog_filmora.find(name)
        if not c["is_transition"]:
            raise ValueError(f"'{name}' is not a transition")
        half = self.ticks(dur) // 2
        clip_a["postTransition"] = {"display": c["name"], "id": c["guid"], "placeholder": False, "placeholderStatus": 0,
                                    "thisUId": thisuid(), "tlBegin": clip_a["tlEnd"] - half, "tlEnd": clip_a["tlEnd"] + half, "type": 5,
                                    "userData": [ud_guid64(3, guid()), ud(12, res_info(c).encode()), ud_int(80, 1), ud_int(8, 3)]}
        return clip_a["postTransition"]
