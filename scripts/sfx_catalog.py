"""Catalog a sound-effect library and pick soft Foley sounds for visual events.

    python sfx_catalog.py scan "D:/Sound Effects" "E:/Foley"    # (re)build, remembers the folders
    python sfx_catalog.py pick tap --n 6                         # best soft matches + why each one was chosen
    python sfx_catalog.py pick whoosh --n 6 --max-dur 0.8        # a whoosh no longer than the camera move
    python sfx_catalog.py pick click --exclude Arcade --exclude "Digital Click \\d+"
    python sfx_catalog.py pick pop --seed my-project             # another (still reproducible) order of near-ties
    python sfx_catalog.py pick click --allow-tonal               # allow bell/chime-like sounds (excluded by default)
    python sfx_catalog.py stats

Every file gets: duration, peak time (the SFX is placed so its peak lands on the visual event), loudness, brightness
(spectral centroid), tonality (bell/chime detector), single hits inside multi-take files, and a soft score (0..1).
Name words, tonal-name filter and soft score are computed at pick time from the stored analysis, so improving the
word lists never needs a rescan.

Events: tap, click, pop, paper, cloth, wood, plastic, camera, whoosh, swish, impact, type, ui (soft events), and
riser, glitch, magic, notification. A file must match the event by its OWN name or its parent folder (pack/vendor
folder names only add penalties). House policy: soft Foley first; no bells, chimes, dings, pings, notification
tones, jingles, glockenspiel/xylophone/marimba, "tonal" or key-named (_Am, _F#) files unless --allow-tonal; no
weapons, fights, war, vehicles, machines, sci-fi, magic, gore or ambiences for soft events.

Ignored folder names (library/vendor/pack containers that mislead tagging) are the IGNORE_FOLDERS patterns below,
e.g. "... Library", "... Bundle", "... Collection", "Sound Effects", "SFX", "One Shots", "Loops and Kits",
"Vol. 2", "WAV". Add your own regexes in %LOCALAPPDATA%/kadr/config.json as "sfx_ignore_folders": ["My Vendor"].

Python:  from sfx_catalog import pick, place
    used = set()                                     # one per project: each FILE is used once
    place("whoosh", 7.86, used=used, max_dur=0.6)    # gain/max length default per event; reproducible
    place("tap", 12.5, used=used, exclude=["Foley FX"])
Catalog: %LOCALAPPDATA%/kadr/sfx_catalog.json
"""
import argparse, glob, json, os, re, sys, zlib

OUT = os.path.join(os.path.expandvars("%LOCALAPPDATA%"), "kadr", "sfx_catalog.json")
EXT = (".wav", ".mp3", ".aif", ".aiff", ".flac", ".ogg")

# Folder names that are containers (library / vendor / bundle / pack / format names), not descriptions of the sound.
IGNORE_FOLDERS = [
    r"\blibrar(y|ies)\b", r"\bbundles?\b", r"\bcollections?\b", r"\bpacks?\b", r"\bvol(ume)?\b\.?\s*\d*",
    r"\beditions?\b", r"\bsound ?(effects?|fx)\b", r"\bsfx\b", r"\bsamples?\b", r"\bone ?shots?\b",
    r"\bloops? (and|&) kits?\b", r"\bkits?\b", r"^(wav|mp3|aiff?|flac|ogg|audio|files?|assets?)$",
    r"\b\d{2} ?bit\b", r"\b\d{2,3} ?khz\b",
]

