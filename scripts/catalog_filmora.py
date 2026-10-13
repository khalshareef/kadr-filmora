"""Catalog every effect / filter / overlay / transition installed (downloaded) in the user's Filmora.

    python catalog_filmora.py                 # (re)build the catalog
    python catalog_filmora.py search glitch   # search by English/Arabic name, slug or category
    python catalog_filmora.py list transition # list one category (transition, overlay, filter, resFilterNew)

Catalog: %LOCALAPPDATA%/kadr/catalog.json. Source of truth for each resource:
  Download/Filmora/<category>/<folder>/resinfo.json  -> id, slug, type, titles (en/ae)
  .../Data/filter.xml                                 -> GUID, Name, Transition flag
  .../*.conf                                          -> PARAMS (name, type, default, min, max)
"""
import glob, json, os, re, sys, xml.etree.ElementTree as ET

import filmora_paths
DL = filmora_paths.download_dir()
OUT = os.path.join(os.path.expandvars("%LOCALAPPDATA%"), "kadr", "catalog.json")
CATS = ["filter", "overlay", "transition", "resFilterNew", "resAITransition", "resAdjustLayer", "videoeffects"]
_cache = None


def _xml(path):
    try:
        t = open(path, encoding="utf-8", errors="replace").read().strip()
        return ET.fromstring(t[t.find("<"):])
    except Exception:
        return None


def _params(folder):
    for conf in glob.glob(os.path.join(folder, "**", "*.conf"), recursive=True):
        try:
            j = json.loads(re.sub(r",\s*([}\]])", r"\1", open(conf, encoding="utf-8", errors="replace").read()))
        except Exception:
            continue
        ps = [{"name": p.get("NAME"), "type": str(p.get("TYPE", "float")).lower(), "default": p.get("DEFAULT"),
               "min": p.get("MIN"), "max": p.get("MAX")} for p in j.get("PARAMS", [])]
        if ps:
            return ps
    return []


def build():
    cat = []
    for c in CATS:
        for folder in sorted(glob.glob(os.path.join(DL, c, "*"))):
            if not os.path.isdir(folder):
                continue
            fx = next((x for x in (_xml(p) for p in glob.glob(os.path.join(folder, "**", "filter.xml"), recursive=True))
                       if x is not None and x.findtext("GUID")), None)
            if fx is None:
                continue                      # elements/templates without a filter definition are not effects
            try:
                info = json.load(open(os.path.join(folder, "resinfo.json"), encoding="utf-8"))
            except Exception:
                info = {}
            t = info.get("titles", {})
            cat.append({"category": c, "guid": fx.findtext("GUID").strip(), "name": (fx.findtext("Name") or "").strip(),
                        "is_transition": (fx.findtext("Transition") or "0").strip() == "1" or c in ("transition", "resAITransition"),
                        "slug": info.get("slug") or os.path.basename(folder), "res_id": info.get("id"), "res_type": info.get("type"),
                        "source": info.get("source", 0), "sale_mode": info.get("sale_mode", 0),
                        "title_en": t.get("en", ""), "title_ar": t.get("ae", ""), "params": _params(folder)})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(cat, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return cat


def load():
    global _cache
    if _cache is None:
        _cache = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else build()
    return _cache


def find(name):
    """Exact slug first, then English title, then internal name, then Arabic title (titles can collide)."""
    key = name.lower().strip()
    for field in ("slug", "title_en", "name", "title_ar"):
        for c in load():
            if c[field].lower() == key:
                return c
    raise KeyError(f"'{name}' is not installed in this Filmora (download it inside Filmora, then rebuild the catalog)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) == 1:
        from collections import Counter
        cat = build()
        print("catalog:", OUT, len(cat), dict(Counter(c["category"] + (" (transition)" if c["is_transition"] else "") for c in cat)))
    elif sys.argv[1] == "search":
        q = " ".join(sys.argv[2:]).lower()
        for c in load():
            if q in f'{c["title_en"]} {c["name"]} {c["slug"]} {c["title_ar"]} {c["category"]}'.lower():
                print(f'{c["category"]:13} {c["slug"]:42} {c["title_en"] or c["name"]:36} {c["title_ar"]}')
    elif sys.argv[1] == "list":
        for c in load():
            if c["category"] == sys.argv[2] or (sys.argv[2] == "transition" and c["is_transition"]):
                print(f'{c["slug"]:42} {c["title_en"] or c["name"]:36} {c["title_ar"]}')
