"""Filmora's native SUBTITLE TRACK (the one SRT import / Speech-to-Text creates): one type-22 clip whose
`subtitleSource` holds every cue, editable in Filmora's subtitle editor and exportable back to .srt.

    from filmora_fx import FxProject
    from filmora_subtitle import subtitle_track, from_srt
    p = FxProject("My Reel", 1080, 1920, 30)
    ...                                                   # video / image lanes first
    subtitle_track(p, from_srt("talk.srt"), font="<the user's chosen font>", size=44, color="#FFFFFF", y=0.72)
    p.save("G:/.../My Reel.wfp")                          # also writes "My Reel.srt" next to it (the track's source)

    python filmora_subtitle.py talk.srt          # prints the parsed cues (check timing/text before building)

Model (decoded from projects saved by Filmora):
  * a normal video track (trackType 1 + its paired audio track) holding ONE clip of type 22 (userData 1 = 29);
  * clip.subtitleSource = JSON string {AniTemplates, End, Items, Layout, Start, Templates, Version}; Items =
    [{AniTemplate, Content, End, Layer, Start, Template}] with Start/End in ticks (1e7/s) relative to the clip start;
  * Templates[name] = a full text style (same engine as titles: font, size, colour, background box, stroke, shadow,
    PosX/PosY/ScaleX/ScaleY); AniTemplates[name] = the transform (position/box scale) + optional in/out animation;
  * the clip references a media item of type 16384 = the .srt file (medias_info.json + Medias/<id>/media.json, no
    entry in the timeline's resources); the text itself lives in subtitleSource, the .srt is the import source.
Text is stored exactly as given (logical order; Filmora shapes Arabic RTL itself). Stroke/shadow/glow are off.

DYNAMIC CAPTIONS (word highlight, Filmora 16 "AI Captions > Dynamic Caption") are a different model:
    subtitle_track(p, words=[("هل", 0.23, 0.47), ...], font=..., size=44, y=0.72, dynamic="blue_and_yellow")
  * one TITLE per caption line on a track flagged as subtitle track (main timeline userData 30323);
    type-7 wrapper -> own title timeline -> type-4 clip whose scriptBuf has TextVersion 3.0, TextMode 1,
    Stt.words [{text,start,end,key,supersize}] (ticks from the caption start, " " items between words),
    SttAnimation (preset: word animation rules) and styles [type 1 = spoken word, type 2 = key words];
  * inner clip userData 2001 = preset resource (res_type 85, e.g. Dynamic_Blue_and_Yellow); word times live only in
    the project — the .srt Filmora keeps is sentence-level and only a media-library item.
"""
import copy, hashlib, json, os, re, sys, time, types, uuid, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from filmora_wfp import (TICKS, aspect, fresh_uids, guid, pip_buf, thisuid, ud, ud_guid, ud_guid64, ud_int,  # noqa: E402
                         ud_str)
import filmora_paths  # noqa: E402

