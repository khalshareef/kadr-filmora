"""Catalog the user's sound-effect library and pick soft Foley sounds for visual events.

    python sfx_catalog.py scan "D:/Sound Effects" "D:/Foley"   # (re)build, remembers folders
    python sfx_catalog.py pick tap --n 5            # best soft matches for an event
    python sfx_catalog.py pick whoosh --n 5 --max-dur 1.2
    python sfx_catalog.py pick click --allow-tonal  # allow bell/chime-like sounds (excluded by default)
    python sfx_catalog.py stats

Every file gets: duration, peak time (place the SFX so its peak lands on the visual event), loudness, brightness
(spectral centroid), attack, tonality (bell/chime/ding detector), name/folder tags, and a soft score (0..1: gentle,
warm, short, not tonal). Events: tap, click, pop, paper, cloth, wood, plastic, camera, whoosh, swish, impact, riser,
glitch, type, ui, magic, notification. Default policy (user rule): soft Foley first; no bells, chimes or dings.
Catalog: %LOCALAPPDATA%/kadr/sfx_catalog.json
"""
import argparse, glob, json, os, re, sys

OUT = os.path.join(os.path.expandvars("%LOCALAPPDATA%"), "kadr", "sfx_catalog.json")
EXT = (".wav", ".mp3", ".aif", ".aiff", ".flac", ".ogg")
TAGS = {  # tag: words in file/folder names
    "foley": ["foley"], "plastic": ["plastic"], "wood": ["wood", "wooden", "knock"], "paper": ["paper", "page", "book", "card"],
    "cloth": ["cloth", "fabric", "cotton", "leather", "rustle"], "camera": ["camera", "shutter", "snapshot", "photo"],
    "click": ["click", "clic", "button", "switch", "toggle", "press"], "tap": ["tap", "touch", "tick", "knock", "pluck"],
    "pop": ["pop", "bubble", "blip"], "whoosh": ["whoosh", "woosh", "swoosh", "swish", "swipe", "flyby", "whip"],
    "impact": ["impact", "hit", "punch", "slam", "thud", "braam"], "riser": ["riser", "rise", "build", "uplifter", "sweep"],
    "glitch": ["glitch", "digital", "error", "data", "static"], "type": ["type", "typing", "keyboard", "typewriter"],
    "ui": ["ui", "interface", "menu", "hover", "select", "confirm", "negative", "positive"], "magic": ["magic", "spell", "sparkle", "shimmer"],
    "notification": ["notification", "alert", "message", "notify"], "bell": ["bell", "chime", "ding", "ring", "gong", "glock", "bling"],
    "scifi": ["sci", "scifi", "laser", "robot", "cyber", "mothership", "xenon"], "explosion": ["explosion", "explosive", "blast", "debris"],
    "metal": ["metal", "steel", "chain", "sword", "steampunk"], "loop": ["loop", "loops", "bpm"],
    "weapon": ["pistol", "gun", "laser", "shot", "rifle", "blaster", "sword", "punch", "kick", "fighting", "fight", "body",
               "bodyfall", "bone", "crunch", "gore", "slash", "stab"],
}
EVENT = {  # event -> tags that fit it (first = strongest)
    "tap": ["tap", "wood", "plastic", "foley", "click"], "click": ["click", "camera", "plastic", "ui"], "pop": ["pop", "tap", "plastic", "ui"],
    "paper": ["paper", "cloth", "foley"], "cloth": ["cloth", "foley"], "wood": ["wood", "tap", "foley"], "plastic": ["plastic", "click", "foley"],
    "camera": ["camera", "click"], "whoosh": ["whoosh"], "swish": ["whoosh", "cloth"], "impact": ["impact"], "riser": ["riser"],
    "glitch": ["glitch"], "type": ["type", "click", "tap"], "ui": ["ui", "click"], "magic": ["magic"], "notification": ["notification", "ui"],
}


