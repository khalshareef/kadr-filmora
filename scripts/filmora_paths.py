"""Where things live — read from Filmora's own settings, overridable per user.

Priority: user config (%LOCALAPPDATA%/kadr/config.json) > FilmoraSettings.xml > Filmora defaults.

    python filmora_paths.py                          # show the resolved paths
    python filmora_paths.py set project_dir "G:/Filmora Projects"   # save projects on another drive
    python filmora_paths.py set project_dir default                 # back to Filmora's folder
"""
import json, os, re, sys

APPDATA_F = os.path.join(os.path.expandvars("%APPDATA%"), "Wondershare", "Wondershare Filmora")
CONFIG = os.path.join(os.path.expandvars("%LOCALAPPDATA%"), "kadr", "config.json")


def _setting(tag):
    try:
        s = open(os.path.join(APPDATA_F, "FilmoraSettings.xml"), encoding="utf-8", errors="replace").read()
        m = re.search(rf"<{tag}>\s*([^<]*?)\s*</{tag}>", s)
        return m.group(1).strip() if m and m.group(1).strip() else None
    except OSError:
        return None


def _config():
    try:
        return json.load(open(CONFIG, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def project_dir():
    """Folder new .wfp files are written to: saved preference, else the current working directory (the folder the
    Claude Code conversation was opened in)."""
    return _config().get("project_dir") or os.getcwd()


def filmora_projects_dir():
    """Filmora's own default project folder (used to find the user's projects, e.g. for template extraction)."""
    return _setting("DefaultProjectSaveFolder") or os.path.join(APPDATA_F, "Projects")


def download_dir():
    """Filmora's downloaded effects/filters/transitions library (…/Download/Filmora)."""
    d = _setting("DownloadFileFolder")
    base = d if d and os.path.isdir(os.path.join(d, "Filmora")) else os.path.join(APPDATA_F, "Download")
    return os.path.join(base, "Filmora")


def library_xml():
    """Filmora's home-screen project list (its own spelling)."""
    return os.path.join(APPDATA_F, "ProjectLibarays.xml")


def log_dir():
    root = os.path.join(os.path.expandvars("%LOCALAPPDATA%"), "..", "LocalWondershare", "Wondershare Filmora")
    root = os.path.normpath(root)
    vers = sorted((d for d in os.listdir(root) if re.match(r"\d+\.\d+", d)), key=lambda v: [int(x) for x in v.split(".")]) if os.path.isdir(root) else []
    return os.path.join(root, vers[-1], "log") if vers else None


def installed_versions():
    """(editor_version, vbl_version) of the installed Filmora, read from the newest project it saved itself; a project
    stamped with an older version makes Filmora ask to back it up on every open. Falls back to the log folder name."""
    import glob, zipfile
    best = None
    files = sorted(glob.glob(os.path.join(filmora_projects_dir(), "**", "*.wfp"), recursive=True), key=os.path.getmtime, reverse=True)
    for f in files[:40]:
        try:
            info = json.loads(zipfile.ZipFile(f).read("ProjectFolder/project_info.json"))
            v = (info["project_editor_modify_version"], info["vbl_modify_version"])
        except Exception:
            continue
        key = [int(x) for x in v[0].split(".") if x.isdigit()]
        if best is None or key > best[0]:
            best = (key, v)
    logv = os.path.basename(os.path.dirname(log_dir() or "")) or None
    if best and (not logv or [int(x) for x in logv.split(".")] <= best[0]):
        return best[1]
    return (logv, None) if logv else (None, None)


def resolve_project(arg):
    """A project name or relative path -> full path: tried in the current folder, the saved project_dir, then
    Filmora's own Projects folder. ".wfp" may be omitted."""
    names = [arg] if arg.lower().endswith(".wfp") else [arg + ".wfp", arg]
    if os.path.isabs(arg):
        return next((n for n in names if os.path.isfile(n)), names[0])
    for base in (os.getcwd(), project_dir(), filmora_projects_dir()):
        for n in names:
            if os.path.isfile(os.path.join(base, n)):
                return os.path.abspath(os.path.join(base, n))
    return os.path.abspath(names[0])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) >= 4 and sys.argv[1] == "set":
        cfg = _config()
        if sys.argv[3] == "default":
            cfg.pop(sys.argv[2], None)
        else:
            os.makedirs(sys.argv[3], exist_ok=True)
            cfg[sys.argv[2]] = sys.argv[3].replace("\\", "/")
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        json.dump(cfg, open(CONFIG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    pd = project_dir() if _config().get("project_dir") else f"(current folder) {os.getcwd()}"
    for k, v in [("project_dir", pd), ("filmora_projects", filmora_projects_dir()), ("download_dir", download_dir()), ("library_xml", library_xml()), ("log_dir", log_dir()),
                 ("config", CONFIG)]:
        print(f"{k:13} {v}")
