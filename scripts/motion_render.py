"""Render a time-driven HTML/SVG motion page (window.KADR.render(t)) to video clips or still frames.

    python motion_render.py page.html --out scene.mp4                         # whole duration, opaque H.264
    python motion_render.py page.html --cuts 0,3.45,8.16,12.2 --out "S{n}.mp4"  # one clip per section (S1.mp4, S2.mp4…)
    python motion_render.py page.html --alpha --out layer.mov                  # transparent ProRes 4444 (overlay layer)
    python motion_render.py page.html --stills 1.5,6,10.2 --out "frame_{t}.png"  # storyboard frames
    python motion_render.py page.html --layers assets/layers                   # one editable clip per layer + layers.json
    python motion_render.py page.html --cuts … --out "S{n}.mp4" --subframes 4  # real motion blur (4 subframes averaged)

The page must define  window.KADR = {width, height, fps, duration, render(t)}  (see assets/motion/kadr-motion.js,
include it with <script src="…/kadr-motion.js">). Frames are seeked one by one, so timing is exact.
Opaque output: H.264 High, CRF 12, yuv420p (Filmora-friendly). Alpha output: ProRes 4444 with alpha (.mov).
Needs: playwright (chromium) and ffmpeg on PATH.
"""
import argparse, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))


def _ffmpeg(out, w, h, fps, alpha):
    vf = f"scale={w}:{h}:flags=lanczos"
    if alpha:
        # Filmora always reads ProRes alpha as PREMULTIPLIED (its alphaPremultiply flag changes nothing): straight
        # alpha from Chromium gave a light fringe on every edge. Premultiply before scaling/encoding -> clean edges
        # (measured on Filmora snapshots: edge overshoot 25 -> 0.7, projects\alpha_edge_test).
        vf = "format=gbrap10le,premultiply=inplace=1," + vf
        enc = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0"]
    else:
        enc = ["-c:v", "libx264", "-preset", "slow", "-crf", "12", "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart"]
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "png", "-i", "-",
           "-vf", vf, "-r", str(fps)] + enc + [out]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def _blend(pngs):
    """Average subframes -> real motion blur (what ffmpeg tmix does), returns PNG bytes (straight alpha).
    Colours are averaged premultiplied, so a moving edge over transparency doesn't pick up dark/light halos."""
    import io
    import numpy as np
    from PIL import Image
    acc = None
    for b in pngs:
        a = np.asarray(Image.open(io.BytesIO(b)).convert("RGBA"), dtype=np.float32)
        a[..., :3] *= a[..., 3:4] / 255.0
        acc = a if acc is None else acc + a
    acc /= len(pngs)
    alpha = acc[..., 3:4]
    acc[..., :3] = np.where(alpha > 0, acc[..., :3] * 255.0 / np.maximum(alpha, 1e-6), 0)
    out = io.BytesIO()
    Image.fromarray(acc.clip(0, 255).round().astype("uint8"), "RGBA").save(out, "PNG", compress_level=1)
    return out.getvalue()


