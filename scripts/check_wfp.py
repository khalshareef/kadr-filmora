"""Validate a .wfp the way Filmora does on open (integrity stamps + structure), before handing it to the user.

    python check_wfp.py "C:/.../Projects/My Project.wfp" [more.wfp ...]
    python check_wfp.py "My Project"              # bare names resolve in the project folder (filmora_paths.py)
Exit code 1 if any check fails.
"""
import base64, hashlib, json, os, sys, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import filmora_paths  # noqa: E402
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
bad = False
for arg in sys.argv[1:]:
    path = filmora_paths.resolve_project(arg)
    z = zipfile.ZipFile(path)
    info = json.loads(z.read("ProjectFolder/project_info.json"))
    mid = info["timeline_mediaId"]
    d = json.loads(z.read(f"ProjectFolder/Medias/{mid}/timeline.wesproj"))
    main = d["timelineInfos"][0]
    k140 = [base64.b64decode(u["data"]).decode() for u in main["userData"] if u["key"] == 140]
    tl_ids = {t["timelineId"] for t in d["timelineInfos"]}
    res_files = {r["filename"] for r in d["resources"]}
    clips = [c for t in main["trackInfos"] for c in t.get("clipList", [])]
    missing = sorted({c["filename"][6:] for c in clips if "filename" in c and not os.path.exists(c["filename"][6:])})
    checks = {
        "suffix .wfp": info["project_file_suffix"] == ".wfp",
        "editor Filmora": info["project_editor_name"] == "Filmora",
        "project_source stamp": info["project_source"] == hashlib.md5(f"Filmora{info['project_date_modify']}".encode()).hexdigest(),
        "timeline key-140 stamp": hashlib.md5(("Filmora" + mid).encode()).hexdigest() in k140,
        "title timelines exist": all(c["timelineId"] in tl_ids for c in clips if c.get("type") == 7),
        "media in resources": all(c["filename"] in res_files for c in clips if "filename" in c),
        "media files on disk": not missing,
        "bufsize = utf8+1": all(c.get(k + "Size") == len(c[k].encode()) + 1 for t in d["timelineInfos"]
                                for tr in t["trackInfos"] for c in tr.get("clipList", []) for k in ("scriptBuf", "pipBuf") if k in c),
    }
    ok = all(checks.values())
    bad |= not ok
    print(("OK  " if ok else "FAIL") + f"  {os.path.basename(path)}  clips={len(clips)}  duration={info['project_timeline_duration'] / 1e7:.2f}s")
    for k, v in checks.items():
        if not v:
            print("      x", k, missing if k == "media files on disk" else "")
sys.exit(1 if bad else 0)
