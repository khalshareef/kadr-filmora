"""Pick installed Filmora effects / filters / overlays / transitions that fit a style.

    python fx_pick.py velocity --use transition -n 6       # 6 transitions for a Velocity edit
    python fx_pick.py glitch cyber --use hit -n 4 --on video
    python fx_pick.py "cinematic-trailer" --use look -n 2
    python fx_pick.py --styles                              # named edit styles + every tag word
    python fx_pick.py --info "Glitch Block 2"               # tags of one resource

Tags live in assets/fx_tags.json (hand-tagged from preview frames, keyed by slug):
  styles  free words (glitch, cinematic, retro, soft, velocity, light-leak, ...)
  energy  1 calm .. 5 violent
  use     hit (one beat, 0.2-0.6 s) | bar (a phrase, 1-4 s) | clip (whole clip) | transition | intro | outro | look (whole
          section/video grade or overlay) | util (technical: sharpen, blur fill, LUT, text helpers)
  on      video | text | face | any
  note    what it looks like (also checked: "split screen", "multi-panel", "intro", "outro", "pop out" ...)
Resources installed later (or on another PC) without tags get name-based guesses (marked "guess").
Returned names are slugs, accepted everywhere a spec takes an effect/filter/transition name.

Matching rules (strict enough for automatic drafts):
- A resource matches a style only through a specific tag word; "dynamic"/"energy"/"misc" alone never make a match.
- Intro/outro resources (use or note) are never picked for hit/bar/clip/look/transition unless edge=True (--edge).
- Layout-changing resources (split, slideshow, frame, polaroid, mockup, grid) only when the style/words ask for them
  (short pure hits such as a split flash cut excepted).
- on="video" excludes face-only effects (they need a visible subject); on="face" asks for them.
- strict=True (--strict): when nothing carries the style words, return nothing instead of the closest others
  (a style recipe like "Look: none or a light contrast look" then gets none). require=[tags]: must carry one of them.
"""
import argparse, json, os, random, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catalog_filmora  # noqa: E402

TAGS_FILE = os.path.join(HERE, "..", "assets", "fx_tags.json")

# Named edit styles -> wanted tag words, tag words to avoid, energy range.
STYLES = {
    "velocity":          (["velocity", "zoom", "blur", "flash", "shake", "dynamic", "speed-lines"],
                          ["romantic", "soft", "warm", "film", "fire", "psychedelic", "cartoon", "clone", "crack", "heart"], (3, 5)),
    "glitch-party":      (["glitch", "rgb", "cyber", "flash", "slice", "neon", "music"], ["romantic", "vintage"], (3, 5)),
    "cinematic-trailer": (["cinematic", "light-leak", "smoke", "letterbox", "flash", "dark", "epic", "film"], ["cartoon", "fun", "heart"], (1, 4)),
    "hype-sport":        (["dynamic", "shake", "flash", "energy", "fire", "speed-lines", "sport", "zoom"], ["romantic", "soft"], (3, 5)),
    "smooth-vlog":       (["soft", "vlog", "light-leak", "warm", "camera-ui", "classic", "slide"], ["glitch", "horror"], (1, 3)),
    "retro-vhs":         (["retro", "vhs", "tv", "film", "vintage", "noise", "static", "camera-ui"], ["neon", "cyber"], (1, 4)),
    "kinetic-typography": (["text-fx", "pop", "dynamic", "glitch", "light"], [], (2, 4)),
    "romantic":          (["romantic", "heart", "soft", "light-leak", "petals", "glow", "warm"], ["glitch", "horror", "fire"], (1, 3)),
    "horror":            (["horror", "dark", "smoke", "film", "glitch", "static"], ["heart", "fun", "romantic"], (1, 4)),
    "anime":             (["anime", "speed-lines", "comic", "energy", "lightning", "fire"], ["vintage"], (2, 5)),
    "tech":              (["tech", "cyber", "hud", "data", "glitch", "neon", "scan"], ["vintage", "heart"], (2, 4)),
    "slideshow":         (["slideshow", "frame", "polaroid", "3d", "mockup"], ["glitch"], (1, 3)),
    "calm":              (["soft", "classic", "light", "zoom", "cinematic"],
                          ["glitch", "flash", "shake", "fire", "heart", "romantic", "party", "psychedelic", "horror", "fun", "cartoon"], (1, 2)),
}
GENERIC = {"dynamic", "energy", "misc"}                     # too common to decide a style on their own
LAYOUT = {"split", "slideshow", "frame", "polaroid", "mockup", "grid"}  # change the whole picture layout: only when asked
EDGE_USES = {"intro", "outro"}
EDGE_NOTE = re.compile(r"(intro|outro|opening|ending|opener|closer|exit|pop[ -]?out|split[ -]?screen|multi[ -]?panel)", re.I)
ALIASES = {  # Arabic / loose words -> style or tag
    "سريع": "velocity", "فيلوسيتي": "velocity", "قلتش": "glitch-party", "سينمائي": "cinematic-trailer", "تريلر": "cinematic-trailer",
    "حماسي": "hype-sport", "رياضي": "hype-sport", "فلوق": "smooth-vlog", "هادئ": "calm", "ديني": "calm", "ريترو": "retro-vhs",
    "قديم": "retro-vhs", "رومانسي": "romantic", "رعب": "horror", "انمي": "anime", "تقني": "tech", "سلايدشو": "slideshow",
    "نصوص": "kinetic-typography", "dynamic": "dynamic", "trailer": "cinematic-trailer", "vhs": "retro-vhs", "vlog": "smooth-vlog",
}
GUESS = [  # name regex -> (styles, energy, use)
    (r"glitch|rgb|signal|error|distort", ["glitch", "dynamic"], 4, "hit"), (r"shake|jitter|vibrat", ["shake", "dynamic"], 4, "hit"),
    (r"flash|burst|explo", ["flash", "dynamic"], 4, "hit"), (r"zoom|warp", ["zoom", "dynamic"], 3, "clip"),
    (r"blur", ["blur"], 2, "clip"), (r"leak|flare|light|glow", ["light", "light-leak"], 2, "bar"),
    (r"retro|vhs|vintage|old|film|grain|16mm", ["retro", "film", "vintage"], 1, "look"), (r"smoke|fog", ["smoke", "cinematic"], 1, "look"),
    (r"heart|love|wedding|romant", ["romantic", "heart"], 1, "look"), (r"fire|flame", ["fire", "energy"], 4, "hit"),
    (r"particle|star|spark", ["particles"], 2, "bar"), (r"cinema", ["cinematic"], 1, "look"), (r"text|title|word", ["text-fx"], 2, "util"),
    (r"frame|border|polaroid|photo", ["frame", "slideshow"], 1, "look"), (r"anime|cartoon|comic", ["anime", "comic"], 3, "bar"),
]