def _config():
    p = os.path.join(os.path.dirname(OUT), "config.json")
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def analyse(path):
    import numpy as np, librosa
    y, sr = librosa.load(path, sr=22050, mono=True, duration=6.0)
    dur = librosa.get_duration(path=path)
    if len(y) < 256:
        return None
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]
    peak_i = int(np.argmax(rms))
    peak_t = peak_i * 256 / sr
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512)) + 1e-9
    cent = float(np.median(librosa.feature.spectral_centroid(S=S, sr=sr)))
    flat = float(np.median(librosa.feature.spectral_flatness(S=S)))
    # tonality (bells/chimes/dings): energy concentrated in a few narrow partials ABOVE 500 Hz that keep ringing
    f = librosa.fft_frequencies(sr=sr, n_fft=2048)
    band = S[f > 500].mean(axis=1)
    top = np.sort(band)[-6:].sum() / band.sum()
    after = rms[min(len(rms) - 1, peak_i + int(0.4 * sr / 256))] / (rms.max() + 1e-9)
    top = top * min(1.0, 0.4 + 2 * after)                              # short clicks are not bells
    attack = float(peak_t - (np.argmax(rms > 0.1 * rms.max()) * 256 / sr))
    # separate hits (many UI/Foley files are a row of takes): runs above 12 % of max, split by gaps >= 0.12 s
    on = rms > 0.12 * rms.max()
    hits, i, gap = [], 0, int(0.12 * sr / 256)
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and (on[j] or (j + gap < len(on) and on[j:j + gap].any())):
                j += 1
            a, b = i * 256 / sr, j * 256 / sr
            pk = (i + int(np.argmax(rms[i:j]))) * 256 / sr
            hits.append([round(max(0, a - 0.02), 3), round(min(len(y) / sr, b + 0.08), 3), round(pk, 3)])
            i = j
        i += 1
    loud = float(20 * np.log10(rms.max() + 1e-9))
    return {"dur": round(dur, 3), "peak": round(peak_t, 3), "loud_db": round(loud, 1), "bright": round(cent), "flat": round(flat, 4),
            "tonal": round(float(top), 3), "attack": round(attack, 3), "hits": hits[:16], "v": 2}


def tags_for(path, roots=()):
    """Tags from the file name and its own folders — not from library/bundle container names (they mislead)."""
    p = path.replace("\\", "/")
    for r in sorted(roots, key=len, reverse=True):
        if p.lower().startswith(r.lower().rstrip("/") + "/"):
            p = p[len(r.rstrip("/")) + 1:]
            break
    parts = [x for x in p.split("/") if not re.search(r"library|bundle|loops and kits|sound effects", x, re.I)]
    words = re.findall(r"[a-z]+", " ".join(parts).lower())
    hit = lambda k: any(w == k or (len(k) >= 4 and w.startswith(k)) for w in words)     # "clicks" matches "click"
    return sorted({t for t, keys in TAGS.items() if any(hit(k) for k in keys)})


def soft_score(m):
    """0..1: gentle (not too loud/bright), warm, short attack-not-harsh, not tonal."""
    import math
    bright = max(0.0, min(1.0, (m["bright"] - 1500) / 4500))          # 1500 Hz warm .. 6000 Hz harsh
    tonal = max(0.0, min(1.0, (m["tonal"] - 0.06) / 0.14))
    loud = max(0.0, min(1.0, (m["loud_db"] + 12) / 12))                # peaks near 0 dBFS are aggressive
    long_ = max(0.0, min(1.0, (m["dur"] - 1.5) / 4))
    return round(max(0.0, 1 - 0.35 * bright - 0.35 * tonal - 0.15 * loud - 0.15 * long_), 3)


