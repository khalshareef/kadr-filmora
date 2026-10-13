"""Subtitles -> Filmora text clips. Reads SRT / VTT, or word-level JSON ([{"word", "start", "end"}, ...] — e.g. from
faster-whisper with word_timestamps), regroups into short caption chunks and adds them to a filmora-core spec.

    python captions.py subs.srt --spec "My Reel.spec.json" [--font "Cairo Bold"] [--size 64] [--y 0.72]
                       [--max-chars 22] [--max-words 4] [--color "#FFFFFF"] [--highlight "#C6FF3D"] [--offset 0] [--z 10]
    python captions.py words.json --spec ... --karaoke      # one clip per chunk + a coloured clip per spoken word
    options: --max-chars 22 --max-words 6 --min-dur 0.6 --in pop|fade|rise|punch --in-duration 0.18 --out fade

Text is copied exactly as written (dialect, spelling, punctuation) — never "corrected".
Without --spec, prints the clip list as JSON.
"""
import argparse, json, re, sys


def _ts(s):
    t = 0.0
    for part in s.strip().replace(",", ".").split(":"):
        t = t * 60 + float(part)
    return t


def read_cues(path):
    """[(start, end, text)] from SRT/VTT, or words grouped later from JSON."""
    raw = open(path, encoding="utf-8-sig").read()
    if path.lower().endswith(".json"):
        return [("w", float(w["start"]), float(w["end"]), w["word"].strip(), bool(w.get("break"))) for w in json.loads(raw)]
    cues = []
    for block in re.split(r"\n\s*\n", raw.replace("\r", "")):
        m = re.search(r"([\d:.,]+)\s*-->\s*([\d:.,]+)[^\n]*\n(.*)", block, re.S)
        if m:
            text = re.sub(r"<[^>]+>", "", m.group(3)).strip()
            if text:
                cues.append(("c", _ts(m.group(1)), _ts(m.group(2)), " ".join(text.split("\n"))))
    return cues


PUNCT = tuple(".,!?;:،؛؟…")


def split_balanced(words, max_chars, max_words):
    """Fewest pieces that respect the limits, with balanced lengths and breaks after punctuation preferred."""
    n = len(words)
    L = lambda i, j: len(" ".join(words[i:j]))
    for k in range(1, n + 1):
        target = L(0, n) / k
        best = {0: (0.0, [])}                                  # dynamic programming over break positions
        for _ in range(k):
            nxt = {}
            for i, (cost, cuts) in best.items():
                for j in range(i + 1, n + 1):
                    if L(i, j) > max_chars and j > i + 1 or j - i > max_words:
                        break
                    c = cost + (L(i, j) - target) ** 2 - (25 if j < n and words[j - 1].endswith(PUNCT) else 0)
                    if j not in nxt or c < nxt[j][0]:
                        nxt[j] = (c, cuts + [j])
            best = nxt
            if n in best:
                cuts = [0] + best[n][1]
                return [" ".join(words[x:y]) for x, y in zip(cuts, cuts[1:])]
    return [" ".join(words)]


def merge_short(chunks, min_dur, max_chars, ends=()):
    """Join pieces shorter than min_dur with a neighbour of the same cue/gap when the result still fits
    (never across a sentence end listed in `ends`)."""
    out = []
    for c in chunks:
        if (out and (c[1] - c[0] < min_dur or out[-1][1] - out[-1][0] < min_dur) and abs(c[0] - out[-1][1]) < 0.05
                and out[-1][1] not in ends and len(out[-1][2]) + 1 + len(c[2]) <= max_chars * 1.35):
            p = out.pop()
            c = (p[0], c[1], p[2] + " " + c[2], (p[3] or []) + (c[3] or []) or None)
        out.append(c)
    return out