# Filmora's own default subtitle style ("Base"), copied from a project Filmora saved (identical in every sample).
_BASE_TEMPLATE = json.loads(r'''{"Aspect":"16:9","AutoLine":1,"AutoLineLimited":1,"AutoLineScale":0.0,"AutoLineVer":1,"Background":{"Alpha":255,"Border":{"Alpha":255,"Color":0,"Enable":0,"Gradient":{"Angle":0,"ColorPos":[{"Color":16777215,"Pos":0},{"Color":0,"Pos":100}],"Enable":0,"FillMode":0,"GradType":0,"GradVer":"2.0"},"Size":0},"Bottom":2.0,"Color":0,"Enable":0,"FillMode":0,"Gradient":{"Angle":0,"ColorPos":[{"Color":16777215,"Pos":0},{"Color":0,"Pos":100}],"Enable":0,"FillMode":0,"GradType":0,"GradVer":"2.0"},"Left":2.0,"OffsetX":0,"OffsetY":0,"Radian":0,"Right":2.0,"Texture":{"Enable":0,"File":"","FillMode":0,"KeepRatio":0,"LoopPath":"","SegmentNum":0},"Top":2.0},"BasePixel":0,"BoldVer":1,"ChangeAlignMode":0,"CleanAreaSize":0,"Curve":{"Angle":180,"Animation":{"Duration":10000000,"Enable":0,"Loop":0},"Distance":0.0,"Enable":0,"Mode":0,"PathAnchorType":0,"PathClose":0,"PathType":0,"VerticalPath":1},"DirectX":1,"DirectY":1,"Edge":{"Bottom":0.0,"Left":0.0,"Right":0.0,"Top":0.0},"Edit":{"Cursor":0,"CursorNext":0,"Enable":0,"SelectStart":0,"SelectStop":0},"FeatureVersion":1,"FillTextArea":0,"Glow":{"color":16777215,"enable":0,"hrotation":0,"intensity":50,"param":[{"color":16777215,"hrotation":0,"intensity":50,"range":50,"vrotation":0},{"color":16777215,"hrotation":0,"intensity":50,"range":50,"vrotation":0}],"range":50,"type":0,"vrotation":0},"Gradient":{"Angle":0,"ColorPos":[{"Color":16777215,"Pos":0},{"Color":0,"Pos":100}],"Enable":0,"FillMode":0,"GradType":0,"GradVer":"2.0"},"HideChar":0,"HideText":0,"Layout":{"Angle":0.0,"CharSpace":0,"LineSpace":0,"TextAlign":"center","TextAlignMode":"horizontal","TextAlignPos":"bottom","Underline":0,"UnderlineColor":-1},"NLEProjChangeStatus":false,"Offset":{"x":0.0,"y":0.0},"OutputTextPath":0,"PosX":0.5,"PosY":0.5,"Record":{"AspectX":0,"AspectY":0,"AutoLine":0,"AutoLineLimited":0,"AutoLineScale":0.0,"TextMode":1,"ViewHeight":0,"ViewWidth":0},"Rotate3D":{"x":0.0,"y":0.0,"z":0.0},"ScaleX":1.0,"ScaleY":1.0,"TemplatePath":"","Text":"New Text","TextData":[{"Basic":{"BgTexture":{"Enable":0,"File":"","FillMode":0,"KeepRatio":0,"LoopPath":"","SegmentNum":0},"Effect":0,"Enable":1,"FontBold":0,"FontHSize":20.0,"FontItalic":0,"FontName":"Arial","FontSize":20.0,"FontVSize":20.0,"TextAlpha":255,"TextBlurRadius":0,"TextColor":[{"Color":-1}],"Texture":{"Enable":0,"File":"","FillMode":0,"KeepRatio":0,"LoopPath":"","SegmentNum":0}},"Border":{"Alpha":255,"Angle":0,"BlurRadius":0,"Color":16777215,"Distance":0,"Enable":0,"Gradient":{"Angle":0,"ColorPos":[{"Color":16777215,"Pos":0},{"Color":0,"Pos":100}],"Enable":0,"FillMode":0,"GradType":0,"GradVer":"2.0"},"Size":8,"Texture":{"Enable":0,"File":"","FillMode":0,"KeepRatio":0,"LoopPath":"","SegmentNum":0}},"CharCase":0,"CharData":"New Text","CharSpace":0,"LineSpace":0,"Shadow":{"Alpha":255,"BlurRadius":5,"Color":16777215,"Direction":3,"Distance":4,"Enable":0,"Gradient":{"Angle":0,"ColorPos":[{"Color":16777215,"Pos":0},{"Color":0,"Pos":100}],"Enable":0,"FillMode":0,"GradType":0,"GradVer":"2.0"},"InAlpha":255,"InAngle":0,"InBlurRadius":5,"InColor":255,"InDistance":10,"InEnable":0,"Texture":{"Enable":0,"File":"","FillMode":0,"KeepRatio":0,"LoopPath":"","SegmentNum":0}},"Strikeout":0,"StrikeoutColor":-1,"Underline":0,"UnderlineColor":-1}],"TextMode":0,"TextScale":1.0,"TextVersion":1.0,"Texture":{"Enable":0,"File":"","FillMode":0,"KeepRatio":0,"LoopPath":"","SegmentNum":0},"UseDefaultBaseline":0,"UseDefaultSliderColor":1,"ViewSize":"0:0"}''')

# The thisUId values below are the same constants in every Filmora-saved subtitle track.
_CPZ = {"display": "crop-pan-zoom", "id": "video/effect/crop-pan-zoom", "thisUId": "e8becc5d-80d4-ee11-a45a-6c02e044ef35", "type": 3}


def _ani_template(x, y, sx, sy):
    p = [("EnableTransform", 5, 1), ("Position_x", 3, float(x)), ("Position_y", 3, float(y)), ("Scale_x", 3, float(sx)),
         ("Scale_y", 3, float(sy)), ("Rotation", 3, 0.0)]
    return {"effectList": [dict(_CPZ), {"display": "transform", "id": "video/effect/transform",
                                        "paramList": [{"fxParam": {"paramType": t, "unValue": v}, "name": n} for n, t, v in p],
                                        "thisUId": "eabecc5d-80d4-ee11-a45a-6c02e044ef35", "type": 3}]}


def hex_color(c):
    """'#RRGGBB' (or int) -> Filmora colour int 0xRRGGBB (same encoding as title TextColor)."""
    return c if isinstance(c, int) else int(str(c).lstrip("#")[:6], 16)


# ------------------------------------------------------------------ SRT in / out
def _ts(s):
    t = 0.0
    for part in s.strip().replace(",", ".").split(":"):
        t = t * 60 + float(part)
    return t


def from_srt(path, keep_breaks=False):
    """[(start_sec, end_sec, text)] from an .srt (or .vtt). Text is kept exactly (no spelling changes); tags like
    <i> are dropped; a cue's line breaks become spaces (Filmora wraps by width) unless keep_breaks=True."""
    raw = open(path, encoding="utf-8-sig").read().replace("\r", "")
    cues = []
    for block in re.split(r"\n\s*\n", raw):
        m = re.search(r"([\d:.,]+)\s*-->\s*([\d:.,]+)[^\n]*\n?(.*)", block, re.S)
        if not m:
            continue
        lines = [ln.strip() for ln in re.sub(r"<[^>]+>", "", m.group(3)).split("\n") if ln.strip()]
        text = ("\n" if keep_breaks else " ").join(lines)
        if text:
            cues.append((_ts(m.group(1)), _ts(m.group(2)), text))
    return cues