def render(page, out, start=None, end=None, cuts=None, stills=None, alpha=False, scale=1.0, layers_dir=None, only=None, subframes=1):
    from playwright.sync_api import sync_playwright
    url = "file:///" + os.path.abspath(page).replace("\\", "/")
    made = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.on("pageerror", lambda e: print("page error:", e, file=sys.stderr))
        pg.goto(url)
        pg.wait_for_function("window.KADR && document.fonts.status === 'loaded'", timeout=20000)
        meta = pg.evaluate("({w: KADR.width, h: KADR.height, fps: KADR.fps, d: KADR.duration})")
        w, h, fps, dur = meta["w"], meta["h"], meta["fps"], meta["d"]
        pg.set_viewport_size({"width": w, "height": h})
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
        pg.goto(url)
        pg.wait_for_function("window.KADR && document.fonts.status === 'loaded'", timeout=20000)
        pg.wait_for_timeout(300)
        if alpha:
            pg.evaluate("for (const e of [document.documentElement, document.body]) e.style.background = 'transparent'")
        shot = lambda: pg.screenshot(omit_background=alpha, type="png")

        if layers_dir:                                  # editable layers: KADR.layers + KADR.solo(name)
            import json
            os.makedirs(layers_dir, exist_ok=True)
            todo = pg.evaluate("KADR.layers")
            manifest, t_start = [], time.time()
            for z, L in enumerate(todo):
                if only and L["name"] not in only:
                    continue
                opaque = bool(L.get("opaque"))
                path = os.path.join(layers_dir, f"{z:02d}_{L['name']}" + (".mp4" if opaque else ".mov"))
                pg.evaluate(f"KADR.solo({json.dumps(L['name'])})")
                # a page/body background colour is painted even with omit_background -> clear it for transparent layers
                pg.evaluate("bg => { for (const e of [document.documentElement, document.body]) e.style.background = bg; }",
                            "" if opaque else "transparent")
                ff = _ffmpeg(path, w, h, fps, not opaque)
                f0, f1 = int(round(L["start"] * fps)), int(round(L["end"] * fps))
                for f in range(f0, f1):
                    pg.evaluate(f"KADR.render({f / fps})")
                    ff.stdin.write(pg.screenshot(omit_background=not opaque, type="png"))
                ff.stdin.close()
                ff.wait()
                manifest.append({"name": L["name"], "path": os.path.abspath(path).replace("\\", "/"), "start": f0 / fps,
                                 "end": f1 / fps, "z": z, "opaque": opaque})
                print(f"  layer {L['name']}: {f0 / fps:.2f}-{f1 / fps:.2f}s  {os.path.getsize(path) / 1e6:.1f} MB  "
                      f"{time.time() - t_start:.0f}s elapsed", flush=True)
            pg.evaluate("KADR.solo(null)")
            mpath = os.path.join(layers_dir, "layers.json")
            old = json.load(open(mpath, encoding="utf-8")) if only and os.path.exists(mpath) else []
            keep = {m["name"]: m for m in old}
            keep.update({m["name"]: m for m in manifest})
            json.dump(sorted(keep.values(), key=lambda m: m["z"]), open(mpath, "w", encoding="utf-8"), indent=1)
            made.append(mpath)
        elif stills:
            for t in stills:
                pg.evaluate(f"KADR.render({t})")
                path = out.replace("{t}", f"{t:06.2f}".replace(".", "_"))
                open(path, "wb").write(shot())
                made.append(path)
        else:
            bounds = cuts or [start or 0.0, end or dur]
            t_start = time.time()
            for n, (a, z) in enumerate(zip(bounds, bounds[1:]), 1):
                path = out.replace("{n}", str(n))
                ff = _ffmpeg(path, w, h, fps, alpha)
                f0, f1 = int(round(a * fps)), int(round(z * fps))
                for f in range(f0, f1):
                    if subframes > 1:                    # motion blur: average N moments inside the frame's shutter
                        subs = []
                        for k in range(subframes):
                            pg.evaluate(f"KADR.render({(f + (k + 0.5) / subframes - 0.5) / fps})")
                            subs.append(shot())
                        ff.stdin.write(_blend(subs))
                    else:
                        pg.evaluate(f"KADR.render({f / fps})")
                        ff.stdin.write(shot())
                ff.stdin.close()
                ff.wait()
                made.append(path)
                print(f"  {os.path.basename(path)}: {a:.2f}-{z:.2f}s ({f1 - f0} frames)  {time.time() - t_start:.0f}s elapsed", flush=True)
        b.close()
    return made


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("page"); ap.add_argument("--out")
    ap.add_argument("--start", type=float); ap.add_argument("--end", type=float)
    ap.add_argument("--cuts", help="comma-separated section times; --out must contain {n}")
    ap.add_argument("--stills", help="comma-separated times; --out must contain {t}")
    ap.add_argument("--alpha", action="store_true"); ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--layers", help="output folder: one clip per KADR.layers entry + layers.json")
    ap.add_argument("--only", help="comma-separated layer names to (re)render")
    ap.add_argument("--subframes", type=int, default=1, help="motion-blur subframes per frame (4 recommended, 8 for very fast moves)")
    a = ap.parse_args()
    cuts = [float(x) for x in a.cuts.split(",")] if a.cuts else None
    stills = [float(x) for x in a.stills.split(",")] if a.stills else None
    only = set(a.only.split(",")) if a.only else None
    for path in render(a.page, a.out or "", a.start, a.end, cuts, stills, a.alpha, a.scale, a.layers, only, a.subframes):
        print(path)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