def chunk(cues, max_chars=22, max_words=6, min_dur=0.6):
    """Split long cues into short chunks; time is shared by character count (or exact word times from JSON)."""
    out = []
    if cues and cues[0][0] == "w":
        cur = []
        brk = False
        for _, s, e, w, b in cues:                  # "break": true on a word = sentence end (e.g. from whisper segments)
            if cur and (len(" ".join(x[2] for x in cur + [(0, 0, w)])) > max_chars or len(cur) >= max_words
                        or s - cur[-1][1] > 0.6 or cur[-1][2].endswith(PUNCT) or brk):
                out.append((cur[0][0], cur[-1][1], " ".join(x[2] for x in cur), cur))
                cur = []
            cur.append((s, e, w))
            brk = b
        if cur:
            out.append((cur[0][0], cur[-1][1], " ".join(x[2] for x in cur), cur))
        return merge_short(out, min_dur, max_chars, {e for _, _, e, _, b in cues if b})
    for _, s, e, text in cues:
        parts = split_balanced(text.split(), max_chars, max_words)
        total = sum(len(p) for p in parts) or 1
        t = s
        for p in parts:
            d = (e - s) * len(p) / total
            out.append((t, t + d, p, None))
            t += d
    return merge_short(out, min_dur, max_chars)


def clips(chunks, font, size, y, color, z, offset=0.0, highlight=None, karaoke=False, anim=("pop", 0.18, None, None)):
    res = []
    for s, e, text, words in chunks:
        s, e = round(s + offset, 3), round(max(e, s + 0.3) + offset, 3)
        res.append({"type": "text", "text": text, "font": font, "size": size, "color": color, "y": y, "start": s, "end": e,
                    "in": anim[0], "in_duration": anim[1], "z": z})
        if anim[2]:
            res[-1].update(out=anim[2], out_duration=anim[3] or 0.2)
        if karaoke and words and highlight:      # one text can't change colour per word: pop each spoken word above the line
            for ws, we, w in words:
                res.append({"type": "text", "text": w, "font": font, "size": int(size * 1.15), "color": highlight,
                            "y": round(y - 0.06, 3), "start": round(ws + offset, 3), "end": round(max(we, ws + 0.15) + offset, 3),
                            "in": "punch", "in_duration": 0.12, "z": z + 1})
    for a, b in zip(res, res[1:]):               # no overlaps between consecutive captions of the same row
        if a["y"] == b["y"] and a["end"] > b["start"]:
            a["end"] = b["start"]
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("subs"); ap.add_argument("--spec"); ap.add_argument("--font", default="Cairo Bold")
    ap.add_argument("--size", type=float, default=64)
    ap.add_argument("--role", help="caption | label | sub ... : size chosen by the builder for the font (instead of --size)"); ap.add_argument("--y", type=float, default=0.72)
    ap.add_argument("--max-chars", type=int, default=22); ap.add_argument("--max-words", type=int, default=6)
    ap.add_argument("--min-dur", type=float, default=0.6, help="merge pieces shorter than this (s)")
    ap.add_argument("--in", dest="anim_in", default="pop", help="pop | fade | rise | punch | ... ; calm content: fade")
    ap.add_argument("--in-duration", type=float, default=0.18); ap.add_argument("--out", dest="anim_out")
    ap.add_argument("--out-duration", type=float, default=0.2)
    ap.add_argument("--color", default="#FFFFFF"); ap.add_argument("--highlight", default="#C6FF3D")
    ap.add_argument("--offset", type=float, default=0.0); ap.add_argument("--z", type=int, default=10)
    ap.add_argument("--karaoke", action="store_true")
    a = ap.parse_args()
    res = clips(chunk(read_cues(a.subs), a.max_chars, a.max_words, a.min_dur), a.font, a.size, a.y, a.color, a.z, a.offset,
                a.highlight, a.karaoke, (a.anim_in, a.in_duration, a.anim_out, a.out_duration))
    if a.role:                                   # let the builder size it for the chosen font (build_from_spec ROLES)
        for c in res:
            c.pop("size", None)
            c["role"] = a.role if c["text"] and c.get("y") == a.y else "label"
    if not a.spec:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return
    spec = json.load(open(a.spec, encoding="utf-8"))
    old = sum(1 for c in spec["clips"] if c.get("caption"))
    spec["clips"] = [c for c in spec["clips"] if not c.get("caption")] + [dict(c, caption=True) for c in res]
    json.dump(spec, open(a.spec, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{a.spec}: {len(res)} caption clips" + (f" (replaced {old} old ones)" if old else ""))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
