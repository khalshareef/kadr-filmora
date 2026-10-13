"""Find the good fonts installed on this PC (like Filmora does) and render specimen sheets so they can be chosen by eye.

    python font_scout.py list [--arabic] [--latin] [--all]          # families, weights, scripts (dated system fonts hidden)
    python font_scout.py specimen --text "هل تفهم الآلة لهجتك؟" [--arabic] [--families "Cairo,Tajawal"] [--out fonts.png]
                                  [--sub "نص الكابشن"] [--bg "#F0EEE6"] [--ink "#141413"] [--per-page 16]

Fonts are read from Windows Fonts and the user's own fonts folder. For each family: weights available (with the
exact Filmora names, "Family Style"), Arabic / Latin coverage, and a tag: quran (Quranic script — only for Quranic
text), decorative (calligraphic/handwritten/display), or text. System fonts that look dated (Arial, Tahoma, Times,
Segoe, Traditional/Simplified Arabic…) are hidden unless --all.
The specimen shows the real headline in the heaviest weight and an optional caption line in a medium weight, both in
the SAME family — to choose a Latin font for English sublines, render a separate --latin sheet. When the fonts need
more than one page, --out fonts.png writes fonts_1.png, fonts_2.png, ... (the paths are printed).
"""
import argparse, glob, json, os, sys, tempfile
from collections import defaultdict

FONT_DIRS = [os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts"), r"C:\Windows\Fonts"]
DATED = {"arial", "tahoma", "times new roman", "courier new", "segoe ui", "segoe ui variable", "segoe ui historic", "segoe print",
         "segoe script", "microsoft sans serif", "sylfaen", "ebrima", "gadugi", "leelawadee ui", "javanese text", "calibri",
         "cambria", "candara", "constantia", "corbel", "lucida console", "lucida sans unicode", "sans serif collection",
         "palatino linotype", "trebuchet ms", "verdana", "georgia", "comic sans ms", "mistral", "gabriola", "simplified arabic",
         "traditional arabic", "arabic typesetting", "sakkal majalla", "urdu typesetting", "aldhabi", "andalus",
         "microsoft uighur", "franklin gothic medium", "malgun gothic", "mv boli", "ink free", "impact", "bahnschrift"}
QURAN = ("kfgqpc", "uthman", "hafs", "quran", "amiri quran", "me_quran")
DECOR = ("ruqaa", "diwani", "thuluth", "naskh old", "kalam", "caveat", "vibes", "script", "marker", "sketch", "brush",
         "galaxy", "ghareeb", "forsha", "scribble", "lemon", "bangers", "shrikhand", "sigmar", "lalezar", "blaka", "marhey",
         "free palestine", "3asomy", "heaven", "modal3at", "trika", "foda", "momken")
WEIGHT = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}


def scan():
    from fontTools.ttLib import TTFont
    fams = defaultdict(lambda: {"styles": {}, "arabic": False, "latin": False})
    for d in FONT_DIRS:
        for p in glob.glob(os.path.join(d, "*.[ot]tf")) + glob.glob(os.path.join(d, "*.[OT]TF")):
            try:
                f = TTFont(p, lazy=True, fontNumber=0)
                nm = f["name"]
                fam = (nm.getDebugName(16) or nm.getDebugName(1) or "").strip()
                sty = (nm.getDebugName(17) or nm.getDebugName(2) or "Regular").strip()
                cmap = f.getBestCmap() or {}
                w = f["OS/2"].usWeightClass if "OS/2" in f else 400
            except Exception:
                continue
            if not fam or len(cmap) < 60:
                continue                                       # icon / symbol fonts
            e = fams[fam]
            e["styles"][sty] = {"path": p, "weight": w, "italic": "italic" in sty.lower()}
            e["arabic"] |= all(c in cmap for c in (0x627, 0x644, 0x645, 0x647, 0x628, 0x6CC if False else 0x64A))
            e["latin"] |= all(c in cmap for c in range(0x41, 0x5B))
    out = {}
    for fam, e in fams.items():
        low = fam.lower()
        tag = "quran" if any(q in low for q in QURAN) else "decorative" if any(k in low for k in DECOR) else "text"
        out[fam] = dict(e, tag=tag, dated=low in DATED or low.startswith(("segoe", "microsoft", "opus", "simsun")))
    return out