def _guess(c):
    name = f'{c["slug"]} {c["title_en"]} {c["name"]}'.lower()
    st, en, use = [], 2, "look"
    for rx, s, e, u in GUESS:
        if re.search(rx, name):
            st, en, use = st + s, max(en, e) if st else e, u if not st else use
    if c["is_transition"]:
        use = "transition"
    elif c["category"] == "resFilterNew":
        st, use = st + ["color"], "look"
    return {"title": c["title_en"] or c["name"], "category": c["category"], "styles": st or ["misc"], "energy": en,
            "use": [use], "on": "text" if "text-fx" in st else "video", "note": "guess", "guess": True}


def library():
    """Every installed resource with tags: {slug: {...tags, is_transition}}."""
    tags = json.load(open(TAGS_FILE, encoding="utf-8")) if os.path.exists(TAGS_FILE) else {}
    lib = {}
    for c in catalog_filmora.load():
        t = dict(tags.get(c["slug"]) or _guess(c))
        t["is_transition"] = c["is_transition"]
        lib[c["slug"]] = t
    return lib


def resolve(words):
    """Style words (English, Arabic or tag words) -> (wanted tags, avoided tags, energy range or None)."""
    want, avoid, energy = [], [], None
    for w in words:
        w = ALIASES.get(w.strip().lower(), w.strip().lower())
        if w in STYLES:
            a, b, e = STYLES[w]
            want, avoid, energy = want + a, avoid + b, e if energy is None else (min(energy[0], e[0]), max(energy[1], e[1]))
        else:
            want.append(w)
    return want, avoid, energy


