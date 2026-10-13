"""Render design elements as crisp transparent PNGs (HTML/SVG -> Chromium -> PNG) for use as image clips in a spec.

    python render_png.py plate  --w 900 --h 150 --color "#000000" --opacity 0.55 --radius 36 --out plate.png
    python render_png.py bar    --w 700 --h 110 --color "#070B14" --accent "#C6FF3D"  # body, side strip --out lower_third.png
    python render_png.py bg     --w 1080 --h 1920 --color "#132036" --to "#070B14" [--grid] --out bg.png
    python render_png.py glow   --w 600 --h 600 --color "#3DE0FF" --out glow.png         # soft radial light blob
    python render_png.py frame  --w 760 --h 1000 --color "#C6FF3D" --radius 40 --stroke 8 --out frame.png
    python render_png.py html   page.html --w 1080 --h 1920 --out art.png               # any custom HTML/SVG
    python render_png.py svg    icon.svg --w 400 --h 400 --out icon.png

Output is rendered at --scale 2 (default) for sharpness; place it with "scale" in the spec (100 = fit frame, so a
900 px wide plate on a 1080 frame ≈ scale 83 when it is the image's full width — see filmora-design-system).
Fonts: any installed font can be used in custom HTML via font-family "Family" names as installed.
"""
import argparse, os, sys


def render(html, w, h, out, scale=2.0, transparent=True):
    from playwright.sync_api import sync_playwright
    page = (f"<html><head><meta charset='utf-8'><style>html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;"
            f"background:{'transparent' if transparent else '#000'}}}</style></head><body>{html}</body></html>")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
        pg.set_content(page)
        pg.wait_for_timeout(400)
        pg.screenshot(path=out, omit_background=transparent, clip={"x": 0, "y": 0, "width": w, "height": h})
        b.close()
    return os.path.abspath(out)


def rgba(hexc, a=1.0):
    h = hexc.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def element(kind, a):
    W, H, c = a.w, a.h, a.color
    if kind == "plate":
        return f"<div style='width:{W}px;height:{H}px;border-radius:{a.radius}px;background:{rgba(c, a.opacity)}'></div>"
    if kind == "bar":
        return (f"<div style='position:relative;width:{W}px;height:{H}px'>"
                f"<div style='position:absolute;left:0;top:0;width:{H * 0.12}px;height:{H}px;background:{a.accent}'></div>"
                f"<div style='position:absolute;left:{H * 0.18}px;top:0;right:0;height:{H}px;border-radius:0 {a.radius}px {a.radius}px 0;"
                f"background:{rgba(c, a.opacity)}'></div></div>")
    if kind == "bg":
        to = a.to or "#000000"
        grid = (f"<svg width='{W}' height='{H}' style='position:absolute;inset:0'><g stroke='white' stroke-opacity='.07'>"
                + "".join(f"<line x1='{x}' y1='0' x2='{x}' y2='{H}'/>" for x in range(0, W + 1, 90))
                + "".join(f"<line x1='0' y1='{y}' x2='{W}' y2='{y}'/>" for y in range(0, H + 1, 90)) + "</g></svg>") if a.grid else ""
        return (f"<div style='position:relative;width:{W}px;height:{H}px;background:radial-gradient(ellipse at 50% 42%,{c} 0%,{to} 75%)'>"
                f"{grid}<div style='position:absolute;inset:0;background:radial-gradient(ellipse at center,transparent 60%,rgba(0,0,0,.6))'></div></div>")
    if kind == "glow":
        return f"<div style='width:{W}px;height:{H}px;background:radial-gradient(circle,{rgba(c, .9)} 0%,{rgba(c, .35)} 30%,transparent 70%)'></div>"
    if kind == "frame":
        s = a.stroke
        return (f"<div style='box-sizing:border-box;width:{W}px;height:{H}px;border:{s}px solid {c};border-radius:{a.radius}px;"
                f"box-shadow:0 0 {s * 3}px {rgba(c, .7)}, inset 0 0 {s * 3}px {rgba(c, .5)}'></div>")
    raise SystemExit(f"unknown element {kind}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["plate", "bar", "bg", "glow", "frame", "html", "svg"])
    ap.add_argument("src", nargs="?", help="file for html/svg")
    ap.add_argument("--w", type=int, required=True); ap.add_argument("--h", type=int, required=True)
    ap.add_argument("--color", default="#000000"); ap.add_argument("--to"); ap.add_argument("--accent", default="#C6FF3D")
    ap.add_argument("--opacity", type=float, default=0.6); ap.add_argument("--radius", type=float, default=24)
    ap.add_argument("--stroke", type=float, default=6); ap.add_argument("--grid", action="store_true")
    ap.add_argument("--scale", type=float, default=2.0); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.kind in ("html", "svg"):
        html = open(a.src, encoding="utf-8").read()
        if a.kind == "svg":
            html = f"<div style='width:{a.w}px;height:{a.h}px'>{html.replace('<svg', '<svg width=\"100%\" height=\"100%\"', 1)}</div>"
    else:
        html = element(a.kind, a)
    print(render(html, a.w, a.h, a.out, a.scale, transparent=a.kind != "bg"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
