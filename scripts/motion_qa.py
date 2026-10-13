"""Quality checks for rendered motion before handing it over.

    python motion_qa.py contact "stills/*.png" --out board.jpg [--cols 5]   # contact sheet of storyboard stills
    python motion_qa.py pops clip.mp4 [more.mp4 …] [--factor 6]           # find single-frame pops / glitches

pops: flags frames that differ from both neighbours while the neighbours match each other — the classic "something
blinked for one frame" bug (a value jumping for one frame, an element flashing, a glitchy camera frame). Normal motion
onsets are not flagged.
"""
import argparse, glob, subprocess, sys


def contact(pattern, out, cols=5, w=324):
    from PIL import Image
    files = sorted(glob.glob(pattern))
    if not files:
        raise SystemExit(f"no files match {pattern}")
    ims = [Image.open(f).convert("RGB") for f in files]
    h = int(w * ims[0].height / ims[0].width)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (w + 8) + 8, rows * (h + 8) + 8), (255, 255, 255))
    for i, im in enumerate(ims):
        sheet.paste(im.resize((w, h)), (8 + (i % cols) * (w + 8), 8 + (i // cols) * (h + 8)))
    sheet.save(out, quality=88)
    return out


def pops(path, factor=6.0):
    import numpy as np
    w, h = 96, 160
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    diff = lambda a, b: float(np.abs(fr[a] - fr[b]).mean())
    flagged = []
    for i in range(1, len(fr) - 1):          # frame i is a pop if it differs from both neighbours, which match each other
        da, db, skip = diff(i - 1, i), diff(i, i + 1), diff(i - 1, i + 1)
        if min(da, db) > 1.0 and min(da, db) > factor * max(skip, 0.05) / 2:
            flagged.append((i, round(min(da, db), 2), round(skip, 2)))
    return len(fr), flagged


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["contact", "pops"]); ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out", default="contact.jpg"); ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--factor", type=float, default=6.0)
    a = ap.parse_args()
    if a.cmd == "contact":
        print(contact(a.inputs[0], a.out, a.cols))
    else:
        for p in a.inputs:
            n, fl = pops(p, a.factor)
            print(f"{p}: {n} frames, {len(fl)} suspicious" + "".join(f"\n  frame {f}: change {c} vs neighbours {b}" for f, c, b in fl[:20]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