def scan(dirs):
    files = [p for d in dirs for p in glob.glob(os.path.join(d, "**", "*"), recursive=True) if p.lower().endswith(EXT)]
    old = {}
    if os.path.exists(OUT):
        old = {e["path"]: e for e in json.load(open(OUT, encoding="utf-8")).get("files", [])}
    out = []
    for i, p in enumerate(files):
        p = p.replace("\\", "/")
        e = old.get(p)
        if not e or e.get("mtime") != int(os.path.getmtime(p)) or e.get("v") != 2:
            try:
                m = analyse(p)
            except Exception:
                m = None
            if not m:
                continue
            e = dict(path=p, name=os.path.splitext(os.path.basename(p))[0], mtime=int(os.path.getmtime(p)), **m)
        e["tags"] = tags_for(p, dirs)
        e["bell_like"] = "bell" in e["tags"] or e["tonal"] > 0.16
        e["soft"] = soft_score(e)
        out.append(e)
        if i % 250 == 0:
            print(f"  {i}/{len(files)}", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"dirs": dirs, "files": out}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    cfg = _config(); cfg["sfx_dirs"] = dirs
    json.dump(cfg, open(os.path.join(os.path.dirname(OUT), "config.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out


def load():
    return json.load(open(OUT, encoding="utf-8"))["files"]


def pick(event, n=5, allow_tonal=False, max_dur=None, exclude=(), seed=None):
    """Best soft matches for an event: tag match first, then soft score; bells/chimes excluded unless allow_tonal."""
    import random
    want = EVENT.get(event, [event])
    rng = random.Random(seed)
    scored = []
    for e in load():
        if e["path"] in exclude or "loop" in e["tags"] or (not allow_tonal and e["bell_like"]):
            continue
        if not set(want) & {"impact", "glitch", "magic"} and set(e["tags"]) & {"weapon", "explosion", "scifi", "magic"}:
            continue                                   # soft events never get guns, explosions, sci-fi or magic
        if event not in ("camera", "impact") and "metal" in e["tags"]:
            continue                                   # metal (keys, chains) is not soft
        if max_dur and e["dur"] > max_dur:
            continue
        match = sum((len(want) - k) for k, t in enumerate(want) if t in e["tags"])
        if not match:
            continue
        scored.append((match / len(want) + 1.2 * e["soft"] + 0.05 * rng.random(), e))
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:n]]


def place(event, t, gain=-14.0, used=None, allow_tonal=False, max_hit=1.5, tail=0.25):
    """A spec audio clip for a visual event at time t: picks a soft sound (not used yet), takes ONE hit out of the
    file and lines its peak up with t. used: a set shared across the project for variety."""
    used = used if used is not None else set()
    for e in pick(event, 25, allow_tonal):
        hits = [h for h in (e.get("hits") or [[0, e["dur"], e["peak"]]]) if h[1] - h[0] <= max_hit]
        for h in hits:
            key = (e["path"], h[0])
            if key in used:
                continue
            used.add(key)
            src, end, pk = h
            return {"type": "audio", "path": e["path"], "start": round(max(0.0, t - (pk - src)), 3), "src_in": src,
                    "duration": round(min(end - src + tail, 2.5), 3), "gain_db": gain, "sfx_event": event}
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["scan", "pick", "stats"]); ap.add_argument("args", nargs="*")
    ap.add_argument("--n", type=int, default=5); ap.add_argument("--allow-tonal", action="store_true"); ap.add_argument("--max-dur", type=float)
    a = ap.parse_args()
    if a.cmd == "scan":
        dirs = a.args or _config().get("sfx_dirs") or []
        if not dirs:
            raise SystemExit("give the sound-effect folders to scan")
        out = scan([d.replace("\\", "/") for d in dirs])
        print(f"{OUT}: {len(out)} sounds, {sum(e['bell_like'] for e in out)} bell-like (excluded by default)")
    elif a.cmd == "pick":
        for e in pick(a.args[0] if a.args else "tap", a.n, a.allow_tonal, a.max_dur):
            print(f"soft {e['soft']:.2f}  {e['dur']:5.2f}s  peak {e['peak']:.2f}s  {','.join(e['tags']):28} {e['path']}")
    else:
        from collections import Counter
        fs = load()
        print(len(fs), "sounds;", Counter(t for e in fs for t in e["tags"]).most_common(25))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
