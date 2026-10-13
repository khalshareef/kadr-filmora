"""Find installed fonts by Filmora's font name ("Family Style", e.g. "Alexandria Black") and measure shaped text width.

Filmora sizes a title's box from the rendered text; we measure the same text with Chromium (correct Arabic shaping)
so the box matches and the text is not stretched.
"""
import glob, os

FONT_DIRS = [os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts"), r"C:\Windows\Fonts"]
_cache = None


def font_index():
    """{ "family style" (lowercase): path } for every installed TTF/OTF."""
    global _cache
    if _cache is None:
        from PIL import ImageFont
        _cache = {}
        for d in FONT_DIRS:
            for p in glob.glob(os.path.join(d, "*.[ot]tf")) + glob.glob(os.path.join(d, "*.[OT]TF")):
                try:
                    fam, sty = ImageFont.truetype(p, 10).getname()
                except Exception:
                    continue
                _cache.setdefault(f"{fam} {sty}".lower(), p)
                if sty.lower() == "regular":
                    _cache.setdefault(fam.lower(), p)
    return _cache


def font_file(name):
    idx = font_index()
    key = name.lower()
    if key in idx:
        return idx[key]
    for k, p in idx.items():          # tolerant match: "Alexandria Black" vs "Alexandria Black Regular"
        if k.startswith(key) or key.startswith(k):
            return p
    raise FileNotFoundError(f"Font '{name}' is not installed (Filmora can only use installed fonts).")


def measure(items):
    """items: [(text, font_name)] -> [width of the text at font-size 1px]"""
    from playwright.sync_api import sync_playwright
    fonts = sorted({f for _, f in items})
    fam = {f: f"F{i}" for i, f in enumerate(fonts)}
    css = "".join(f"@font-face{{font-family:{fam[f]};src:url('file:///{font_file(f).replace(os.sep, '/')}')}}" for f in fonts)
    spans = "".join(f"<span id=s{i} style='font-family:{fam[f]};font-size:100px;white-space:pre'>{t}</span><br>"
                    for i, (t, f) in enumerate(items))
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        # fonts load from file:// only when the page itself is a file (set_content pages can't reach local files)
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "kadr_measure.html")
        open(tmp, "w", encoding="utf-8").write(f"<html dir=rtl><meta charset=utf-8><style>{css}</style>{spans}</html>")
        pg.goto("file:///" + tmp.replace(os.sep, "/"))
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(200)
        out = [pg.evaluate(f"document.getElementById('s{i}').getBoundingClientRect().width") / 100 for i in range(len(items))]
        b.close()
    return out


def screen_width(text, font, size, frame_w):
    """On-screen width in px of a single-line Filmora text at `size` and scale 100 (Filmora: em = 1.5*size*W/1920 px)."""
    return measure([(text, font)])[0] * 1.5 * size * frame_w / 1920


if __name__ == "__main__":
    import argparse, sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="List installed fonts, or measure how wide a text will be on screen.")
    ap.add_argument("text", nargs="?"); ap.add_argument("--font", default="Arial"); ap.add_argument("--size", type=float, default=60)
    ap.add_argument("--width", type=int, default=1080, help="project width in px"); ap.add_argument("--fonts", help="filter installed fonts")
    a = ap.parse_args()
    if a.text is None:
        print("\n".join(k for k in sorted(font_index()) if not a.fonts or a.fonts.lower() in k))
    else:
        for line in a.text.replace("\\n", "\n").split("\n"):
            px = screen_width(line, a.font, a.size, a.width)
            print(f"{px:7.0f} px  = {px / a.width:.0%} of the frame width   {line}")
        print(f"glyph height (1 em) ~ {1.5 * a.size * a.width / 1920:.0f} px")