class Picker:
    """Keeps a history so one project doesn't repeat the same effect until the pool runs out."""

    def __init__(self, seed=None):
        self.used, self.rng, self.lib, self.fallback = set(), random.Random(seed), library(), False

    def pick(self, style=(), use=None, on=None, n=1, energy=None, kind=None, top=12, strict=False, require=None, edge=False):
        """style: list of words. use: hit|bar|clip|transition|intro|outro|look|util. on: video|text|face.
        kind: 'transition' or 'effect' (anything that is not a transition). energy: (lo, hi) overrides the style's range.
        strict: return [] when nothing carries the style words (no 'closest other' fallback).
        require: tag words of which a result must carry at least one. edge: allow intro/outro resources mid-edit."""
        want, avoid, e_style = resolve([style] if isinstance(style, str) else list(style))
        want_set, need = set(want), set(require or [])
        lo, hi = energy or e_style or (1, 5)
        if use == "transition":
            kind = "transition"
        mid = use in ("hit", "bar", "clip", "look", "transition") and not edge
        pool = []
        for slug, t in self.lib.items():
            if kind == "transition" and not t["is_transition"] or kind == "effect" and t["is_transition"]:
                continue
            if use and use not in t["use"] and not (use == "transition" and t["is_transition"]):
                continue
            if not use and "util" in t["use"]:
                continue
            if on == "text" and t["on"] != "text" or on and t["on"] not in (on, "any"):
                continue
            st = set(t["styles"])
            if st & set(avoid):
                continue
            if st & LAYOUT and not st & LAYOUT & (want_set | need) and t["use"] != ["hit"]:
                continue                                       # split/slideshow/frame layouts only when asked for
            if mid and (set(t["use"]) & EDGE_USES or EDGE_NOTE.search(t.get("note") or "")):
                continue                                       # an intro/outro (or split layout) in the middle of an edit
            if need and not st & need:
                continue
            hit_specific = st & want_set - GENERIC
            score = 2 * len(hit_specific) + len(st & want_set & GENERIC) - (0 if lo <= t["energy"] <= hi else 3)                 - (1 if t.get("guess") else 0)
            pool.append((score + self.rng.random(), slug, bool(hit_specific)))
        matched = [x for x in pool if x[2]] if want else pool
        self.fallback = bool(want and not matched)      # nothing carries the style words
        if self.fallback and strict:
            return []
        pool = [x[:2] for x in sorted(matched or pool, reverse=True)]
        fresh = [(sc, s) for sc, s in pool if s not in self.used]
        best = fresh[0][0] if fresh else 0                   # vary within the best-matching tier, widen only if needed
        tier = [s for sc, s in fresh if sc >= best - 2]
        fresh = tier[:max(top, n)] if len(tier) >= n else [s for _, s in fresh][:n]
        if len(fresh) < n:                                   # pool exhausted: allow repeats, least-recent first
            fresh += [s for _, s in pool if s not in fresh][: n - len(fresh)]
        self.rng.shuffle(fresh)
        out = fresh[:n]
        self.used.update(out)
        return out

    def info(self, name):
        c = catalog_filmora.find(name)
        return {"slug": c["slug"], **self.lib[c["slug"]]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("style", nargs="*")
    ap.add_argument("--use"), ap.add_argument("--on"), ap.add_argument("--kind", choices=["transition", "effect"])
    ap.add_argument("-n", type=int, default=5), ap.add_argument("--energy", help="lo-hi, e.g. 3-5")
    ap.add_argument("--seed", type=int), ap.add_argument("--styles", action="store_true"), ap.add_argument("--info")
    ap.add_argument("--json", action="store_true"), ap.add_argument("--require", help="comma-separated tags, one must match")
    ap.add_argument("--strict", action="store_true", help="nothing instead of the closest others when no style match")
    ap.add_argument("--edge", action="store_true", help="allow intro/outro resources for mid-edit uses")
    a = ap.parse_args()
    p = Picker(a.seed)
    if a.styles:
        for k, (w, av, e) in STYLES.items():
            print(f"{k:19} energy {e[0]}-{e[1]}  want: {', '.join(w)}" + (f"  avoid: {', '.join(av)}" if av else ""))
        from collections import Counter
        print("\ntag words:", ", ".join(f"{k}({v})" for k, v in Counter(s for t in p.lib.values() for s in t["styles"]).most_common()))
        return
    if a.info:
        print(json.dumps(p.info(a.info), ensure_ascii=False, indent=1))
        return
    energy = tuple(int(x) for x in a.energy.split("-")) if a.energy else None
    res = p.pick(a.style, use=a.use, on=a.on, n=a.n, energy=energy, kind=a.kind, strict=a.strict,
                 require=a.require.split(",") if a.require else None, edge=a.edge)
    if p.fallback:
        print("(no resource carries those style words for this use - " + ("none picked)" if a.strict else "showing the closest others)"))
    if a.json:
        print(json.dumps([{"slug": s, **p.lib[s]} for s in res], ensure_ascii=False, indent=1))
    else:
        for s in res:
            t = p.lib[s]
            print(f'{s:42} {t["title"]:34} e{t["energy"]} {"/".join(t["use"]):16} {t["note"]}')


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
