"""Extract clip/track/title templates from existing Filmora projects into assets/templates.json.

Run this once per machine/Filmora version if the bundled templates ever stop loading:
    python extract_templates.py                # auto-pick projects from the user's Filmora Projects folder
    python extract_templates.py a.wfp b.wfp    # or name explicit projects to scan

Needs at least one project that contains: a title (text) clip, a .png/.jpg image clip and a .wav/.mp3 audio clip
(they can come from different projects). Personal paths are stripped from the result.
"""
import base64, glob, json, os, re, sys, uuid, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "templates.json")
sys.path.insert(0, HERE)
import filmora_paths  # noqa: E402
PROJ_DIR = filmora_paths.filmora_projects_dir()


def projects(args):
    if args:
        return args
    return sorted(glob.glob(os.path.join(PROJ_DIR, "*.wfp")), key=os.path.getmtime, reverse=True)


def main_doc(z):
    info = json.loads(z.read("ProjectFolder/project_info.json"))
    return info, json.loads(z.read(f"ProjectFolder/Medias/{info['timeline_mediaId']}/timeline.wesproj"))


def scrub(clip):
    """Drop user-specific paths/names from a clip template."""
    clip = json.loads(json.dumps(clip))
    if "filename" in clip:
        clip["filename"] = "file:/PLACEHOLDER"
    clip["userData"] = [u for u in clip.get("userData", []) if u["key"] not in (50, 73, 74, 10)]
    return clip


ID_KEYS = {"thisUId", "busUid", "busUuids", "uuid", "sourceUuid"}
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def scrub_ids(obj, key=None, ids=None):
    """Filmora's instance ids end in the PC's network address -> swap them for random ids (same old -> same new).
    Effect/resource GUIDs (other keys) are left alone: they must match the installed effects."""
    ids = {} if ids is None else ids
    if isinstance(obj, dict):
        for k in obj:
            obj[k] = scrub_ids(obj[k], k, ids)
    elif isinstance(obj, list):
        obj[:] = [scrub_ids(v, key, ids) for v in obj]
    elif isinstance(obj, str) and key in ID_KEYS:
        return UUID_RE.sub(lambda m: ids.setdefault(m.group(0).lower(), str(uuid.uuid4())), obj)
    return obj


found = {}
for path in projects(sys.argv[1:]):
    try:
        z = zipfile.ZipFile(path)
        info, doc = main_doc(z)
    except Exception:
        continue
    tls = {t["timelineId"]: t for t in doc["timelineInfos"]}
    main = doc["timelineInfos"][0]
    for ti, tr in enumerate(main["trackInfos"]):
        for c in tr.get("clipList", []):
            if c.get("type") == 7 and "wrapper" not in found and c.get("timelineId") in tls:
                ttl = tls[c["timelineId"]]
                inner = ttl["trackInfos"][0]["clipList"][0] if ttl["trackInfos"] and ttl["trackInfos"][0].get("clipList") else None
                if inner and "scriptBuf" in inner:
                    found["wrapper"] = c
                    found["title_tl"] = ttl
                    found["track_video"] = {k: v for k, v in tr.items() if k != "clipList"}
                    # the audio track paired with this video track sits right before it
                    if ti > 0 and main["trackInfos"][ti - 1]["trackType"] == 2:
                        found["track_audio_pair"] = {k: v for k, v in main["trackInfos"][ti - 1].items() if k != "clipList"}
                    found["track_audio_main"] = {k: v for k, v in main["trackInfos"][0].items() if k != "clipList"}
                    found["main_tl"] = {k: v for k, v in main.items() if k != "trackInfos"}
                    found["doc"] = {k: v for k, v in doc.items() if k not in ("timelineInfos", "resources")}
                    found["info"] = info
                    found["thumb_tl"] = base64.b64encode(z.read(f"ProjectFolder/Medias/{info['timeline_mediaId']}/thumbnail.png")).decode() \
                        if f"ProjectFolder/Medias/{info['timeline_mediaId']}/thumbnail.png" in z.namelist() else ""
    for t in (t for tl in doc["timelineInfos"] for t in tl["trackInfos"]):
        for c in t.get("clipList", []):
            fn = c.get("filename", "").lower()
            if "img_clip" not in found and fn.endswith((".png", ".jpg", ".jpeg")):
                res = next((r for r in doc["resources"] if r["filename"] == c["filename"]), None)
                if res and res.get("streamType") == 5:
                    found["img_clip"], found["img_res"] = c, res
            if "wav_clip" not in found and fn.endswith((".wav", ".mp3", ".m4a")) and c.get("type") == 2:
                res = next((r for r in doc["resources"] if r["filename"] == c["filename"]), None)
                if res and res.get("streamType") == 3:
                    found["wav_clip"], found["wav_res"] = c, res
    if all(k in found for k in ("wrapper", "img_clip", "wav_clip", "track_audio_pair")):
        break

missing = [k for k in ("wrapper", "img_clip", "wav_clip", "track_audio_pair") if k not in found]
if missing:
    sys.exit(f"Could not find templates for: {missing}. Make a small Filmora project with a text, an image and a wav, save it, re-run.")

# scrub personal data
found["img_clip"] = scrub(found["img_clip"])
found["wav_clip"] = scrub(found["wav_clip"])
for k in ("img_res", "wav_res"):
    found[k]["filename"] = "file:/PLACEHOLDER"
for ch in found["wav_clip"]["effectChainList"]:          # third-party plugins (VST) are not portable
    if ch["name"] == "Effect":
        ch["effectList"] = []
found["info"].update(project_file_name="", proj_zip_save_path="", proj_cover_proj_path="", project_guid="")
scrub_ids(found)
json.dump(found, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("templates written:", os.path.abspath(OUT), {k: True for k in found})
