"""Filmora's own text animation presets (In / Out / Loop) on titles built by filmora_wfp.Project.title_clip().

    python filmora_text_anim.py                     # summary of every text animation known on this PC
    python filmora_text_anim.py list in             # list one scene (in | out | loop | legacy), writable ones first
    python filmora_text_anim.py search typewriter   # search English/Arabic name, slug or engine id

Where the presets live (all read-only):
  * bundled with Filmora  <install>/configs/AnimationNew/{uuid}/info.json + param.conf + <name>.json
      (<install> = %LOCALAPPDATA%/../LocalWondershare/Wondershare Filmora/<version>, found via filmora_paths.log_dir())
  * downloaded            <Download>/Filmora/resTextAnimation/<folder>/resinfo.json + Data/data.json (+ timelineDataInfo.json)
  * online catalog        %APPDATA%/Wondershare/Wondershare Filmora/resInfo.db  (table onlineCloudResourceInfo, res_type 27)
      -> names/ids only; the payload exists only after Filmora downloads it, unless the same preset is also bundled.
  * legacy (Filmora <=12 "animation" key) <install>/resources/captions/Animation.xml -> listed, never written.

How Filmora stores a text animation (recovered from Filmora 15.2-16 projects):
  the INNER title clip (type 4, inside the text's own title timeline) gets
      "inAnimation" / "outAnimation" / "loopAnimation" = {<preset payload>, "duration": ticks, "userData": [...]}
  Nothing changes on the type-7 wrapper on the main timeline, nor in scriptBuf.
  Payload kinds (field "type"): 2 algorithm (stringParam GUID), 3 per-character XML (charXml), 4 transition-style
  (stringParam GUID), 5 MG 2D per-character/word (stringParam "MG_2d_NN"), 6 effect/motion chain
  (effectChain + originLength = the preset's natural length in ticks).
  userData 12 = the cloud resource info (id, slug, res_type 27, res_sub_type 2701/2702/2703) when the preset came from
  the online library; userData 112 = {"res": [effects the chain needs]} + NUL for type-6 presets that use effects.
"""
import base64, copy, glob, json, os, re, sqlite3, sys, xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import filmora_paths  # noqa: E402

TICKS = 10_000_000
SCENES = {"in": 2701, "out": 2702, "loop": 2703}
KEYS = {"in": "inAnimation", "out": "outAnimation", "loop": "loopAnimation"}
SCENE_OF = {"animation_scene_in": "in", "animation_scene_out": "out", "animation_scene_loop": "loop", 2701: "in", 2702: "out", 2703: "loop"}
KIND_OF_TYPE = {2: "algorithm", 3: "char", 4: "transition", 5: "mg2d", 6: "effect"}
MG2D_DEFAULT, MG2D_MAX = 1.5, 5.0          # resources/captions/Animation2DInfos.xml <AnimationTime Intro Outro Min Max>
OTHER_DEFAULT = 1.0
_cache = None


# ------------------------------------------------------------------ locations
def install_dir():
    """Newest installed Filmora program folder (has configs/AnimationNew)."""
    cands = []
    ld = filmora_paths.log_dir()
    if ld:
        cands.append(os.path.dirname(ld))
    root = os.path.normpath(os.path.join(os.path.expandvars("%LOCALAPPDATA%"), "..", "LocalWondershare", "Wondershare Filmora"))
    cands += sorted(glob.glob(os.path.join(root, "*")), reverse=True)
    for pf in ("%ProgramFiles%", "%ProgramFiles(x86)%"):
        cands += sorted(glob.glob(os.path.join(os.path.expandvars(pf), "Wondershare", "Wondershare Filmora*")), reverse=True)
    for c in cands:
        if os.path.isdir(os.path.join(c, "configs", "AnimationNew")):
            return c
    return None


