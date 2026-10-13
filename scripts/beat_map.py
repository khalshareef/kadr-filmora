"""Beat map for music-synced Filmora edits: analyse a track, derive a cut grid, write a ready filmora-core spec.

    python beat_map.py analyze "song.wav" [--start 0] [--duration 60] [--out beats.json]
    python beat_map.py cuts beats.json [--every auto|1|2|4] [--end 30]
    python beat_map.py spec beats.json --media "D:/clips" --name "My Beat Edit" [--style velocity] [--size 1080x1920]
                       [--fit auto|fit|fill|blur] [--fps auto] [--words "يلا!,حفلة!"] [--font "Cairo Black"]
                       [--end 30] [--every auto] [--music-gain -2] [--seed 1]

analyze -> tempo, beats (grid completed to the region edges), downbeats (bar starts), kicks (low-band onsets),
           snares (high-band onsets), per-beat energy 0..1, sections (merged low/mid/high runs), drops (energy jumps up,
           snapped to bar starts) and breaks (energy falls). The region is analysed with 1 s padding on both sides.
cuts    -> cut times: high energy = every beat, mid = every 2, low = every 4 (auto); the bar before a drop goes to every
           beat; the bar after a break is held as one shot.
spec    -> a filmora-core spec: shots on track "main" cut on the grid, punch zoom on kicks, push/pull otherwise,
           transitions (style) only on cuts of 2+ beats, black flash into each drop + hits, bar effects in high sections,
           a look on breaks, optional words on the drops, the music pre-cut to the region. Footage of another aspect is
           handled by --fit: fit (letterbox), fill (crop to fill), blur (blurred copy behind; default when aspects differ).
Times are seconds from the start of the analysed region (--start), which is where the music clip starts.
Needs: pip install librosa numpy (ffprobe/ffmpeg on PATH).
"""
import argparse, glob, json, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
VIDEO_EXT, IMAGE_EXT = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"), (".png", ".jpg", ".jpeg", ".webp")


def analyze(path, start=0.0, duration=None, pad=1.0):
    import numpy as np, librosa
    off = max(0.0, start - pad)
    pre = start - off
    y, sr = librosa.load(path, sr=22050, mono=True, offset=off, duration=(duration + pre + pad) if duration else None)
    length = duration if duration else len(y) / sr - pre
    length = min(length, len(y) / sr - pre)
    hop = 512
    _, bt = librosa.beat.beat_track(y=y, sr=sr, units="time", tightness=120)
    oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    onsets = librosa.onset.onset_detect(onset_envelope=oenv, sr=sr, hop_length=hop, units="time")
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
    f = librosa.fft_frequencies(sr=sr, n_fft=2048)
    norm = lambda a: a / (a.max() or 1)
    low, high = norm(S[f < 150].sum(0)), norm(S[f > 4000].sum(0))
    rms = norm(librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0])
    at = lambda a, t: float(a[min(len(a) - 1, max(0, int((t + pre) * sr / hop)))])   # t in region time
    inside = lambda t: -0.02 <= t <= length + 0.02
    beats = [float(b) - pre for b in bt]
    beat = float(np.median(np.diff(beats))) if len(beats) > 2 else 0.5             # tempo from the real beat spacing
    beats = [b for b in beats if inside(b)]
    while beats and beats[0] - beat > -0.06:                                         # complete the grid to the edges
        beats.insert(0, beats[0] - beat)
    while beats and beats[-1] + beat < length - 0.06:
        beats.append(beats[-1] + beat)
    beats = [round(max(0.0, b), 3) for b in beats if b > -0.06]
    kicks = [round(float(t) - pre, 3) for t in onsets if inside(float(t) - pre) and at(low, float(t) - pre) > 0.45]
    snares = [round(float(t) - pre, 3) for t in onsets if inside(float(t) - pre) and at(high, float(t) - pre) > 0.4 and at(low, float(t) - pre) <= 0.45]
    edges = beats + [length]
    fr = lambda t: max(0, int((t + pre) * sr / hop))
    e = np.array([float(rms[fr(a):max(fr(a) + 1, fr(b))].mean()) for a, b in zip(edges, edges[1:])])
    e = np.convolve(e, np.ones(4) / 4, mode="same") if len(e) >= 4 else e
    e = (e - e.min()) / ((e.max() - e.min()) or 1)
    phase = max(range(4), key=lambda p: sum(at(low, b) for b in beats[p::4])) if len(beats) >= 8 else 0
    downbeats = beats[phase::4]
    level = ["low" if v < 0.33 else "mid" if v < 0.66 else "high" for v in e]
    sections = []
    for i, b in enumerate(beats):
        if sections and sections[-1]["energy"] == level[i]:
            sections[-1]["end"] = edges[i + 1]
        else:
            sections.append({"start": b, "end": edges[i + 1], "energy": level[i], "beats": 0})
        sections[-1]["beats"] += 1
    merged = []
    for s in sections:                                     # absorb runs shorter than a bar, then join equal neighbours
        if merged and (s["beats"] < 4 or merged[-1]["energy"] == s["energy"]):
            merged[-1]["end"], merged[-1]["beats"] = s["end"], merged[-1]["beats"] + s["beats"]
        else:
            merged.append(dict(s))
    for s in merged:
        s.pop("beats")
    snap = lambda t: min(downbeats, key=lambda d: abs(d - t)) if downbeats and min(abs(d - t) for d in downbeats) <= beat * 1.01 else t
    gap = 8 * beat
    drops = [snap(beats[k]) for k in range(4, len(e)) if e[k] - e[k - 4:k].min() > 0.35 and e[k] > 0.6]
    drops = [d for n, d in enumerate(drops) if n == 0 or d - drops[n - 1] > gap]
    breaks = [snap(beats[k]) for k in range(4, len(e)) if e[k - 4:k].max() - e[k] > 0.35 and e[k] < 0.35]
    breaks = [b for n, b in enumerate(breaks) if n == 0 or b - breaks[n - 1] > gap]
    return {"file": os.path.abspath(path), "start": start, "length": round(length, 3), "tempo": round(60 / beat, 2),
            "beat": round(beat, 4), "beats": beats, "downbeats": downbeats, "kicks": kicks, "snares": snares,
            "energy": [round(float(v), 3) for v in e], "sections": merged, "drops": drops, "breaks": breaks}