def heaviest(e, upright=True):
    st = [(v["weight"], s) for s, v in e["styles"].items() if not (upright and v["italic"])] or [(v["weight"], s) for s, v in e["styles"].items()]
    return max(st)[1]


def medium(e):
    st = [(abs(v["weight"] - 500), s) for s, v in e["styles"].items() if not v["italic"]] or [(0, next(iter(e["styles"])))]
    return min(st)[1]


def pick(fams, arabic=False, latin=False, show_all=False, names=None):
    res = []
    for fam, e in sorted(fams.items()):
        if names and fam.lower() not in names:
            continue
        if not names and ((e["dated"] and not show_all) or (arabic and not e["arabic"]) or (latin and not e["latin"])):
            continue
        res.append((fam, e))
    return res


def specimen(items, text, sub, out, bg, ink, per_page=16):
    from playwright.sync_api import sync_playwright
    pages = [items[i:i + per_page] for i in range(0, len(items), per_page)]
    made = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for n, chunk in enumerate(pages, 1):
            css, rows = "", ""
            for k, (fam, e) in enumerate(chunk):
                h, m = heaviest(e), medium(e)
                for tagname, sty in (("h", h), ("m", m)):
                    css += f"@font-face{{font-family:F{k}{tagname};src:url('file:///{e['styles'][sty]['path'].replace(os.sep, '/')}')}}"
                label = f"{fam} — {h}" + (f" / {m}" if m != h else "") + f"  [{e['tag']}{', AR' if e['arabic'] else ''}{', EN' if e['latin'] else ''}]"
                rows += (f"<div class=row><div class=lab>{label}</div><div style=\"font-family:F{k}h;font-size:64px\">{text}</div>"
                         + (f"<div style=\"font-family:F{k}m;font-size:34px;opacity:.85\">{sub}</div>" if sub else "") + "</div>")
            html = (f"<html dir={'rtl' if any('؀' <= ch <= 'ۿ' for ch in text) else 'ltr'}><meta charset=utf-8><style>{css}body{{margin:0;background:{bg};color:{ink};width:1600px}}"
                    f".row{{padding:22px 40px;border-bottom:1px solid rgba(0,0,0,.08)}}.lab{{font:14px Consolas,monospace;direction:ltr;"
                    f"text-align:left;opacity:.6;margin-bottom:6px}}</style>{rows}</html>")
            pg = b.new_page(viewport={"width": 1600, "height": 800})
            tmp = os.path.join(tempfile.gettempdir(), "kadr_fonts.html")     # a file page may load file:// fonts
            open(tmp, "w", encoding="utf-8").write(html)
            pg.goto("file:///" + tmp.replace(os.sep, "/"))
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(300)
            path = out if len(pages) == 1 else out.replace(".png", f"_{n}.png")
            pg.screenshot(path=path, full_page=True)
            made.append(path)
        b.close()
    return made


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["list", "specimen"])
    ap.add_argument("--arabic", action="store_true"); ap.add_argument("--latin", action="store_true"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--families"); ap.add_argument("--text", default="كادر يكتب مشروعك ويفتح بفيلمورا Kadr")
    ap.add_argument("--sub", default=""); ap.add_argument("--out", default="fonts.png"); ap.add_argument("--bg", default="#F0EEE6")
    ap.add_argument("--ink", default="#141413"); ap.add_argument("--per-page", type=int, default=16); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    names = {x.strip().lower() for x in a.families.split(",")} if a.families else None
    items = pick(scan(), a.arabic, a.latin, a.all, names)
    if names:
        missing = names - {f.lower() for f, _ in items}
        if missing:
            print("not found (check the spelling, or add --all for hidden system fonts): " + ", ".join(sorted(missing)))
    if a.cmd == "list":
        if a.json:
            print(json.dumps({f: {"tag": e["tag"], "arabic": e["arabic"], "latin": e["latin"], "styles": sorted(e["styles"])} for f, e in items}, ensure_ascii=False, indent=1))
        for fam, e in items:
            ws = sorted(e["styles"].items(), key=lambda kv: kv[1]["weight"])
            print(f"{fam:30} {e['tag']:10} {'AR' if e['arabic'] else '  '} {'EN' if e['latin'] else '  '}  " + ", ".join(s for s, _ in ws))
        print(f"{len(items)} families")
    else:
        for path in specimen(items, a.text, a.sub, a.out, a.bg, a.ink, a.per_page):
            print(path)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