def _json(path):
    try:
        return json.load(open(path, encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _norm(s):
    return re.sub(r"[\W_]", "", str(s).lower())        # keeps Arabic letters


def _kind(payload, fallback="?"):
    if not payload:
        return fallback
    if payload.get("type") == 6:
        ids = [str(e.get("id", "")) for e in payload["effectChain"].get("effectList", [])]
        return "motion" if ids and all(i.startswith("video/") for i in ids) else "effect"
    return KIND_OF_TYPE.get(payload.get("type"), fallback)


def _payload_from_data(d):
    """data.json / bundled preset json -> (payload dict without duration, origin_length ticks or None)."""
    if not d:
        return None, None
    if isinstance(d.get("animation"), dict):
        a = {k: v for k, v in d["animation"].items() if k in ("type", "name", "stringParam", "charXml")}
        return a, None
    if isinstance(d.get("effectChain"), dict):
        ec = copy.deepcopy(d["effectChain"])
        ec.pop("enable", None)          # projects store {"effectList", "name"} only
        return {"type": 6, "name": ec.get("name", ""), "effectChain": ec}, int(d.get("outPoint") or 0) or None
    return None, None


def _effect_guids():
    """GUIDs of every downloaded effect (Data/filter.xml) - a type-6 preset that uses an effect needs it installed."""
    out = set()
    for f in glob.glob(os.path.join(filmora_paths.download_dir(), "*", "*", "Data", "filter.xml")):
        try:
            out |= {g.upper() for g in re.findall(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}",
                                                   open(f, encoding="utf-8", errors="replace").read())}
        except OSError:
            pass
    return out


def _needs(payload):
    """Effect GUIDs a type-6 chain needs (built-in video/effect/* ids need nothing)."""
    if not payload or payload.get("type") != 6:
        return []
    return [e["id"] for e in payload["effectChain"].get("effectList", []) if not str(e.get("id", "")).startswith("video/")]


# ------------------------------------------------------------------ inventory
def _bundled(inst):
    out = []
    base = os.path.join(inst, "configs", "AnimationNew") if inst else None
    if not base or not os.path.isdir(base):
        return out
    for d in sorted(os.listdir(base)):
        p = os.path.join(base, d)
        info, pc = _json(os.path.join(p, "info.json")), _json(os.path.join(p, "param.conf"))
        if not info or not pc:
            continue
        pv = pc.get("paramValues", {})
        scene = SCENE_OF.get(pv.get("AnimationScene"))
        atype = pv.get("AnimationType", "").replace("animation_type_", "")
        if not scene or atype == "none":
            continue
        payload, olen = _payload_from_data(_json(os.path.join(p, pc.get("Animation", ""))))
        out.append(dict(name=info.get("title"), name_ar=None, scene=scene, kind=_kind(payload, atype),
                        engine=(payload or {}).get("stringParam") or (payload or {}).get("name"), source="bundled", uuid=d,
                        res_id=None, slug=None, sale_mode=0, payload=payload, origin_length=olen, res_info=None, deps=None))
    return out


def _downloaded():
    out = []
    for p in sorted(glob.glob(os.path.join(filmora_paths.download_dir(), "resTextAnimation", "*"))):
        ri = _json(os.path.join(p, "resinfo.json"))
        if not ri:
            continue
        payload, olen = _payload_from_data(_json(os.path.join(p, "Data", "data.json")))
        deps = _json(os.path.join(p, "timelineDataInfo.json"))
        scene = SCENE_OF.get(ri.get("element_sub_type"))
        if not scene:
            continue
        info = {k: v for k, v in ri["download_Info"].items() if k != "resourceRate"} if ri.get("download_Info") else {"id": ri["id"], "infoType": 7, "is_custom": 0, "smart_resource": 0, "sale_mode": ri.get("sale_mode", 0),
                                          "source": ri.get("source", 0), "res_sub_type": ri["element_sub_type"], "res_type": 27,
                                          "related_slug": "", "name": ri["slug"], "user_string": {}}
        t = ri.get("titles", {})
        out.append(dict(name=t.get("en"), name_ar=t.get("ae"), scene=scene, kind=_kind(payload),
                        engine=(payload or {}).get("stringParam") or (payload or {}).get("name"), source="downloaded", uuid=None,
                        res_id=ri["id"], slug=ri["slug"], sale_mode=ri.get("sale_mode", 0), payload=payload, origin_length=olen,
                        res_info=info, deps=deps if isinstance(deps, list) and deps else None, folder=os.path.basename(p),
                        categories=[c.get("name") for c in ri.get("categories", [])]))
    return out


def _online():
    db = os.path.join(filmora_paths.APPDATA_F, "resInfo.db")
    if not os.path.exists(db):
        return []
    out, seen = [], set()
    try:
        con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro&immutable=1", uri=True)
        rows = []
        for table in ("onlineCloudResourceInfo", "cloudResourceInfo"):
            try:
                rows += con.execute(f"select res_info_json from {table} where res_type=27").fetchall()
            except sqlite3.Error:
                pass
        con.close()
    except sqlite3.Error:
        return []
    for (js,) in rows:
        try:
            j = json.loads(js)
        except ValueError:
            continue
        sub = j.get("element_sub_type") or 0
        if not sub:          # a few old rows (type 27, sub 0) are the same presets as in-scene ones
            sub = 2702 if "_out_" in j.get("slug", "") else 2703 if "_loop_" in j.get("slug", "") else 2701
        scene = SCENE_OF.get(sub)
        if not scene or j["id"] in seen or j.get("slug", "").endswith("_none"):
            continue
        seen.add(j["id"])
        rel = ((j.get("related_info") or {}).get("title") or {})
        info = {"id": j["id"], "infoType": 7, "is_custom": 0, "smart_resource": 0, "sale_mode": j.get("sale_mode", 0), "source": j.get("source", 0),
                "res_sub_type": sub, "res_type": 27, "smart_res_relative_path": "", "related_slug": "", "name": j.get("slug"), "user_string": {}}
        out.append(dict(name=(j.get("titles") or {}).get("en") or rel.get("en"), name_ar=rel.get("ae"), scene=scene, kind="?", engine=None,
                        source="online", uuid=None, res_id=j["id"], slug=j.get("slug"), sale_mode=j.get("sale_mode", 0), payload=None,
                        origin_length=None, res_info=info, deps=None,
                        categories=[c.get("slug") for c in j.get("categories", [])]))
    return out


def _legacy(inst):
    p = os.path.join(inst or "", "resources", "captions", "Animation.xml")
    out = []
    try:
        root = ET.fromstring(open(p, encoding="utf-8", errors="replace").read())
    except (OSError, ET.ParseError):
        return out
    kinds = {"0": "none", "1": "char", "2": "transition", "4": "motion", "8": "algorithm", "16": "mg2d"}
    for it in root.iter("item"):
        if it.get("type") == "0":
            continue
        g = it.findtext("Guid") or it.findtext("AnimationPath") or it.get("name")
        out.append(dict(name=it.get("name"), name_ar=None, scene="legacy", kind=kinds.get(it.get("type"), it.get("type")), engine=g,
                        source="legacy", uuid=None, res_id=None, slug=None, sale_mode=0, payload=None, origin_length=None, res_info=None, deps=None))
    return out


def list_text_animations(scene=None, refresh=False):
    """Every text animation Filmora offers on this PC, as dicts:
      name, name_ar, scene (in|out|loop|legacy), kind (mg2d|char|algorithm|transition|effect|motion|?), engine (stringParam),
      source (bundled | downloaded | online | legacy), res_id/slug (cloud id), payload (what goes into the clip),
      writable (True = apply_text_animation() can write it now), why (reason when not writable).
    Online-only presets become writable when the same preset is bundled (same scene + name); otherwise the user has to
    download it once in Filmora (Titles > Animation panel) - its payload is not on disk before that."""
    global _cache
    if _cache is None or refresh:
        inst = install_dir()
        bundled, down, online = _bundled(inst), _downloaded(), _online()
        have_fx = _effect_guids()
        by_name = {}
        for e in bundled:
            by_name.setdefault((e["scene"], _norm(e["name"])), e)
        allx = []
        for e in down:
            miss = [g for g in _needs(e["payload"]) if g.upper() not in have_fx]
            e["writable"] = bool(e["payload"]) and not miss
            e["why"] = "" if e["writable"] else ("needs effect " + ", ".join(miss) if miss else "no Data/data.json")
            allx.append(e)
        down_ids = {e["res_id"] for e in down}
        down_keys = {(e["scene"], _norm(e["name"])) for e in down}
        for e in online:
            if e["res_id"] in down_ids:
                continue
            twin = by_name.get((e["scene"], _norm(e["name"]))) or by_name.get((e["scene"], _norm(re.sub(r"^(27_)?text_(in|out|loop)_", "", e["slug"] or ""))))
            if twin:
                # written exactly like the bundled twin (no cloud userData: the cloud copy is not on disk)
                e.update(payload=twin["payload"], origin_length=twin["origin_length"], kind=twin["kind"], engine=twin["engine"],
                         twin=twin["uuid"], res_info=None)
                e["writable"], e["why"] = True, ""
            else:
                e["writable"], e["why"] = False, "online only - download it once in Filmora's text Animation panel"
            allx.append(e)
        online_keys = {(e["scene"], _norm(e["name"])) for e in online}
        for e in bundled:
            e["writable"], e["why"] = bool(e["payload"]), ("" if e["payload"] else "no preset json")
            e["also_online"] = (e["scene"], _norm(e["name"])) in online_keys or (e["scene"], _norm(e["name"])) in down_keys
            allx.append(e)
        for e in _legacy(inst):
            e["writable"], e["why"] = False, "legacy (pre-Filmora 13) title animation - not written by this module"
            allx.append(e)
        _cache = allx
    return [e for e in _cache if scene is None or e["scene"] == scene]


def find(name, scene):
    """Resolve a preset by English/Arabic name, slug, cloud id or engine id for one scene. Prefers downloaded, then
    online+bundled twin, then bundled; raises with suggestions if nothing writable matches."""
    q = _norm(name)
    if not q:
        raise KeyError("empty animation name")
    rank = {"downloaded": 0, "online": 1, "bundled": 2}
    hits = [e for e in list_text_animations(scene) if e["writable"] and q in
            {_norm(e["name"]), _norm(e.get("name_ar") or ""), _norm(e.get("slug") or ""), _norm(e.get("res_id") or ""),
             _norm(re.sub(r"^(27_)?text_(in|out|loop)_", "", e.get("slug") or ""))}]
    if not hits:
        hits = [e for e in list_text_animations(scene) if e["writable"] and _norm(e.get("engine") or "") == q]
    if not hits:
        near = [e["name"] for e in list_text_animations(scene) if q[:4] in _norm(e["name"])][:8]
        raise KeyError(f"no writable {scene}-animation '{name}'" + (f" (close: {', '.join(near)})" if near else ""))
    return sorted(hits, key=lambda e: rank.get(e["source"], 9))[0]


# ------------------------------------------------------------------ writing
def _ud(key, raw):
    return {"data": base64.b64encode(raw).decode(), "key": key, "size": len(raw)}


def build_animation(entry, dur_sec):
    """The dict Filmora stores under inAnimation/outAnimation/loopAnimation (keys sorted like Filmora writes them)."""
    a = copy.deepcopy(entry["payload"])
    a["duration"] = int(round(dur_sec * TICKS))
    if a.get("type") == 6:
        a["originLength"] = entry.get("origin_length") or a["duration"]
    ud = []
    if entry.get("deps"):
        ud.append(_ud(112, json.dumps({"res": entry["deps"]}, separators=(",", ":")).encode() + b"\0"))
    if entry.get("res_info"):
        ud.append(_ud(12, json.dumps(entry["res_info"], separators=(",", ":")).encode()))
    if ud:
        a["userData"] = ud
    return dict(sorted(a.items()))


def default_duration(entry, scene):
    if entry.get("kind") == "mg2d":
        return MG2D_DEFAULT
    if scene == "loop" and entry.get("origin_length"):
        return entry["origin_length"] / TICKS
    return OTHER_DEFAULT


def apply_text_animation(wrapper_clip, inner_clip, scriptbuf_dict=None, in_=None, out=None, in_dur=None, out_dur=None,
                         loop=None, loop_dur=None):
    """Put Filmora preset animations on a text made by Project.title_clip().
    wrapper_clip: the type-7 clip title_clip() returned (only checked, never changed - Filmora leaves it alone);
    inner_clip: the type-4 clip of that text's title timeline (see inner_clip_of());
    scriptbuf_dict: optional parsed scriptBuf - a stale legacy "Animation" key is removed (inner scriptBuf is fixed too);
    in_/out/loop: preset name (English or Arabic UI name, slug, cloud id or engine id like "MG_2d_09"), or None;
    in_dur/out_dur: seconds (default: Filmora's 1.5 s for per-character MG presets, else 1.0 s); MG presets max 5 s;
    in + out are scaled down to fit inside the clip. loop_dur: seconds of one loop cycle (default: the preset's own).
    Returns the inner clip."""
    if wrapper_clip is not None and inner_clip.get("type") != 4:
        raise ValueError("inner_clip must be the type-4 title clip inside the text's title timeline")
    clip_sec = (inner_clip["tlEnd"] - inner_clip["tlBegin"]) / TICKS
    inner_clip.pop("animation", None)                                     # legacy key: never mix with the new ones
    plan = {}
    for scene, name, dur in (("in", in_, in_dur), ("out", out, out_dur), ("loop", loop, loop_dur)):
        if name:
            e = find(name, scene)
            d = dur if dur is not None else default_duration(e, scene)
            if e.get("kind") == "mg2d":
                d = min(d, MG2D_MAX)
            plan[scene] = [e, max(0.1, float(d))]
    io = sum(plan[s][1] for s in ("in", "out") if s in plan)
    if io > clip_sec * 0.95:                                              # keep a few frames of the still text
        f = clip_sec * 0.95 / io
        for s in ("in", "out"):
            if s in plan:
                plan[s][1] *= f
    for scene in ("in", "out", "loop"):
        if scene in plan:
            inner_clip[KEYS[scene]] = build_animation(plan[scene][0], plan[scene][1])
        else:
            inner_clip.pop(KEYS[scene], None)
    if scriptbuf_dict is not None:
        scriptbuf_dict.pop("Animation", None)
    try:
        s = json.loads(inner_clip.get("scriptBuf") or "{}")
        if "Animation" in s:
            s.pop("Animation")
            inner_clip["scriptBuf"] = json.dumps(s, ensure_ascii=False, separators=(",", ":"))
            inner_clip["scriptBufSize"] = len(inner_clip["scriptBuf"].encode()) + 1
    except ValueError:
        pass
    return inner_clip


def inner_clip_of(project, wrapper_clip):
    """The type-4 clip inside the title timeline a wrapper points to (Project.title_tls)."""
    for tl in project.title_tls:
        if tl["timelineId"] == wrapper_clip["timelineId"]:
            return tl["trackInfos"][0]["clipList"][0]
    raise KeyError("title timeline not found for this wrapper")


def animate(project, wrapper_clip, **kw):
    """Shortcut: animate(p, p.title_clip(...), in_="Appearing Verbatim", out="Fade1", in_dur=0.8)."""
    apply_text_animation(wrapper_clip, inner_clip_of(project, wrapper_clip), None, **kw)
    return wrapper_clip


# ------------------------------------------------------------------ CLI
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    items = list_text_animations()
    if not args:
        from collections import Counter
        c = Counter((e["scene"], e["source"], e["writable"]) for e in items)
        print("install folder:", install_dir())
        for k in sorted(c):
            print(f"  {k[0]:<6} {k[1]:<10} {'writable' if k[2] else 'not writable':<13} {c[k]}")
        sys.exit(0)
    if args[0] == "list":
        sel = [e for e in items if len(args) < 2 or e["scene"] == args[1]]
    elif args[0] == "search":
        q = _norm(" ".join(args[1:]))
        sel = [e for e in items if q in _norm(e["name"]) or q in _norm(e.get("name_ar") or "") or q in _norm(e.get("slug") or "")
               or q in _norm(e.get("engine") or "")]
    else:
        print(__doc__)
        sys.exit(1)
    for e in sorted(sel, key=lambda e: (e["scene"], not e["writable"], e["source"], str(e["name"]))):
        print(f"{e['scene']:<6} {'OK ' if e['writable'] else '-- '} {e['source']:<10} {e['kind']:<10} {str(e['name']):<36} "
              f"{(e.get('name_ar') or ''):<24} {str(e.get('engine') or '')[:38]:<38} {e.get('slug') or ''}  {e.get('why', '')}")