TAGS = {  # informational tags (stats / output); exact word or plural/-ing/-ed form
    "foley": ["foley"], "plastic": ["plastic"], "wood": ["wood", "wooden", "knock"], "paper": ["paper", "page", "book", "card"],
    "cloth": ["cloth", "fabric", "cotton", "leather", "rustle"], "camera": ["camera", "shutter", "snapshot", "photo"],
    "click": ["click", "clic", "button", "switch", "toggle", "press"], "tap": ["tap", "touch", "knock"],
    "pop": ["pop", "bubble", "blip"], "whoosh": ["whoosh", "woosh", "swoosh", "swish", "swipe", "flyby", "whip", "whsh"],
    "impact": ["impact", "hit", "punch", "slam", "thud", "braam"], "riser": ["riser", "rise", "build", "uplifter", "sweep"],
    "glitch": ["glitch", "digital", "error", "data", "static"], "type": ["type", "typing", "keyboard", "typewriter"],
    "ui": ["ui", "interface", "menu", "hover", "select", "confirm", "negative", "positive"], "magic": ["magic", "spell", "sparkle", "shimmer"],
    "notification": ["notification", "alert", "message", "notify"], "bell": ["bell", "chime", "ding", "ring", "gong", "glock", "bling"],
    "scifi": ["sci", "scifi", "laser", "robot", "cyber", "mothership", "xenon"], "explosion": ["explosion", "explosive", "blast", "debris"],
    "metal": ["metal", "steel", "chain", "sword", "steampunk"], "loop": ["loop", "bpm"],
    "weapon": ["pistol", "gun", "laser", "rifle", "blaster", "sword", "punch", "kick", "fighting", "fight", "bodyfall", "bone",
               "crunch", "gore", "slash", "stab"],
}

# Tonal by name (bells, chimes, notification tones...) — excluded unless allow_tonal.
TONAL_WORDS = ["ping", "msg", "message", "notification", "notif", "notify", "ding", "bell", "chime", "alert", "beep", "bleep",
               "ring", "jingle", "sparkle", "magic wand", "harp gliss", "harp", "glock", "glockenspiel", "xylo", "xylophone",
               "marimba", "bling", "gong", "tonal", "kalimba", "celesta", "music box", "vibraphone", "tinkle"]
KEY_SUFFIX = re.compile(r"_(?:[A-G](?:#|b)?(?:m|min|maj|minor|major)?)$")      # "Braam Commander_Cm", "Bass Bubble_F#"
# Soft events never take these when they appear in the file name or its parent folder (pack-level: penalty only).
DANGER = ["gun", "pistol", "rifle", "blaster", "laser", "cannon", "artillery", "missile", "grenade", "bomb", "explosion",
          "explosive", "detonation", "blast", "implosion", "sword", "blade", "axe", "arrow", "bow", "crossbow", "catapult",
          "shield", "armor", "armored", "armour", "troops", "war", "battle", "fight", "fighting", "punch", "kick", "slap",
          "stab", "slash", "gore", "blood", "bone", "scream", "creature", "monster", "zombie", "demon", "devil", "ghost",
          "horror", "alien", "dragon", "spaceship", "scifi", "sci fi", "robot", "cyber", "siren", "medieval",
          # magic / game-reward design
          "magic", "spell", "spellbook", "potion", "wizard", "wizardry", "rune", "mystic", "enchanted", "arcane", "poof",
          "quest", "loot", "reward", "mana", "druid", "holy", "divine", "godmode", "legendary", "coin",
          # vehicles / machines
          "car", "train", "tractor", "truck", "engine", "motor", "jet", "plane", "rocket", "helicopter", "carriage",
          "horse", "bicycle", "vehicle", "drill", "saw", "wrench", "impactor", "hydraulic", "compressor", "pressure",
          "pneumatic", "vise", "winch", "jack", "garage", "razor", "mixer", "whisk", "disposal", "generator", "machine"]
AMBIENCE = ["ambience", "ambiance", "ambient", "atmosphere", "atmos", "drone", "pad", "field", "forest", "bird", "insect",
            "cricket", "rain", "weather", "thunder", "storm", "river", "creek", "water", "fire", "fireplace", "crackle",
            "room", "night", "village", "savanna", "tropical", "wetland", "running", "idle", "wind", "loop", "bpm"]