def energy_at(bm, t):
    k = max([i for i, b in enumerate(bm["beats"]) if b <= t + 0.01] or [0])
    return bm["energy"][min(k, len(bm["energy"]) - 1)] if bm["energy"] else 0.5


def cuts(bm, every="auto", end=None):
    end = min(end or bm["length"], bm["length"])
    beat = bm["beat"] or 0.5
    beats = [b for b in bm["beats"] if b < end - 0.15]
    out, i = [0.0], 0
    while i < len(beats):
        t = beats[i]
        step = int(every) if every != "auto" else (1 if energy_at(bm, t) >= 0.66 else 2 if energy_at(bm, t) >= 0.33 else 4)
        if any(0 < d - t <= 4 * beat + 0.01 for d in bm["drops"]):
            step = 1                                                 # build-up: every beat in the bar before a drop
        if any(-0.01 <= t - b < 4 * beat - 0.01 for b in bm["breaks"]):
            step = 4                                                 # break: hold one shot for a bar
        if t > 0.2:
            out.append(t)
        i += step
    return sorted(set(round(c, 3) for c in out)) + [round(end, 3)]


def _probe(path):
    if path.lower().endswith(IMAGE_EXT):
        from PIL import Image
        w, h = Image.open(path).size
        return {"dur": 1e9, "w": w, "h": h, "fps": None}
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate:format=duration",
                        "-of", "json", path], capture_output=True, text=True)
    j = json.loads(r.stdout or "{}")
    st = (j.get("streams") or [{}])[0]
    n, d = (st.get("r_frame_rate") or "30/1").split("/")
    return {"dur": float(j.get("format", {}).get("duration") or 0), "w": st.get("width", 1920), "h": st.get("height", 1080),
            "fps": float(n) / float(d or 1)}


def _blur_filter():
    import catalog_filmora
    for name in ("Ultra_Blur", "Basic_Blur_196795", "Basic Blur", "Blur"):
        try:
            return catalog_filmora.find(name)["slug"]
        except KeyError:
            pass
    return next((c["slug"] for c in catalog_filmora.load() if "blur" in c["slug"].lower() and not c["is_transition"]), None)