def _srt_time(sec):
    ms = int(round(sec * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def to_srt(cues):
    """SRT text (UTF-8, LF, no BOM — like the .srt files Filmora writes itself)."""
    return "".join(f"{i}\n{_srt_time(s)} --> {_srt_time(e)}\n{t}\n\n" for i, (s, e, t) in enumerate(cues, 1))


# ------------------------------------------------------------------ style
def _template(W, H, font, size, color, x, y, max_width, align, box, text):
    t = copy.deepcopy(_BASE_TEMPLATE)
    t.pop("Edit", None)
    em = 1.5 * size * W / 1920                         # Filmora: 1 em = 1.5 x FontSize x frame width / 1920
    sy = (em * 2.5 * (1 + text.count("\n"))) / H       # one line = 2.5 em (matches a Filmora-saved track); Filmora re-lays out each cue
    t.update(AutoLineScale=float(max_width), PosX=float(x), PosY=float(y), ScaleX=float(max_width), ScaleY=round(sy, 6),
             Text=text, ViewSize=f"{W}:{H}")
    t["Layout"]["TextAlign"] = align
    td = t["TextData"][0]
    td["CharData"] = text
    td["Basic"].update(FontName=font, FontSize=float(size), FontHSize=float(size), FontVSize=float(size), FontBold=0,
                       TextColor=[{"Color": hex_color(color)}])
    td["Border"].update(Enable=0, Size=0)                                  # flat text: no stroke
    td["Shadow"].update(Enable=0, InEnable=0, Distance=0, BlurRadius=0)     # no shadow
    t["Glow"]["enable"] = 0
    bg = t["Background"]
    if box:                                                                 # optional plate behind the text
        b = dict({"color": "#000000", "alpha": 0.6, "pad": 24, "radius": 16}, **(box if isinstance(box, dict) else {}))
        bg.update(Enable=1, Color=hex_color(b["color"]), Alpha=int(round(255 * float(b["alpha"]))), Radian=int(b["radius"]),
                  Left=float(b["pad"]), Right=float(b["pad"]), Top=float(b["pad"]), Bottom=float(b["pad"]))
    else:
        bg["Enable"] = 0
    return t, sy


# ------------------------------------------------------------------ shared pieces
def _basic_chain():
    """The clip-level effect chain Filmora gives subtitle clips and caption wrappers (no transform values)."""
    return [{"effectList": [dict(_CPZ, placeholder=False, placeholderStatus=0, thisUId=thisuid(),
                                 userData=[ud_guid64(3, guid()), ud(7, b"\x01")]),
                            {"display": "transform", "id": "video/effect/transform",
                             "paramList": [{"fxParam": {"paramType": 5, "unValue": 1186339}, "name": "dwValue"}],
                             "placeholder": False, "placeholderStatus": 0, "thisUId": thisuid(), "type": 3,
                             "userData": [ud_guid64(3, guid()), ud_str(15005, "1.0"), ud(7, b"\x01"), ud(36880, b"1\x00")]}],
             "name": "Basic"},
            {"effectList": [], "name": "Effect"},
            {"effectList": [], "name": "_wes_hold_effectchain_"}]


def _register_srt(p, cues, length, name=None, srt_path=None, clip=None, mark_uid=None):
    """Remember an .srt to write next to the .wfp and register as a media item (type 16384) when the project is saved;
    mark_uid: thisUId of a clip whose track gets flagged as a subtitle track (main-timeline userData 30323)."""
    mid = guid()
    stem = name or (os.path.splitext(os.path.basename(srt_path))[0] if srt_path else p.name)
    entry = dict(id=mid, name=stem, named=bool(name or srt_path), path=srt_path, length=length, cues=cues, clip=clip)
    p.__dict__.setdefault("_subtitle_media", []).append(entry)
    if mark_uid:
        p.__dict__.setdefault("_subtitle_marks", []).append(mark_uid)
    _hook_save(p)
    return entry


# ------------------------------------------------------------------ the track
def subtitle_track(project, cues=None, font=None, size=None, color="#FFFFFF", y=0.85, max_width=0.9, x=0.5, align="center",
                   box=None, start=0.0, name=None, srt_path=None, add=True, dynamic=None, words=None, max_chars=22,
                   max_words=6, mark_track=None):
    """Add a native Filmora subtitle track to a filmora_wfp.Project / filmora_fx.FxProject.

    cues: [(start_sec, end_sec, text)] on the timeline; a 4th item {font,size,color,y,x,max_width,align,box} restyles
          that cue (it gets its own template). Overlaps are trimmed (one cue at a time, like Filmora).
    font: the font the user chose (Filmora font name, e.g. "Readex Pro Bold") — required; size: FontSize with the same
    meaning as for titles (filmora_wfp.title_clip) — required; color '#RRGGBB'; y/x: centre of the text box (0..1,
    y down); max_width: wrap width as a fraction of the frame; box: None (no plate, default) or
    {"color", "alpha" 0..1, "pad" px, "radius"}; start: where the track clip begins (default 0, like Filmora's own SRT
    import); srt_path: where the source .srt is written (default: next to the .wfp at save time).

    dynamic: None = plain subtitle track (one type-22 clip). Otherwise Filmora 16 "Dynamic Captions" (word highlight):
      a preset name ("blue_and_yellow", "none") or a dict {"active": "#hex"|None (spoken word colour),
      "keyword": "#hex"|None (key-word colour), "animation": True|False (word fade-in of the preset), "preset": slug}.
      words: [(word, start_sec, end_sec[, is_keyword])] — e.g. faster-whisper word timestamps; grouped into captions by
      max_chars/max_words unless cues are given (then each cue takes the words that fall inside it). Without words,
      each cue's words get times shared by character count.
    Returns the type-22 clip (plain) or the list of caption wrappers (dynamic); add=True puts them on their own track
    above everything added so far.
    """
    if not font or not size:
        raise ValueError("font and size are required (the font is always the user's choice)")
    if dynamic is not None:
        return _dynamic_track(project, cues, words, font, size, color, y, max_width, x, align, dynamic, max_chars,
                              max_words, name, srt_path, add, True if mark_track is None else mark_track)
    p = project
    cues = sorted([tuple(c) for c in cues or []], key=lambda c: c[0])
    if not cues:
        raise ValueError("no cues")
    base = p.ticks(start)
    rows = []
    for i, c in enumerate(cues):
        s, e = max(p.ticks(c[0]), base), p.ticks(c[1])
        if i + 1 < len(cues):
            e = min(e, p.ticks(cues[i + 1][0]))                 # no overlaps on the single subtitle layer
        if e - s < TICKS // p.fps:
            e = s + TICKS // p.fps
        rows.append((s - base, e - base, c[2], c[3] if len(c) > 3 else {}))
    default = dict(font=font, size=size, color=color, y=y, x=x, max_width=max_width, align=align, box=box)
    templates, anis, keys, items = {"Base": copy.deepcopy(_BASE_TEMPLATE)}, {"Base": _ani_template(0.5, 0.85, 80.0, 30.0)}, {}, []
    for s, e, text, over in rows:
        st = dict(default, **over)
        key = json.dumps(st, sort_keys=True)
        if key not in keys:
            keys[key] = f"Base{len(keys) + 1}"
            tp, sy = _template(p.W, p.H, st["font"], st["size"], st["color"], st["x"], st["y"], st["max_width"], st["align"],
                               st["box"], text)
            templates[keys[key]] = tp
            anis[keys[key]] = _ani_template(st["x"], st["y"], st["max_width"] * 100, round(sy * 100, 6))
        items.append({"AniTemplate": keys[key], "Content": text, "End": int(e), "Layer": 0, "Start": int(s), "Template": keys[key]})
    dur = rows[-1][1]
    src = {"AniTemplates": anis, "End": dur // 10000 * 10000, "Items": items, "Layout": {"Angle": 0}, "Start": 0,
           "Templates": templates, "Version": 1}

    clip_guid = guid()
    pip, pip_size = pip_buf(100.0)
    clip = {"allLocked": True, "effectChainList": _basic_chain(),
            "inPoint": 0, "outPoint": dur, "pipBuf": pip, "pipBufSize": pip_size, "placeholder": False, "placeholderStatus": 0,
            "subtitleSource": json.dumps(src, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "thisUId": thisuid(), "tlBegin": base, "tlEnd": base + dur, "type": 22, "userData": []}
    entry = _register_srt(p, [(s / TICKS, e / TICKS, t) for s, e, t, _ in rows], dur, name, srt_path, clip,
                          clip["thisUId"] if mark_track else None)
    clip["userData"] = [ud_int(102, 4), ud_int(103, 0), ud_str(50, entry["name"]), ud_int(2, 0), ud_guid(10, entry["id"]),
                        ud_int(1, 29), ud(13003, b"\x00"), ud_guid64(3, clip_guid), ud_int(6, p.main_tl_id)]
    p.clip_map[clip_guid] = entry["id"]                 # extra.json mediaClipsMapInfo: clip -> .srt media
    if add:
        p.add_lane([clip])
    return clip


# ------------------------------------------------------------------ dynamic captions (Filmora 16 "AI Captions > Dynamic")
# Main text style of a dynamic caption, copied from a project Filmora 16 saved (preset "Blue and Yellow"; words emptied).
_DYN_SCRIPT = json.loads(r'''{"Aspect":"16:9","AutoLine":0,"AutoLineLimited":0,"AutoLineScale":1.0,"AutoLineVer":1,"Background":{"Alpha":255,"Border":{"Alpha":255,"Color":0,"Enable":0,"Gradient":{"Angle":0,"ColorPos":[{"Color":16777215,"Pos":0},{"Color":0,"Pos":100}],"Enable":0,"FillMode":0,"GradType":0,"GradVer":"2.0"},"Size":0},"Bottom":0.0,"Color":0,"Enable":0,"FillMode":0,"Gradient":{"Angle":0,"ColorPos":[{"Color":16777215,"Pos":0},{"Color":0,"Pos":100}],"Enable":0,"FillMode":0,"GradType":0,"GradVer":"2.0"},"Left":0.0,"OffsetX":0,"OffsetY":0,"Radian":0,"Right":0.0,"Texture":{"Enable":0,"File":"","FillMode":0,"KeepRatio":0,"LoopPath":"","SegmentNum":0},"Top":0.0},"BasePixel":0,"BoldVer":1,"ChangeAlignMode":0,"CleanAreaSize":0,"Curve":{"Angle":180,"Animation":{"Duration":10000000,"Enable":0,"Loop":0},"Distance":0.0,"Enable":0,"Mode":0,"PathAnchorType":0,"PathClose":0,"PathType":0,"VerticalPath":1},"DirectX":1,"DirectY":1,"Edge":{"Bottom":0.847711443901062,"Left":0.22860687971115112,"Right":0.22860687971115112,"Top":0.12103855609893799},"FeatureVersion":1,"FillTextArea":0,"Glow":{"color":16777215,"enable":0,"hrotation":0,"intensity":50,"param":[{"color":16777215,"hrotation":0,"intensity":50,"range":50,"vrotation":0},{"color":16777215,"hrotation":0,"intensity":50,"range":50,"vrotation":0}],"range":50,"type":0,"vrotation":0},"Gradient":{"Angle":0,"ColorPos":[{"Color":16777215,"Pos":0},{"Color":0,"Pos":100}],"Enable":0,"FillMode":0,"GradType":0,"GradVer":"2.0"},"HideChar":0,"HideText":0,"Layout":{"Angle":0.0,"CharSpace":0,"LineSpace":0,"TextAlign":"center","TextAlignMode":"horizontal","TextAlignPos":"center","Underline":0,"UnderlineColor":-1},"NLEProjChangeStatus":false,"Offset":{"x":0.0,"y":0.0},"OldShadowProject":0,"OutputTextPath":0,"PosX":0.5,"PosY":0.863336443901062,"Record":{"AspectX":0,"AspectY":0,"AutoLine":0,"AutoLineLimited":0,"AutoLineScale":0.0,"TextMode":1,"ViewHeight":0,"ViewWidth":0},"Rotate3D":{"b":0.0,"enable":0,"p":0.0,"v":2,"x":0.0,"y":0.0,"z":0.0},"ScaleX":0.5427862405776978,"ScaleY":0.03125,"Stt":{"duration":0,"words":[]},"SttAnimation":{"MappingChar":{"alpha":40,"color":16777215,"colorflag":false,"enable":0,"size":40,"sizeflag":false},"background":[{"Gradient":{"Angle":0,"ColorPos":[{"Color":16777215,"Pos":0},{"Color":0,"Pos":100}],"Enable":0,"FillMode":0,"GradType":0,"GradVer":"2.0"},"animation":{"enable":0,"name":"","rules":[]},"border":{"color":23434,"enable":0,"size":10},"bottom":2,"color":-29696,"enable":0,"outsetx":2,"outsety":2,"right":2,"roundAngle":15,"type":2}],"centerPoint":{"x":0.5,"y":0.5},"damping":0,"effect":[],"enable":1,"orgEffect":"","subtitle":{"animation":{"enable":1,"name":"","rules":[{"endTime":0.5,"endValue":255.0,"maxTime":500,"mode":-1,"output":"in","property":"alpha","startTime":127.0,"startValue":0.0,"type":0},{"endTime":1.0,"endValue":255.0,"maxTime":500,"mode":-1,"output":"in","property":"alpha","startTime":0.5,"startValue":255.0,"type":0}]},"charAnimationMode":0,"charHighlightMode":1,"charPlayMode":2,"clipMode":0,"keepStyle":0,"lineCnt":0,"lineWordCnt":0,"orgTextAnimation":"{\"enable\":1,\"rules\":[{\"endTime\":0.5,\"endValue\":255,\"maxTime\":500,\"property\":\"alpha\",\"startTime\":127,\"startValue\":0,\"type\":0},{\"endTime\":1,\"endValue\":255,\"maxTime\":500,\"property\":\"alpha\",\"startTime\":0.5,\"startValue\":255,\"type\":0}]}","punctuationLineBreak":0},"textBoundHeight":0.800000011920929,"textBoundWidth":0.5,"uniformHeight":1080,"uniformWidth":1920,"useBoundArea":0,"version":"3.5","wordBkgSlideStackingPage":0},"SttAutoAspect":1,"SttAutoLine":1,"TemplatePath":"","Text":"","TextData":[{"Basic":{"BgTexture":{"Enable":0,"File":"","FillMode":0,"KeepRatio":0,"LoopPath":"","SegmentNum":0},"Effect":0,"Enable":1,"FontBold":0,"FontHSize":20.0,"FontItalic":0,"FontName":"Outfit SemiBold","FontSize":20.0,"FontVSize":20.0,"TextAlpha":255,"TextBlurRadius":0,"TextColor":[{"Color":16777215}],"Texture":{"Enable":0,"File":"","FillMode":0,"KeepRatio":0,"LoopPath":"","SegmentNum":0}},"Border":{"Alpha":255,"Angle":0,"BlurRadius":0,"Color":13977411,"Distance":0,"Enable":0,"Gradient":{"Angle":0,"ColorPos":[{"Color":16777215,"Pos":0},{"Color":0,"Pos":100}],"Enable":0,"FillMode":0,"GradType":0,"GradVer":"2.0"},"Size":0,"Texture":{"Enable":0,"File":"","FillMode":0,"KeepRatio":0,"LoopPath":"","SegmentNum":0}},"CharCase":0,"CharData":"","CharSpace":0,"LineSpace":0,"Shadow":{"Alpha":140,"BlurRadius":7,"Color":0,"Direction":3,"Distance":2,"Enable":1,"Gradient":{"Angle":0,"ColorPos":[{"Color":16777215,"Pos":0},{"Color":0,"Pos":100}],"Enable":0,"FillMode":0,"GradType":0,"GradVer":"2.0"},"InAlpha":255,"InAngle":0,"InBlurRadius":5,"InColor":255,"InDistance":10,"InEnable":0,"Texture":{"Enable":0,"File":"","FillMode":0,"KeepRatio":0,"LoopPath":"","SegmentNum":0}},"Strikeout":0,"StrikeoutColor":-1,"Underline":0,"UnderlineColor":-1}],"TextMode":1,"TextScale":1.0,"TextVersion":3.0,"Texture":{"Enable":0,"File":"","FillMode":0,"KeepRatio":0,"LoopPath":"","SegmentNum":0},"UseDefaultBaseline":0,"UseDefaultSliderColor":1,"ViewSize":"1080:1920"}''')

# Installed dynamic-caption presets (Filmora 16 configs\AnimateStt\default\85_Dynamic_*). Style type 2 = key words,
# type 1 = the word being spoken (type 0 = the normal text = the main TextData).
DYNAMIC_PRESETS = {
    "blue_and_yellow": {"preset": "Dynamic_Blue_and_Yellow", "active": "#7070FF", "keyword": "#FFED3E", "animation": True},
    "none": {"preset": "Dynamic_None", "active": None, "keyword": None, "animation": False},
}
_STYLE_KEYS = ("Background", "BasePixel", "Gradient", "Layout", "Offset", "TextData", "TextVersion", "Texture")


def _dyn_style(script, typ, color):
    st = {k: copy.deepcopy(script[k]) for k in _STYLE_KEYS}
    st["text"] = ""
    st["TextData"][0]["CharData"] = ""
    if color:
        st["TextData"][0]["Basic"]["TextColor"] = [{"Color": hex_color(color)}]
    return {"enable": 1 if color else 0, "textStyle": json.dumps(st, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "type": typ}


def _group_words(words, cues, max_chars, max_words):
    """-> [(start, end, [(word, s, e, key)])]"""
    words = sorted([(w[0].strip(), float(w[1]), float(w[2]), bool(w[3]) if len(w) > 3 else False) for w in words or []
                    if str(w[0]).strip()], key=lambda w: w[1])
    if cues:
        cues = sorted([tuple(c) for c in cues], key=lambda c: c[0])
        out = []
        for c in cues:
            ws = [w for w in words if c[0] - 0.02 <= (w[1] + w[2]) / 2 < c[1] + 0.02] if words else []
            if not ws:                                 # no word times: share the cue's time by character count
                parts = c[2].split()
                total, t, ws = sum(len(q) for q in parts) or 1, c[0], []
                for q in parts:
                    d = (c[1] - c[0]) * len(q) / total
                    ws.append((q, t, t + d, False))
                    t += d
            out.append((c[0], c[1], ws))
        return out
    import captions                                       # same grouping rules as the text-clip captions
    chunks = captions.chunk([("w", s, e, w, False) for w, s, e, k in words], max_chars, max_words)
    out, i = [], 0
    for s, e, text, ws in chunks:
        out.append((s, e, words[i:i + len(ws)]))
        i += len(ws)
    return out


def _dynamic_track(p, cues, words, font, size, color, y, max_width, x, align, dynamic, max_chars, max_words, name,
                   srt_path, add, mark):
    preset = dict(DYNAMIC_PRESETS["blue_and_yellow"])
    if isinstance(dynamic, str):
        preset = dict(DYNAMIC_PRESETS[dynamic.lower().replace(" ", "_").replace("dynamic_", "")])
    elif isinstance(dynamic, dict):
        base = DYNAMIC_PRESETS.get(str(dynamic.get("preset", "blue_and_yellow")).lower().replace("dynamic_", ""), preset)
        preset = dict(base, **dynamic)
        preset["preset"] = base["preset"]            # Filmora's own resource name (e.g. Dynamic_Blue_and_Yellow)
    groups = _group_words(words, cues, max_chars, max_words)
    if not groups:
        raise ValueError("no cues / words")
    W, H = p.W, p.H
    # Dynamic captions (text engine 3.0) size text against the long side: box height = 3 x FontSize x max(W,H)/1920
    # (Filmora-saved sample). Titles use 3 x FontSize x W/1920 -> convert so `size` means the same on both.
    fs = round(float(size) * W / max(W, H), 3)
    em = 1.5 * fs * max(W, H) / 1920
    anc, tlg, inner_anc, inner_tlg = ("{%s}" % uuid.uuid4() for _ in range(4))
    wrappers, srt_cues = [], []
    for gi, (gs, ge, ws) in enumerate(groups):
        b = p.ticks(gs)
        e = p.ticks(groups[gi + 1][0]) if gi + 1 < len(groups) and p.ticks(groups[gi + 1][0]) < p.ticks(ge) else p.ticks(ge)
        if e - b < TICKS // p.fps:
            e = b + TICKS // p.fps
        dur = e - b
        text = " ".join(w[0] for w in ws)
        srt_cues.append((b / TICKS, e / TICKS, text))
        stt = []
        for n, (w, s, we, k) in enumerate(ws):
            if n:
                stt.append({"end": 0, "key": 0, "start": 0, "supersize": 0, "text": " "})
            rs = min(max(0, int(round(s * TICKS)) - b), dur)
            re_ = min(max(rs, int(round(we * TICKS)) - b), dur)
            stt.append({"end": re_, "key": 1 if k else 0, "start": rs, "supersize": 0, "text": w})
        # layout estimate (Filmora re-fits: SttAutoAspect / SttAutoLine)
        width = min(max_width, max(0.05, len(text) * 0.55 * em / W))
        lines = max(1, -(-int(len(text) * 0.55 * em) // max(1, int(max_width * W))))
        sx, sy = width, lines * 3 * fs * max(W, H) / 1920 / H
        s = copy.deepcopy(_DYN_SCRIPT)
        s.update(Text=text, PosX=float(x), PosY=float(y), ScaleX=sx, ScaleY=sy, ViewSize=f"{W}:{H}",
                 Edge={"Bottom": y - sy / 2, "Left": x - sx / 2, "Right": 1 - x - sx / 2, "Top": 1 - y - sy / 2},
                 Stt={"duration": 0, "words": stt})
        s["Layout"]["TextAlign"] = align
        td = s["TextData"][0]
        td["CharData"] = text
        td["Basic"].update(FontName=font, FontSize=fs, FontHSize=fs, FontVSize=fs, TextColor=[{"Color": hex_color(color)}])
        td["Border"].update(Enable=0, Size=0)                                   # flat text: no stroke, no shadow
        td["Shadow"].update(Enable=0)
        sa = s["SttAnimation"]
        sa["textBoundWidth"] = float(max_width)
        if not preset.get("animation"):
            sa["subtitle"]["animation"] = {"enable": 0, "name": "", "rules": []}
            sa["subtitle"]["orgTextAnimation"] = ""
        # verified in Filmora: style type 1 = the word being spoken, type 2 = key words (stt "key": 1)
        s["styles"] = [_dyn_style(s, 2, preset.get("keyword")), _dyn_style(s, 1, preset.get("active"))]
        script = json.dumps(s, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

        tl_id = p.next_tl_id
        p.next_tl_id += 1
        ttl = copy.deepcopy(p.T.title_tl)
        fresh_uids(ttl)
        ttl.update(timelineId=tl_id, frameRate={"den": 1, "num": p.fps}, resolutionWidth=W, resolutionHeight=H)
        ttl["aspectRatioX"], ttl["aspectRatioY"] = aspect(W, H)
        ttl["userData"] = [u for u in ttl["userData"] if u["key"] not in (11000, 3)] + [ud_guid64(11000, guid()), ud_guid64(3, guid())]
        pip, pip_size = pip_buf(100.0)
        tf = [("Position_x", float(x)), ("Position_y", float(y)), ("Scale_x", sx * 100), ("Scale_y", sy * 100)]
        inner = {"effectChainList": [
                    {"effectList": [dict(_CPZ, placeholder=False, placeholderStatus=0, thisUId=thisuid(),
                                         userData=[ud_guid64(3, guid()), ud(7, b"\x01")]),
                                    {"display": "transform", "id": "video/effect/transform",
                                     "paramList": [{"fxParam": {"paramType": 3, "unValue": v}, "name": n} for n, v in tf],
                                     "placeholder": False, "placeholderStatus": 0, "thisUId": thisuid(), "type": 3,
                                     "userData": [ud_guid64(3, guid()), ud(7, b"\x01")]}], "name": "Basic"},
                    {"effectList": [], "name": "Effect"}, {"effectList": [], "name": "_wes_hold_effectchain_"}],
                 "inPoint": 0, "outPoint": dur, "pipBuf": pip, "pipBufSize": pip_size, "placeholder": False,
                 "placeholderStatus": 0, "scriptBuf": script, "scriptBufSize": len(script.encode()) + 1, "thisUId": thisuid(),
                 "tlBegin": 0, "tlEnd": dur, "type": 4,
                 "userData": [ud_int(2, 0), ud(36866, b"0\x00"), ud_int(103, 6),
                              ud_str(55, json.dumps({"Key_AncestralGuid": inner_anc, "Key_TimelineGuid": inner_tlg,
                                                     "Render.RangeType": "1", "clip_color_infotag": "7",
                                                     "key_timeline_resource_info": json.dumps({"name": "Caption"}),
                                                     "key_timeline_type": "5"}, separators=(",", ":")), nul=True),
                              ud_int(6, tl_id), ud_int(102, 1), ud_guid64(3, guid()), ud_int(1, 5),
                              ud_str(2001, json.dumps({"id": 0, "infoType": 7, "is_custom": 0, "smart_resource": 0, "sale_mode": 0,
                                                       "res_sub_type": 0, "res_type": 85, "related_slug": "",
                                                       "name": preset["preset"], "user_string": {}}, separators=(",", ":")))]}
        ttl["trackInfos"][0]["clipList"] = [inner]
        p.title_tls.append(ttl)

        res55 = json.dumps({"id": "38814", "key_resource_packname": "DefaultPackage_93", "name": "Subtitle 9",
                            "resourcePackID": "3375", "titles": "Subtitles_9"}, separators=(",", ":"))
        wpip, wpip_size = pip_buf(100.0)
        label = " ".join(w[0] for w in ws[:4]) + (" ..." if len(ws) > 4 else "")
        wrappers.append({"effectChainList": _basic_chain(), "inPoint": 0, "isAudio": 0, "keyframeScaleMode": 1, "outPoint": dur,
                         "pipBuf": wpip, "pipBufSize": wpip_size, "placeholder": False, "placeholderStatus": 0,
                         "thisUId": thisuid(), "timelineId": tl_id, "tlBegin": b, "tlEnd": e, "type": 7,
                         "userData": [ud_str(55, json.dumps({"Key_AncestralGuid": anc, "Key_TimelineGuid": tlg,
                                                             "clip_color_infotag": "7", "key_timeline_markInOut_enable": "0",
                                                             "key_timeline_resource_info": res55, "key_timeline_type": "5"},
                                                            separators=(",", ":")), nul=True),
                                      ud_int(103, 0), ud_str(50, label), ud(36866, b"0\x00"), ud_int(2, 1),
                                      ud_str(134, json.dumps({"CreationSourceType": 3, "CanClone": False, "RelatedOriginalClipUuid": ""},
                                                             separators=(",", ":"))),
                                      ud_int(6, p.main_tl_id), ud_int(102, 1), ud_int(1, 12), ud_guid64(3, guid())]})
    # the sentence-level .srt Filmora keeps next to a dynamic caption track (library item only, not linked to a clip)
    _register_srt(p, srt_cues, wrappers[-1]["tlEnd"], name, srt_path, None, wrappers[0]["thisUId"] if mark else None)
    if add:
        p.add_lane(wrappers)
    return wrappers


# ------------------------------------------------------------------ save hook: .srt files, media registry, track flag
def _hook_save(p):
    if getattr(p, "_subtitle_save_hooked", False):
        return
    orig = p.save

    def save(self, out_path=None):
        out = os.path.abspath(out_path or os.path.join(filmora_paths.project_dir(), self.name + ".wfp"))
        for n, m in enumerate(self._subtitle_media):
            if not m["path"]:
                stem = os.path.splitext(os.path.basename(out))[0]
                m["path"] = os.path.join(os.path.dirname(out), stem + (f"_{n + 1}" if n else "") + ".srt")
            m["path"] = os.path.abspath(m["path"]).replace("\\", "/")
            if not m["named"]:                          # media (+ clip) name = the .srt file name, as in Filmora
                m["name"] = os.path.splitext(os.path.basename(m["path"]))[0]
                if m["clip"]:
                    m["clip"]["userData"] = [u if u["key"] != 50 else ud_str(50, m["name"]) for u in m["clip"]["userData"]]
            os.makedirs(os.path.dirname(m["path"]), exist_ok=True)
            with open(m["path"], "w", encoding="utf-8", newline="\n") as f:
                f.write(to_srt(m["cues"]))
        res = orig(out)
        _postprocess(res[0], self._subtitle_media, self.__dict__.get("_subtitle_marks", []))
        return res

    p.save = types.MethodType(save, p)
    p._subtitle_save_hooked = True


def _folder_end(head):
    """Index of the '}' closing the media library's "Folder" object (GUID strings contain braces -> skip strings)."""
    i = head.index('"Folder":{') + len('"Folder":{')
    depth, q = 1, False
    while True:
        ch = head[i]
        if ch == '"':
            q = not q
        elif not q and ch == "{":
            depth += 1
        elif not q and ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1


def _postprocess(wfp, medias, marks):
    """Register each .srt as a type-16384 media item (medias_info.json + Medias/<id>/media.json) and flag subtitle
    tracks on the main timeline (userData 30323, as Filmora 16 does for its caption tracks)."""
    z = zipfile.ZipFile(wfp)
    files = {i.filename: z.read(i.filename) for i in z.infolist()}
    z.close()
    key = "ProjectFolder/Medias/medias_info.json"
    mi = files[key].decode("utf-8")
    head, tail = mi.split(',"media_items":', 1)
    items = json.loads(tail[:-1])
    now = int(time.time())
    for m in medias:
        j = _folder_end(head)
        head = head[:j] + f',"media_item":"{m["id"]}"' + head[j:]
        items[m["id"]] = {"download_url": m["path"], "id": m["id"], "media_type": 16384, "media_length": int(m["length"]),
                          "name": m["name"], "mediaCreationInfo": "{\"creationType\":0}", "import_time": now,
                          "src_md5": hashlib.md5(open(m["path"], "rb").read()).hexdigest(), "stream_idx": -1,
                          "mark_info_list": [{"mark_in": -1, "mark_out": -1}], "scence_info": []}
        mj = {"version": "1.1.7", "file_name": m["path"], "sourceInfo": {"basicInfo": {
            "streamType": 2, "fourCC": 0, "mediaLength": int(m["length"]), "programCount": 0, "videoStreamCount": 0,
            "audioStreamCount": 0, "subPicStreamCount": 0, "bitRate": 0, "createDate": 0}, "recordInfos": {}}}
        files[f"ProjectFolder/Medias/{m['id']}/media.json"] = json.dumps(mj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    files[key] = (head + ',"media_items":' + json.dumps(items, ensure_ascii=False, separators=(",", ":")) + "}").encode("utf-8")
    if marks:
        info = json.loads(files["ProjectFolder/project_info.json"])
        tkey = f"ProjectFolder/Medias/{info['timeline_mediaId']}/timeline.wesproj"
        doc = json.loads(files[tkey])
        main = doc["timelineInfos"][0]
        idx, uuids, nvideo = [], [], 0
        for t in main["trackInfos"]:
            if t["trackType"] == 1:
                nvideo += 1
                if any(c.get("thisUId") in marks for c in t["clipList"]):
                    idx.append(nvideo)                  # 1-based video-track number (sample: 2nd video track -> [2])
                    uuids.append(t["uuid"])
        main["userData"] = [u for u in main["userData"] if u["key"] != 30323] + [
            ud_str(30323, json.dumps({"subtitleTrackIndexes": idx, "subtitleTracks": uuids, "version": 2}, separators=(",", ":")))]
        files[tkey] = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    tmp = wfp + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in files.items():
            z.writestr(n, b)
    os.replace(tmp, wfp)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    for s, e, t in from_srt(sys.argv[1]):
        print(f"{s:8.3f} {e:8.3f}  {t}")