HARSH = ["metal", "steel", "iron", "anvil", "chain", "glass", "axe", "sword", "blade", "shield", "gun", "pistol", "rifle",
         "laser", "explosion", "blast", "crash", "smash", "slam", "scrape", "grind", "saw", "drill", "hammer",
         "sledgehammer", "harsh", "hard", "heavy", "aggressive", "distorted", "screech", "scream", "gore", "bone",
         "crunch", "shatter", "break", "breakdown", "punch", "slap", "kick", "impactor"]
GENTLE = ["soft", "light", "gentle", "subtle", "tiny", "small", "airy", "quiet", "organic", "cotton", "cloth", "paper",
          "wood", "wooden", "felt"]

_TAPPY = ["tiny", "small", "soft", "light", "organic"]
_SYNTH = ["digital", "arcade", "glitch", "negative", "invalid", "deep", "heavy", "glass", "data", "screen", "error"]
_DRUMS = ["snare", "hihat", "hi hat", "shaker", "clap", "tom", "conga", "bongo", "djembe", "cymbal", "perc"]
_WHOOSH_BAD = ["fire", "flame", "burst", "crackle", "ball", "lava", "space", "craft", "roar", "squall", "glitch",
               "electric", "energy", "plasma", "freight", "drive", "muddy", "bubble", "villain", "ice", "phantom", "siren",
               "whale", "voice", "call", "pump", "howling", "spear", "thrust", "take off"]
_WHOOSH_SOFTEN = ["dark", "big", "heavy", "hard", "harsh", "huge", "large", "reverberant", "reverb", "rumble", "howl",
                  "metal", "shiny", "rattle", "deep", "wind tunnel", "storm", "gust"]
