"""Beat map for music-synced Filmora edits: analyse a track, derive a cut grid, write a ready filmora-core spec.

    python beat_map.py analyze "song.wav" [--start 0] [--duration 60] [--out beats.json]
    python beat_map.py cuts beats.json [--every auto|1|2|4] [--end 30]
    python beat_map.py spec beats.json --media "D:/clips" --name "My Beat Edit" [--style velocity] [--size 1080x1920]
                       [--fit auto|fit|fill|blur] [--fps auto] [--words "word1,word2"] [--word-times "6.5,7.45"]
                       [--words-y 0.22] [--font "Cairo Black"] [--text-size N] [--drop 7.45]
                       [--end 30] [--every auto] [--music-gain -2] [--seed 1] [--out path.spec.json]

analyze -> tempo, beats (grid completed to the region edges), downbeats (bar starts), kicks (low-band onsets),
           snares (high-band onsets), per-beat energy 0..1 and sections (merged low/mid/high runs) — both NORMALISED TO
           THE ANALYSED WINDOW, so "high" means loud for this excerpt, not for the song. Drops = energy jumps up, timed
           on the raw (unsmoothed) loudness + bass jump and moved to the downbeat/kick where the music lands (a 1-2 beat
           pickup before a downbeat counts as build-up); drop_strength per drop; main_drop = the strongest. Breaks =
           energy falls. The region is analysed with 1 s padding on both sides.
cuts    -> cut times: high energy = every beat, mid = every 2, low = every 4 (auto); the bar before a drop goes to every
           beat; the bar after a break is held as one shot; a cut lands exactly on every drop and the main-drop shot
           holds 2 beats.
spec    -> a filmora-core spec: shots on track "main" cut on the grid, the style's punch on drop shots (velocity
           scale 130 -> 104 in 0.12 s), punch zoom on kicks, push/pull otherwise, transitions (style) only on cuts of 2+
           beats and never into a drop, black flash into each strong drop + a hit ON it (shake for velocity) and one
           2 beats later, bar effects in high sections, a look on breaks only if the style has one installed (none
           otherwise), hook words (role "hit", y 0.22) one beat before the main drop and ON it, the music pre-cut to
           the region. Footage of another aspect is handled by --fit: fit (letterbox), fill (crop to fill), blur
           (blurred copy behind; default when aspects differ).
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
    # Raw (unsmoothed) loudness + bass per beat: the bar smoothing above blurs a jump over ~2 beats, so drop times are
    # taken from this curve, not from the section energy.
    seg = lambda a, b: slice(fr(a), max(fr(a) + 1, fr(b)))
    c_rms = np.array([float(rms[seg(a, b)].mean()) for a, b in zip(edges, edges[1:])])
    c_low = np.array([float(low[seg(a, b)].mean()) for a, b in zip(edges, edges[1:])])
    c = (c_rms / (c_rms.max() or 1) + c_low / (c_low.max() or 1)) / 2
    mean = lambda a, b: float(c[max(0, a):max(max(0, a) + 1, min(len(c), b))].mean())
    rise = lambda j: mean(j, j + 2) - mean(j - 2, j)
    strength = lambda i: round(mean(i, i + 4) - min(mean(i - 6, i - 2), mean(i - 4, i)), 3)
    idx = lambda t: min(range(len(beats)), key=lambda i: abs(beats[i] - t))

    def drop_time(k):
        """Where the music really hits: the beat with the biggest raw jump near k, moved forward to the next downbeat
        when that is ≤ 2 beats later (the beats in between are a pickup/fill), with a kick preferred."""
        j = max(range(max(1, k - 4), min(len(c), k + 3)), key=rise)
        rt = beats[j]
        nxt = [d for d in downbeats if -0.06 <= d - rt <= 2 * beat + 0.06]
        if nxt:
            kicked = [d for d in nxt if any(abs(kk - d) <= 0.08 for kk in kicks)]
            return (kicked or nxt)[0]
        return snap(rt)

    cand = sorted({drop_time(k) for k in range(4, len(e)) if e[k] - e[k - 4:k].min() > 0.35 and e[k] > 0.6})
    drops = []
    for d in cand:                                         # closer than 8 beats: keep the stronger one
        if drops and d - drops[-1] <= gap:
            if strength(idx(d)) > strength(idx(drops[-1])):
                drops[-1] = d
        else:
            drops.append(d)
    strengths = [strength(idx(d)) for d in drops]
    main = drops[strengths.index(max(strengths))] if drops else None
    if main is None and len(c) > 8:                        # no clear drop: the biggest rise on a downbeat, if any
        best = max((idx(d) for d in downbeats if 2 * beat < d < length - 2 * beat), key=lambda i: strength(i), default=None)
        if best is not None and strength(best) > 0.15:
            main = beats[best]
    breaks = [snap(beats[k]) for k in range(4, len(e)) if e[k - 4:k].max() - e[k] > 0.35 and e[k] < 0.35]
    breaks = [b for n, b in enumerate(breaks) if n == 0 or b - breaks[n - 1] > gap]
    return {"file": os.path.abspath(path), "start": start, "length": round(length, 3), "tempo": round(60 / beat, 2),
            "beat": round(beat, 4), "beats": beats, "downbeats": downbeats, "kicks": kicks, "snares": snares,
            "energy": [round(float(v), 3) for v in e], "energy_note": "normalised to this analysed window (0 = its quietest beat)",
            "sections": merged, "drops": drops, "drop_strength": strengths, "main_drop": main, "breaks": breaks}


def main_drop(bm, end=None):
    """The drop the edit is built around: the user-set / analysed main drop; if that lies outside the edit (before
    `end`), the strongest drop inside it; else None."""
    end = bm["length"] if end is None else end
    md = bm.get("main_drop")
    if md is not None and 0.2 < md < end - 0.5:
        return md
    st = bm.get("drop_strength") or [0.0] * len(bm.get("drops", []))
    inside = [(s, d) for d, s in zip(bm.get("drops", []), st) if 0.2 < d < end - 0.5]
    return max(inside)[1] if inside else None


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
        if any(-0.01 <= t - b < 0.5 * beat for b in bm["breaks"]):
            step = 4                                                 # break: hold one shot for a bar
        if t > 0.2:
            out.append(t)
        i += step
    out = [round(c, 3) for c in out]
    md = main_drop(bm, end)
    for d in (x for x in bm["drops"] + ([md] if md is not None else []) if 0.2 < x < end - 0.2):
        hold = 2 * beat - 0.05 if d == md else 0.15                    # main drop shot holds 2 beats so the punch reads
        out = [c for c in out if not (d - 0.15 < c < d + hold)] + [round(d, 3)]   # a cut exactly on every drop
    return sorted(set(out)) + [round(end, 3)]


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


# Per-style drop treatment: punch on the drop shot (start %, settle time s, settle %), the hit ON the drop (tag words it
# must carry), and an optional bar effect over the phrase after the drop. Unknown styles use the default row.
DROP_STYLE = {
    "velocity":     ((130, 0.12, 104), ["shake"], ["speed-lines"]),
    "hype-sport":   ((130, 0.12, 104), ["shake"], ["speed-lines"]),
    "anime":        ((128, 0.12, 104), ["shake"], ["speed-lines"]),
    "glitch-party": ((124, 0.12, 104), ["glitch"], []),
    None:           ((118, 0.18, 102), ["shake"], []),
}


def word_plan(bm, words, end, word_times=None):
    """Times for the hook words: explicit --word-times win; otherwise one word a beat before the main drop
    (anticipation) and the next ON it, any further words every 2 beats after. Returns [(word, start, end)]."""
    beat = bm["beat"] or 0.5
    if not words:
        return []
    if word_times:
        times = list(word_times)[:len(words)]
    else:
        md = main_drop(bm, end)
        if md is None:                                   # no drop found: the second downbeat (or 1 s)
            md = next((d for d in bm["downbeats"] if d >= 4 * beat - 0.05), 1.0)
        near = lambda t: min(bm["beats"], key=lambda b: abs(b - t)) if bm["beats"] else t
        times = [md] if len(words) == 1 else [near(md - beat), md] + [near(md + 2 * beat * i) for i in range(1, len(words) - 1)]
    out = []
    for n, (w, t) in enumerate(zip(words, times)):
        nxt = times[n + 1] if n + 1 < len(times) else None
        e = min(t + 2 * beat, nxt if nxt is not None and nxt > t else t + 2 * beat, end)
        if e - t >= 0.3:
            out.append((w, round(t, 3), round(e, 3)))
    return out


def spec(bm, media, name, style="velocity", size=(1920, 1080), end=None, every="auto", music_gain=-2.0, seed=1,
         fit="auto", fps="auto", words=None, font="Arial", text_size=None, words_y=0.22, word_times=None, drop=None, out_dir=None):
    from fx_pick import Picker
    rng, pk = random.Random(seed), Picker(seed)
    bm = dict(bm)
    if drop is not None:                                 # the drop is heard somewhere else: trust the ear
        bm["main_drop"] = drop
        bm["drops"] = sorted(set([x for x in bm["drops"] if abs(x - drop) > 8 * (bm["beat"] or 0.5)] + [drop]))
        bm.pop("drop_strength", None)
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
    md = main_drop(bm, end)
    (p0, pt, p1), drop_req, drop_bar = DROP_STYLE.get(style, DROP_STYLE[None])
    strong = bm.get("drop_strength") or [1.0] * len(bm["drops"])
    top = max(strong) if strong else 1.0
    big_drops = [d for d, s in zip(bm["drops"], strong) if d == md or s >= 0.6 * top]   # minor drops get the cut only
    if md is not None and md not in big_drops:
        big_drops.append(md)
    pick = lambda use, n=1, **kw: pk.pick(style, use=use, n=n, on="video", strict=True, **kw)
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
        if any(abs(a - x) < 0.01 for x in big_drops):                # the drop shot: the style's punch
            c["keyframes"] = {"scale": [[0, sc(p0)], [min(d, pt), sc(p1)], [d, sc(100)]]}
        elif kick:
            c["keyframes"] = {"scale": [[0, sc(118)], [min(d, 0.18), sc(102)], [d, sc(100)]]}
        else:
            c["keyframes"] = {"scale": [[0, sc(100)], [d, sc(108)]] if k % 2 else [[0, sc(108)], [d, sc(100)]]}
        if k + 1 < len(grid) - 1 and d >= 1.9 * beat and k % 2 == 0 and not any(abs(b - x) < 0.01 for x in big_drops):
            tr = pick("transition")                                  # hard cut INTO a drop, transitions elsewhere
            if tr:
                c["transition_out"] = {"name": tr[0], "duration": round(min(0.45, beat * 0.6), 3)}
        clips.append(c)
        if blur and base < fill - 1:
            g = {k2: c[k2] for k2 in ("type", "path", "start", "end", "src_in") if k2 in c}
            bg.append(dict(g, track="bg", z=-1, scale=round(fill * 1.08, 1), filters=[blur]))
    fx, busy = [], []
    flash = "4_Flash_Black" if "4_Flash_Black" in pk.lib else (pk.pick(["flash", "black"], use="hit", strict=True) or [None])[0]
    pk.used.add(flash)                                               # the flash is not also a "hit" pick
    for dt in sorted(x for x in big_drops if x < end - 0.2):        # flash into the drop, a hit ON it, one 2 beats later
        if flash:
            fx.append({"type": "effect", "name": flash, "start": round(max(0, dt - 0.12), 3), "end": round(dt + 0.05, 3), "z": 6})
        hits = pk.pick(style, use="hit", n=1, on="video", strict=True, energy=(3, 5), require=drop_req) or pick("hit", energy=(3, 5))
        hits += pick("hit", energy=(3, 5))
        for n, h in enumerate(hits[:2]):
            s0 = dt + n * 2 * beat
            if s0 < end - 0.2:
                fx.append({"type": "effect", "name": h, "start": round(s0, 3), "end": round(min(end, s0 + 0.35), 3), "z": 5})
        span = 3 * beat
        if drop_bar and dt == md:                                    # optional bar effect over the drop phrase
            bar = pk.pick(style, use="bar", n=1, on="video", strict=True, require=drop_bar)
            if bar:
                fx.append({"type": "effect", "name": bar[0], "start": round(dt, 3), "end": round(min(end, dt + 4 * beat), 3), "z": 4})
                span = 4 * beat
        busy.append((dt - 0.2, dt + span))
    for sec in (s for s in bm["sections"] if s["energy"] == "high"):  # one bar effect on every other bar in high sections
        for t in [x for x in bm["downbeats"] if sec["start"] <= x < min(sec["end"], end) - 4 * beat][1::2]:
            if not any(a0 <= t <= a1 or a0 <= t + 4 * beat <= a1 or t <= a0 <= t + 4 * beat for a0, a1 in busy):
                bar = pick("bar")
                if bar:
                    fx.append({"type": "effect", "name": bar[0], "start": t, "end": round(t + 4 * beat, 3), "z": 4})
                    busy.append((t, t + 4 * beat))
    for br in (x for x in bm["breaks"] if x < end - 1):             # a look over the held break shot, only if the style has one
        look = pick("look")
        if look:
            fx.append({"type": "effect", "name": look[0], "start": br, "end": round(min(end, br + 4 * beat), 3), "z": 3})
    plan = word_plan(bm, words, end, word_times)
    texts = []
    for w, t0, t1 in plan:
        tx = {"type": "text", "text": w, "font": font, "color": "#FFFFFF", "x": 0.5, "y": words_y, "start": t0, "end": t1,
              "in": "punch", "in_duration": 0.18, "out": "fade", "out_duration": 0.15, "z": 10}
        tx.update({"size": text_size} if text_size else {"role": "hit"})
        texts.append(tx)
    out = {"name": name, "width": W, "height": H, "fps": fps, "clips": bg + clips + fx + texts,
           "beat_map": {"tempo": bm["tempo"], "beat": beat, "main_drop": md, "drops": bm["drops"], "breaks": bm["breaks"],
                        "fit": fit, "words": [list(p) for p in plan]}}
    music = bm["file"]
    if bm.get("start") or end < bm["length"] - 0.05:                # pre-cut the analysed region so the music starts at 0
        music = os.path.join(out_dir or os.getcwd(), os.path.basename(name) + "_music.wav")
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
    s.add_argument("--words", help="comma-separated hook words: one a beat before the main drop, the next on it")
    s.add_argument("--word-times", help="comma-separated start times for the words (overrides the drop placement)")
    s.add_argument("--words-y", type=float, default=0.22, help="vertical centre of the words (hooks: 0.18-0.28)")
    s.add_argument("--font", default="Arial")
    s.add_argument("--text-size", type=float, help="explicit size; default = role 'hit' sized by the builder per font")
    s.add_argument("--drop", type=float, help="main drop time (s, region time) when the ear disagrees with the detector")
    o = ap.parse_args()
    if o.cmd == "analyze":
        bm = analyze(o.audio, o.start, o.duration)
        json.dump(bm, open(o.out, "w", encoding="utf-8"), indent=1)
        print(f"{o.out}: tempo {bm['tempo']} BPM, beat {bm['beat']} s, {len(bm['beats'])} beats, {len(bm['kicks'])} kicks, "
              f"main drop {bm['main_drop']}, drops {bm['drops']} (strength {bm['drop_strength']}), breaks {bm['breaks']}")
        for sec in bm["sections"]:
            print(f"  {sec['start']:7.2f} - {sec['end']:7.2f}  {sec['energy']}")
        print("  (low/mid/high are relative to this analysed window, not to the whole song)")
    elif o.cmd == "cuts":
        g = cuts(json.load(open(o.beats, encoding="utf-8")), o.every, o.end)
        print(json.dumps(g)); print(f"{len(g) - 1} shots")
    else:
        w, h = (int(v) for v in o.size.lower().split("x"))
        out = o.out or f"{o.name}.spec.json"
        sj = spec(json.load(open(o.beats, encoding="utf-8")), o.media, o.name, o.style, (w, h), o.end, o.every, o.music_gain, o.seed,
                  o.fit, o.fps if o.fps == "auto" else int(o.fps), [x.strip() for x in o.words.split(",")] if o.words else None,
                  o.font, o.text_size, o.words_y, [float(x) for x in o.word_times.split(",")] if o.word_times else None, o.drop,
                  os.path.dirname(os.path.abspath(out)))
        json.dump(sj, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        n = lambda t: sum(1 for c in sj["clips"] if c["type"] == t)
        bmj = sj["beat_map"]
        print(f"{out}: {sum(1 for c in sj['clips'] if c.get('track') == 'main')} shots (fit={bmj['fit']}, fps={sj['fps']}), "
              f"{sum(1 for c in sj['clips'] if c.get('transition_out'))} transitions, {n('effect')} effects, {n('text')} texts")
        print(f"  main drop {bmj['main_drop']} (cut on it); words " + ", ".join(f"{w} @ {a}" for w, a, _ in bmj["words"]))
        for c in sj["clips"]:
            if c["type"] == "effect":
                print(f"  fx {c['start']:7.3f}-{c['end']:7.3f}  {c['name']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