def spec(bm, media, name, style="velocity", size=(1920, 1080), end=None, every="auto", music_gain=-2.0, seed=1,
         fit="auto", fps="auto", words=None, font="Arial", text_size=130):
    from fx_pick import Picker
    rng, pk = random.Random(seed), Picker(seed)
    files = sorted(f for f in (glob.glob(os.path.join(media, "*")) if os.path.isdir(media) else glob.glob(media))
                   if f.lower().endswith(VIDEO_EXT + IMAGE_EXT))
    if not files:
        raise SystemExit(f"no video/image files in {media}")
    info = {f: _probe(f) for f in files}
    files = [f for f in files if info[f]["dur"] > 1.2]
    rng.shuffle(files)
    W, H = size
    if fps == "auto":
        src = next((info[f]["fps"] for f in files if info[f]["fps"]), 30)
        fps = min((24, 25, 30, 50, 60), key=lambda r: abs(r - src))
    first = info[files[0]]
    if fit == "auto":
        fit = "blur" if abs(first["w"] / first["h"] - W / H) > 0.1 else "fit"
    blur = _blur_filter() if fit == "blur" else None
    end = min(end or bm["length"], bm["length"])
    grid, beat = cuts(bm, every, end), bm["beat"] or 0.5
    clips, bg, hold = [], [], 0.3                                    # hold = spare source footage for transitions
    for k, (a, b) in enumerate(zip(grid, grid[1:])):
        f, d = files[k % len(files)], round(b - a, 3)
        m = info[f]
        fill = 100 * max(W / m["w"], H / m["h"]) / min(W / m["w"], H / m["h"])     # % that fills the frame (100 = fit)
        base = fill if fit == "fill" else min(fill, 130) if fit == "blur" else 100
        c = {"type": "image" if f.lower().endswith(IMAGE_EXT) else "video", "path": f.replace("\\", "/"), "start": a, "end": b,
             "track": "main", "z": 0}
        if c["type"] == "video":
            c["src_in"] = round(rng.uniform(hold, max(hold, m["dur"] - d - hold)), 2)
        kick = any(a - 0.03 <= t <= a + 0.06 for t in bm["kicks"])
        sc = lambda v: round(base * v / 100, 2)
        c["scale"] = sc(100)
        c["keyframes"] = {"scale": [[0, sc(118)], [min(d, 0.18), sc(102)], [d, sc(100)]]} if kick else \
            {"scale": [[0, sc(100)], [d, sc(108)]] if k % 2 else [[0, sc(108)], [d, sc(100)]]}
        if k + 1 < len(grid) - 1 and d >= 1.9 * beat and k % 2 == 0:
            c["transition_out"] = {"name": pk.pick(style, use="transition", n=1)[0], "duration": round(min(0.45, beat * 0.6), 3)}
        clips.append(c)
        if blur and base < fill - 1:
            g = {k2: c[k2] for k2 in ("type", "path", "start", "end", "src_in") if k2 in c}
            bg.append(dict(g, track="bg", z=-1, scale=round(fill * 1.08, 1), filters=[blur]))
    fx, busy = [], []
    for dt in (x for x in bm["drops"] if x < end - 0.2):            # black flash into the drop, then two hits
        fx.append({"type": "effect", "name": "4_Flash_Black", "start": round(max(0, dt - 0.12), 3), "end": round(dt + 0.05, 3), "z": 5})
        for n, h in enumerate(pk.pick(style, use="hit", n=2, energy=(3, 5))):
            s0 = dt + 0.06 + n * 2 * beat
            fx.append({"type": "effect", "name": h, "start": round(s0, 3), "end": round(min(end, s0 + 0.4), 3), "z": 5})
        busy.append((dt - 0.2, dt + 3 * beat))
    for sec in (s for s in bm["sections"] if s["energy"] == "high"):  # one bar effect on every other bar in high sections
        for t in [x for x in bm["downbeats"] if sec["start"] <= x < min(sec["end"], end) - 4 * beat][1::2]:
            if not any(a0 <= t <= a1 or a0 <= t + 4 * beat <= a1 for a0, a1 in busy):
                fx.append({"type": "effect", "name": pk.pick(style, use="bar", n=1)[0], "start": t, "end": round(t + 4 * beat, 3), "z": 4})
                busy.append((t, t + 4 * beat))
    for br in (x for x in bm["breaks"] if x < end - 1):             # a look over the held break shot
        fx.append({"type": "effect", "name": pk.pick(style, use="look", n=1)[0], "start": br, "end": round(min(end, br + 4 * beat), 3), "z": 3})
    texts = []
    for n, dt in enumerate(x for x in bm["drops"] if x < end - 0.5):
        if words:
            texts.append({"type": "text", "text": words[n % len(words)], "font": font, "size": text_size, "color": "#FFFFFF",
                          "y": 0.45, "start": round(dt + 0.05, 3), "end": round(min(end, dt + 2 * beat), 3), "in": "punch",
                          "in_duration": 0.18, "out": "fade", "out_duration": 0.15, "z": 10})
    out = {"name": name, "width": W, "height": H, "fps": fps, "clips": bg + clips + fx + texts,
           "beat_map": {"tempo": bm["tempo"], "beat": beat, "drops": bm["drops"], "breaks": bm["breaks"], "fit": fit}}
    music = bm["file"]
    if bm.get("start") or end < bm["length"] - 0.05:                # pre-cut the analysed region so the music starts at 0
        music = os.path.splitext(os.path.abspath(name))[0] + "_music.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(bm.get("start", 0)), "-t", str(round(end, 3)), "-i", bm["file"], music], check=True)
    out["clips"].append({"type": "audio", "path": music.replace("\\", "/"), "start": 0, "gain_db": music_gain, "fade_out": 0.6})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("analyze"); a.add_argument("audio"); a.add_argument("--start", type=float, default=0.0)
    a.add_argument("--duration", type=float); a.add_argument("--out", default="beats.json")
    c = sp.add_parser("cuts"); c.add_argument("beats"); c.add_argument("--every", default="auto"); c.add_argument("--end", type=float)
    s = sp.add_parser("spec"); s.add_argument("beats"); s.add_argument("--media", required=True); s.add_argument("--name", required=True)
    s.add_argument("--style", default="velocity"); s.add_argument("--size", default="1920x1080"); s.add_argument("--end", type=float)
    s.add_argument("--every", default="auto"); s.add_argument("--music-gain", type=float, default=-2.0)
    s.add_argument("--seed", type=int, default=1); s.add_argument("--out")
    s.add_argument("--fit", default="auto", choices=["auto", "fit", "fill", "blur"]); s.add_argument("--fps", default="auto")
    s.add_argument("--words", help="comma-separated words for the drops"); s.add_argument("--font", default="Arial")
    s.add_argument("--text-size", type=float, default=130)
    o = ap.parse_args()
    if o.cmd == "analyze":
        bm = analyze(o.audio, o.start, o.duration)
        json.dump(bm, open(o.out, "w", encoding="utf-8"), indent=1)
        print(f"{o.out}: tempo {bm['tempo']} BPM, beat {bm['beat']} s, {len(bm['beats'])} beats, {len(bm['kicks'])} kicks, "
              f"drops {bm['drops']}, breaks {bm['breaks']}")
        for sec in bm["sections"]:
            print(f"  {sec['start']:7.2f} - {sec['end']:7.2f}  {sec['energy']}")
    elif o.cmd == "cuts":
        g = cuts(json.load(open(o.beats, encoding="utf-8")), o.every, o.end)
        print(json.dumps(g)); print(f"{len(g) - 1} shots")
    else:
        w, h = (int(v) for v in o.size.lower().split("x"))
        sj = spec(json.load(open(o.beats, encoding="utf-8")), o.media, o.name, o.style, (w, h), o.end, o.every, o.music_gain, o.seed,
                  o.fit, o.fps if o.fps == "auto" else int(o.fps), [x.strip() for x in o.words.split(",")] if o.words else None,
                  o.font, o.text_size)
        out = o.out or f"{o.name}.spec.json"
        json.dump(sj, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        n = lambda t: sum(1 for c in sj["clips"] if c["type"] == t)
        print(f"{out}: {sum(1 for c in sj['clips'] if c.get('track') == 'main')} shots (fit={sj['beat_map']['fit']}, fps={sj['fps']}), "
              f"{sum(1 for c in sj['clips'] if c.get('transition_out'))} transitions, {n('effect')} effects, {n('text')} texts")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