# event -> want (strong name words), ok (weaker), prefer (+), penal (-), avoid (excluded), need (name/folder match
# required — always true here), max_hit (longest single hit), max_dur (default max length), gain, soft (house rules)
EVENT = {
    "tap": dict(want=["tap", "knock", "wood", "wooden", "plastic", "finger"], ok=["click", "button", "organic", "foley", "bit"],
                prefer=_TAPPY + ["wood", "plastic"], penal=_SYNTH + _DRUMS,
                avoid=["clock", "tick", "door", "knocker", "chop", "creak", "crackle", "hammer", "splitting", "kick", "bass"],
                max_hit=0.8),
    "click": dict(want=["click", "button", "switch", "toggle", "press", "mouse"], ok=["tap", "plastic", "finger"],
                  prefer=_TAPPY + ["plastic", "wood", "finger"], penal=_SYNTH + ["metal"], avoid=["clock", "tick", "door"],
                  max_hit=0.8),
    "pop": dict(want=["pop", "bubble", "blop", "plop", "cork"], ok=["mouth", "tap", "finger"],
                prefer=_TAPPY + ["mouth"], penal=_SYNTH + ["up"], avoid=["underwater", "bass", "drone", "car", "straw"],
                max_hit=0.8),
    "paper": dict(want=["paper", "page", "book", "card", "envelope", "letter", "notebook", "crumple", "crumble", "cardboard",
                        "newspaper", "magazine", "origami"], ok=[],
                  prefer=["turn", "flip", "slide", "soft", "light", "small", "open", "close"],
                  penal=["whoosh", "whsh", "digital", "ui", "brush"], avoid=["pager"], max_hit=1.5),
    "cloth": dict(want=["cloth", "cotton", "fabric", "linen", "polyester", "denim", "wool", "sweater", "jacket", "shirt",
                        "towel", "blanket", "curtain"], ok=["leather", "rustle", "movement", "grab"],
                  prefer=["soft", "light", "short", "small", "cotton"],
                  avoid=["leaf", "leave", "leaves", "wind", "rain", "forest", "troops", "armored", "march", "punch",
                         "sweetener"], max_hit=1.5),
    "wood": dict(want=["wood", "wooden", "knock", "bamboo", "plank", "timber"], ok=["tap"],
                 prefer=_TAPPY + ["tap", "button", "click"], penal=_SYNTH,
                 avoid=["fire", "fireplace", "crackle", "creak", "chop", "saw", "splitting", "hammer", "breakdown", "fall",
                        "crunch", "forest", "field", "door", "knocker", "ghost", "whirlpool", "stick", "slide"], max_hit=0.8),
    "plastic": dict(want=["plastic"], ok=[], prefer=_TAPPY + ["button", "click"], penal=_SYNTH,
                    avoid=["bowl", "bucket", "marble", "spin", "ice", "water", "rattle"], max_hit=0.8),
    "camera": dict(want=["camera", "shutter", "snapshot", "photo", "polaroid", "lens"], ok=["click", "button"],
                   prefer=["plastic", "tiny", "small", "mechanical", "shutter"], penal=_SYNTH + ["wood"],
                   avoid=["clock", "tick", "door"], max_hit=0.8,
                   note="no camera/shutter file matched by name; these are small plastic clicks instead"),
    "whoosh": dict(want=["whoosh", "woosh", "swoosh", "whsh", "swish", "swipe", "flyby", "passby", "whip"],
                   ok=["air", "airy", "breeze", "swing", "transition", "flutter", "pass"],
                   prefer=["soft", "light", "airy", "subtle", "short", "small", "cloth", "cotton", "breath", "gentle",
                           "quick", "fast", "neutral", "air"],
                   penal=_WHOOSH_SOFTEN + ["tonal"], avoid=_WHOOSH_BAD, max_hit=1.2, max_dur=1.2, gain=-13.0),
    "swish": dict(want=["swish", "swipe", "whip", "swoosh", "cloth", "cotton", "whoosh", "whsh"], ok=["swing", "air"],
                  prefer=["cloth", "cotton", "polyester", "short", "small", "light", "soft", "high", "quick", "fast"],
                  penal=_WHOOSH_SOFTEN, avoid=_WHOOSH_BAD, max_hit=0.8, max_dur=0.8, gain=-13.0),
    "impact": dict(want=["thud", "thump", "stomp", "boom", "impact", "hit", "drop", "bump", "fall", "landing"],
                   ok=["low", "deep", "sub", "sweetener"],
                   prefer=["soft", "low", "deep", "dull", "sub", "stomp", "sweetener", "short", "snow", "sand", "grass",
                           "thud", "thump", "wood"],
                   penal=["big", "huge", "epic", "hard", "heavy", "harsh", "reverberant", "crash", "dark", "tonal",
                          "strike", "smash", "slam", "concrete", "gravel", "rattling", "lingering"],
                   avoid=["metal", "steel", "iron", "anvil", "glass", "smash", "braam", "thunder", "implosion", "crunch",
                          "detonation", "scifi", "shot", "taiko", "timpani", "earthquake", "hell", "showdown"],
                   max_hit=1.5, gain=-10.0),
    "type": dict(want=["type", "typing", "typewriter", "keyboard", "keystroke"], ok=["click", "tap", "button"],
                 prefer=_TAPPY + ["plastic", "finger"], penal=_SYNTH + ["metal", "medium"], avoid=["clock", "tick"],
                 max_hit=0.5, gain=-18.0),
    "ui": dict(want=["ui", "click", "button", "select", "hover", "focus", "menu", "confirm", "toggle", "switch", "tab"],
               ok=["tap", "plastic", "slide"], prefer=_TAPPY + ["plastic", "wood", "neutral"],
               penal=_SYNTH + ["fail", "tonal", "large", "metal"], avoid=["clock", "tick"], max_hit=0.8),
    # not soft by nature — only when asked
    "riser": dict(want=["riser", "rise", "rising", "build", "buildup", "uplifter", "sweep", "swell"], ok=[], soft=False,
                  max_hit=8.0, gain=-13.0),
    "glitch": dict(want=["glitch", "digital", "error", "data", "static", "stutter"], ok=[], soft=False, max_hit=1.5),
    "magic": dict(want=["magic", "spell", "sparkle", "shimmer", "poof", "potion"], ok=[], soft=False, max_hit=2.0),
    "notification": dict(want=["notification", "notif", "notify", "alert", "message", "msg", "ping"], ok=[], soft=False,
                         max_hit=1.5, note="notification sounds are tonal: only with allow_tonal, when the user asks"),
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


# ---------------------------------------------------------------- words
def _tokens(s):
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)                    # UIClick -> UI Click, DSGNWhsh -> DSGN Whsh
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)                          # camelCase
    return re.findall(r"[a-z]+", s.lower())


class _W:
    """Tokens of one text with forgiving word tests: exact, plural, -ing/-ed (incl. doubled consonant); phrases."""
    __slots__ = ("set", "joined")

    def __init__(self, tokens):
        self.set, self.joined = set(tokens), " " + " ".join(tokens) + " "

    def has(self, k):
        if " " in k:
            return f" {k} " in self.joined or f" {k}s " in self.joined
        s = self.set
        return (k in s or k + "s" in s or k + "es" in s or k + "ing" in s or k + "ed" in s or k + "er" in s
                or k + k[-1] + "ing" in s or k + k[-1] + "ed" in s or (k.endswith("e") and k[:-1] + "ing" in s))

    def hits(self, words):
        return [k for k in words if self.has(k)]


def _ignore_patterns():
    return [re.compile(p, re.I) for p in IGNORE_FOLDERS + list(_config().get("sfx_ignore_folders", []))]


def _split(path, roots=(), ign=None):
    """(name, parent folder, other folders) of a file, relative to its library root, container folders removed."""
    ign = ign if ign is not None else _ignore_patterns()
    p = path.replace("\\", "/")
    for r in sorted(roots, key=len, reverse=True):
        if p.lower().startswith(r.lower().rstrip("/") + "/"):
            p = p[len(r.rstrip("/")) + 1:]
            break
    parts = p.split("/")
    name = os.path.splitext(parts[-1])[0]
    folders = [x for x in parts[:-1] if x and ":" not in x and not any(rx.search(x) for rx in ign)]
    parent = folders[-1] if folders and parts[:-1] and folders[-1] == parts[-2] else ""
    return name, parent, [x for x in folders if x != parent]


def tags_for(path, roots=(), ign=None):
    """Tags from the file name and its own folders — not from library/bundle container names (they mislead)."""
    name, parent, packs = _split(path, roots, ign)
    w = _W(_tokens(" ".join([name, parent] + packs)))
    return sorted({t for t, keys in TAGS.items() if any(w.has(k) for k in keys)})


def soft_parts(m, words=None):
    """Soft score 0..1 and its parts: gentle (not bright/loud), not tonal, short, no harsh-material words."""
    c = lambda v: max(0.0, min(1.0, v))
    parts = {"br": 0.30 * c((m["bright"] - 1500) / 4000),             # 1500 Hz warm .. 5500 Hz harsh
             "tn": 0.30 * c((m["tonal"] - 0.06) / 0.14),
             "ld": 0.10 * c((m["loud_db"] + 12) / 12),                # peaks near 0 dBFS are aggressive
             "ln": 0.10 * c((m["dur"] - 1.5) / 6)}
    if words is not None:
        parts["hw"] = min(0.5, 0.25 * len(words.hits(HARSH)))
        parts["gw"] = -min(0.1, 0.05 * len(words.hits(GENTLE)))
    return round(c(1 - sum(parts.values())), 3), parts


def soft_score(m, words=None):
    return soft_parts(m, words)[0]


# ---------------------------------------------------------------- catalog
def scan(dirs):
    files = [p for d in dirs for p in glob.glob(os.path.join(d, "**", "*"), recursive=True) if p.lower().endswith(EXT)]
    old = {}
    if os.path.exists(OUT):
        old = {e["path"]: e for e in json.load(open(OUT, encoding="utf-8")).get("files", [])}
    out, ign = [], _ignore_patterns()
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
        info = _info(e, dirs, ign)
        e["tags"], e["bell_like"], e["soft"] = info["tags"], info["bell_like"], info["soft"]
        out.append(e)
        if i % 250 == 0:
            print(f"  {i}/{len(files)}", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"dirs": dirs, "files": out}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    cfg = _config(); cfg["sfx_dirs"] = dirs
    json.dump(cfg, open(os.path.join(os.path.dirname(OUT), "config.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    _CACHE.clear()
    return out


def _info(e, roots, ign):
    """Derived, recomputed at load time (no rescan needed): words per level, tags, tonal-by-name, soft score."""
    name, parent, packs = _split(e["path"], roots, ign)
    wn, wp, wk = _W(_tokens(name)), _W(_tokens(parent)), _W(_tokens(" ".join(packs)))
    wall = _W(_tokens(" ".join([name, parent] + packs)))
    tonal_words = wall.hits(TONAL_WORDS) + (["key-suffix"] if KEY_SUFFIX.search(name) else [])
    soft, parts = soft_parts(e, _W(_tokens(name + " " + parent)))
    return {"wn": wn, "wp": wp, "wk": wk, "tags": sorted({t for t, ks in TAGS.items() if any(wall.has(k) for k in ks)}),
            "tonal_words": tonal_words, "bell_like": bool(tonal_words) or e["tonal"] > 0.16, "soft": soft, "sp": parts}


_CACHE = {}


def load():
    """Catalog entries (raw)."""
    return _catalog()[0]


def _catalog():
    st = os.stat(OUT)
    key = (st.st_mtime, st.st_size, json.dumps(_config().get("sfx_ignore_folders", [])))
    if _CACHE.get("key") != key:
        d = json.load(open(OUT, encoding="utf-8"))
        ign = _ignore_patterns()
        files = d["files"]
        _CACHE.update(key=key, files=files, info=[_info(e, d.get("dirs", []), ign) for e in files])
        _RANKED.clear()
    return _CACHE["files"], _CACHE["info"]


# ---------------------------------------------------------------- picking
def _excluded(path, exclude):
    for x in exclude or ():
        if isinstance(x, re.Pattern):
            if x.search(path):
                return True
        elif isinstance(x, str):
            if x.lower() in path.lower():
                return True
            try:
                if re.search(x, path, re.I):
                    return True
            except re.error:
                pass
    return False


def _segments(e, max_seg, whole_first=False):
    """Usable (src, end, peak) pieces of a file no longer than max_seg: single hits of multi-take files, or the
    whole file for short single sounds (whooshes prefer the whole file so their fade-in is kept)."""
    whole = [0.0, e["dur"], e["peak"]]
    if whole_first and e["dur"] <= max_seg:
        return [whole]
    segs = [h for h in (e.get("hits") or [whole]) if h[1] - h[0] <= max_seg]
    if not segs and e["dur"] <= max_seg:
        segs = [whole]
    return segs


def _jitter(seed, path):
    return zlib.crc32(f"{seed}|{path}".encode("utf-8")) / 2 ** 32


def pick(event, n=5, allow_tonal=False, max_dur=None, exclude=(), seed=None, max_hit=None):
    """Ranked soft matches for an event (list of catalog entries + "score", "why", "seg", "segs").

    Ranking = name match (file name > parent folder; pack folders never count) + event prefer/penalty words +
    soft score + a tiny seeded tie-break. Deterministic: seed None -> the event name, so the CLI `pick`
    and place() rank identically. exclude: substrings or regexes matched against the path (case-insensitive).
    max_dur: longest usable sound in seconds (a single hit inside a multi-take file counts); default per event
    (whoosh 1.2 s, swish 0.8 s). n None -> all candidates."""
    files, infos = _catalog()
    key = (_CACHE["key"], event, bool(allow_tonal), max_dur, tuple(exclude or ()), seed, max_hit)
    ranked = _RANKED.get(key)
    if ranked is None:
        ranked = _RANKED.setdefault(key, _rank(event, files, infos, allow_tonal, max_dur, exclude, seed, max_hit))
    return list(ranked) if n is None else ranked[:n]


_RANKED = {}


def _rank(event, files, infos, allow_tonal, max_dur, exclude, seed, max_hit):
    spec = EVENT.get(event) or dict(want=[event], ok=[], soft=True, max_hit=1.5)
    soft_event = spec.get("soft", True)
    seed = event if seed is None else seed
    max_dur = spec.get("max_dur") if max_dur is None else max_dur
    max_seg = min(x for x in (max_hit or spec.get("max_hit", 1.5), max_dur or 99) if x)
    want, ok = spec["want"], spec.get("ok", [])
    out = []
    for e, i in zip(files, infos):
        if _excluded(e["path"], exclude) or "loop" in i["tags"]:
            continue
        if not allow_tonal and i["bell_like"]:
            continue
        wn, wp, wk = i["wn"], i["wp"], i["wk"]
        local = lambda ws: wn.hits(ws) + [k for k in wp.hits(ws) if k not in wn.hits(ws)]
        # name/parent-folder match is required
        m = [(1.0, k, "name") for k in wn.hits(want)] + [(0.75, k, "dir") for k in wp.hits(want)] + \
            [(0.5, k, "name") for k in wn.hits(ok)] + [(0.35, k, "dir") for k in wp.hits(ok)]
        if not m:
            continue
        if local(spec.get("avoid", [])):
            continue
        pen, why_pen = 0.0, []
        if soft_event:
            if local(DANGER):
                continue
            if e["dur"] > 30:
                continue                                                # field recordings / ambience beds
            amb = [k for k in local(AMBIENCE) if not (event in ("whoosh", "swish") and k == "wind")]
            if amb:
                pen += 0.6; why_pen.append(f"amb:{amb[0]}")
            pk = wk.hits(DANGER)
            if pk:
                pen += 0.3; why_pen.append(f"pack:{pk[0]}")
            if e["dur"] > 6:
                p = 0.4 * min(1.0, (e["dur"] - 6) / 24); pen += p; why_pen.append(f"long{e['dur']:.0f}s")
            if "metal" in i["tags"] and event not in ("impact",):
                pen += 0.3; why_pen.append("metal")
        pn = local(spec.get("penal", []))
        if pn:
            pen += min(0.5, 0.25 * len(pn)); why_pen.append("-" + ",".join(pn[:3]))
        segs = _segments(e, max_seg, whole_first=event in ("whoosh", "swish", "riser"))
        if not segs:
            continue
        m.sort(key=lambda x: -x[0])
        match = m[0][0] + (0.1 if len({k for w_, k, _ in m if w_ >= 0.75}) > 1 else 0.0)
        pr = local(spec.get("prefer", []))
        bonus = min(0.3, 0.12 * len(pr))
        jit = 0.04 * _jitter(seed, e["path"])
        score = match + bonus - pen + i["soft"] + jit
        sp = " ".join(f"{k}{-v:+.2f}" for k, v in i["sp"].items() if abs(v) >= 0.01)
        why = (f"{m[0][1]}@{m[0][2]}+{match:.2f}" + (f" +{','.join(pr[:3])}" if pr else "") +
               (f" {' '.join(why_pen)}" if why_pen else "") + f" soft{i['soft']:.2f}" + (f"({sp})" if sp else ""))
        out.append(dict(e, score=round(score, 3), why=why, seg=segs[0], segs=segs, tags=i["tags"], soft=i["soft"],
                        _strong=m[0][1] in want))
    out.sort(key=lambda x: (-x["score"], x["path"]))
    return out


def place(event, t, gain=None, used=None, allow_tonal=False, max_hit=None, tail=0.25, exclude=(), max_dur=None,
          seed=None):
    """A spec audio clip for a visual event at time t: the best-ranked soft sound whose FILE is not used yet (same
    ranking as `pick`), ONE hit of it, its peak lined up with t. used: one set per project (file paths). A file is
    reused only when every candidate is used — then a different hit of it, with a warning. gain None -> event default
    (-14 taps/clicks, -13 whoosh/swish, -10 one hero impact, -18 typing). max_dur: e.g. the camera-move length for whooshes."""
    used = used if used is not None else set()
    ranked = pick(event, None, allow_tonal, max_dur, exclude, seed, max_hit)
    gain = EVENT.get(event, {}).get("gain", -14.0) if gain is None else gain
    if not ranked:
        print(f"sfx: nothing fits '{event}' (max_dur={max_dur}, exclude={list(exclude)})", file=sys.stderr)
        return None
    choice = next(((e, e["seg"]) for e in ranked if e["path"] not in used), None)
    if choice is None:                                               # catalog ran out: reuse, but a different hit
        choice = next(((e, h) for e in ranked for h in e["segs"] if (e["path"], h[0]) not in used), (ranked[0], ranked[0]["seg"]))
        print(f"sfx: all {len(ranked)} '{event}' sounds already used — reusing {choice[0]['name']}", file=sys.stderr)
    e, (src, end, pk) = choice
    used.add(e["path"]); used.add((e["path"], src))
    dur = min(end - src + tail, e["dur"] - src, 2.5)
    lim = max_dur if max_dur else EVENT.get(event, {}).get("max_dur")
    if lim:                                                          # tail included: never longer than the move
        dur = min(dur, max(lim, end - src))
    return {"type": "audio", "path": e["path"], "start": round(max(0.0, t - (pk - src)), 3), "src_in": src,
            "duration": round(dur, 3), "gain_db": gain, "sfx_event": event}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["scan", "pick", "stats"]); ap.add_argument("args", nargs="*")
    ap.add_argument("--n", type=int, default=5); ap.add_argument("--allow-tonal", action="store_true")
    ap.add_argument("--max-dur", type=float, help="longest usable sound in s (default per event: whoosh 1.2, swish 0.8)")
    ap.add_argument("--exclude", action="append", default=[], help="substring or regex on the path (repeatable)")
    ap.add_argument("--seed", help="tie-break seed (default: the event name — same order as place())")
    a = ap.parse_args()
    if a.cmd == "scan":
        dirs = a.args or _config().get("sfx_dirs") or []
        if not dirs:
            raise SystemExit("give the sound-effect folders to scan")
        out = scan([d.replace("\\", "/") for d in dirs])
        print(f"{OUT}: {len(out)} sounds, {sum(e['bell_like'] for e in out)} bell-like (excluded by default)")
    elif a.cmd == "pick":
        ev = a.args[0] if a.args else "tap"
        if ev not in EVENT:
            print(f"(unknown event '{ev}': matching the word itself; events: {', '.join(EVENT)})")
        res = pick(ev, a.n, a.allow_tonal, a.max_dur, a.exclude, a.seed)
        for e in res:
            s, en, _ = e["seg"]
            print(f"{e['score']:.2f}  {en - s:4.2f}s@{s:<5.2f} {e['name'][:58]:58}  {e['why']}")
            print(f"      {e['path']}")
        note = EVENT.get(ev, {}).get("note")
        if note and (not res or not any(e["_strong"] for e in res)):
            print("note:", note)
        if not res:
            print(f"note: nothing fits '{ev}' with these settings")
        elif len(res) < a.n:
            print(f"note: only {len(res)} '{ev}' sounds fit — place() will reuse files (other hits) after that")
    else:
        from collections import Counter
        files, infos = _catalog()
        print(len(files), "sounds;", sum(i["bell_like"] for i in infos), "tonal/bell-like;",
              Counter(t for i in infos for t in i["tags"]).most_common(25))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
