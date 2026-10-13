---
name: filmora-beat-edit
description: Make music-synced Filmora edits — analyse a song's tempo, beats, kicks, snares, energy sections, drops and breaks, cut footage on the beat grid, punch-zoom on kicks, put flashes/glitches/shakes on hits and drops, and output an editable Filmora project. Use whenever the user wants a beat edit, beat sync, "cut to the music", a montage/AMV/hype video/sports edit/party edit on a song, a velocity edit, or says "قصّ على الإيقاع", "مونتاج على البيت", "بيت سينك", "خلي القص مع الموسيقى", "إيديت على أغنية", "فيلوسيتي". Uses filmora-core to build and filmora-fx-library to choose effects.
---

# Filmora Beat Edit — the music decides where every cut goes

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or two folders above this file). Needs `pip install librosa numpy`.
**Not for religious/Quranic content** (no music there — see filmora-core).

## Fast path (3 commands)

```
python beat_map.py analyze "song.wav" [--start 12.5] [--duration 30] --out beats.json
python beat_map.py spec beats.json --media "D:/clips" --name "My Edit" --style velocity --size 1080x1920 --out "<project folder>/My Edit.spec.json"
       [--words "word1,word2" --font "<chosen font>"] [--word-times 6.5,7.45] [--words-y 0.22] [--drop 7.45]
       [--fit auto|fit|fill|blur] [--fps auto] [--end 30]
python build_from_spec.py "My Edit.spec.json"
```
Analyse the **whole song first** (no --start) to see its map, then analyse the chosen part again with
`--start/--duration` (more accurate tempo for that part; padded 1 s each side so the grid reaches both edges).
`analyze` prints tempo, the **main drop**, all drops with their strength, breaks and energy sections — **read them back
to the user in one line** and confirm the section (most reels: 15–30 s around the hook/drop). `spec` pre-cuts the
music to that region (written next to the spec), so everything starts at 0.

`spec` gives a solid first draft:
- shots on the grid (bar before a drop = every beat, bar after a break = one held shot), push/pull otherwise,
  punch zoom on kicks, transitions only on cuts of 2+ beats and never into a drop;
- **a cut exactly on the main drop**; that shot holds 2 beats and gets the style's drop punch (Velocity:
  `scale [[0,130],[0.12,104],[d,100]]`); black flash into the drop (−0.12 → +0.05 s), a hit **on** the drop
  (shake for Velocity) and one 2 beats later; Velocity/Hype add a speed-lines bar over the drop phrase. Weak
  secondary drops (< 60 % of the main one's strength) only get the cut;
- bar effects on every other bar of high sections; a look on breaks **only if the style has one installed** — no
  "closest other" fallback (fx_pick strict mode), no intro/outro or split-layout effects mid-edit;
- `--words`: hook words with `role: "hit"` (the builder sizes them for the chosen font; `--text-size` only to force a
  number) at **y 0.22** (`--words-y`, hooks live at 0.18–0.28 — above faces in fit/blur layouts): word 1 one beat
  **before** the main drop (anticipation), word 2 **on** it, further words every 2 beats. `--word-times` places them
  at given times instead. The font is always the user's pick from specimens (filmora-text).
`--fit auto` handles footage of another aspect (blurred copy behind; `fill` = crop to fill, `fit` = bars) and
`--fps auto` matches the footage. Then **improve the spec by hand** (below) — the draft is a starting point.

## What's in beats.json

| key | meaning |
|---|---|
| `tempo`, `beat` | BPM and seconds per beat (`beat` = 60/BPM; a bar = 4 beats) |
| `beats` | every beat time · `downbeats` = bar starts (beat 1) |
| `kicks` | low-band onsets (bass drum) → punch zoom, cut, flash |
| `snares` | high-band onsets (snare/clap/hat) → shake, glitch, text pop |
| `energy` | 0..1 per beat (smoothed over a bar) — **normalised to the analysed window** |
| `sections` | runs of `low` / `mid` / `high` energy with start/end — relative to the window, not the song |
| `drops` | energy jumps up (the hit after a build-up), with `drop_strength`; `main_drop` = the strongest |
| `breaks` | energy falls (pause, breakdown) |

Drop times come from the raw loudness + bass jump and are moved to the **downbeat/kick where the music lands** (a 1–2
beat pickup or fill before a downbeat counts as build-up), so a window and the whole song agree. Because energy labels
are per window, an excerpt that starts quiet calls its intro "low" even if it is loud for the song — compare with the
whole-song map. The detector is good but not perfect: if the drop is heard somewhere else, pass `--drop <s>`.
`python beat_map.py cuts beats.json --every 2 --end 30` prints just the cut grid (auto | 1 | 2 | 4 beats).

## Cutting rules (what the grid does and what to adjust)

- Cut length follows energy: **high = 1 beat, mid = 2 beats, low = 4 beats (1 bar)**; the bar before a drop goes to
  every beat (build-up). For half-time feel use `--every 2` everywhere.
- Very fast shots (< 0.35 s) need very readable footage (close-ups, big motion). Put wide/slow shots on long cuts.
- **The drop** gets a cut exactly on it, the strongest shot of the whole edit, a black flash 0.12 s before it, then a
  hit effect on it. Check the draft: the drop must never fall mid-shot.
- **Breaks**: hold one shot (2–4 beats), slow push-in, maybe a colour/film look, text line. Silence is a tool.
- **Last shot** ends on a downbeat with a fade or a hard cut on the last hit; music `fade_out` 0.5–1 s.
- Don't put a transition on every cut: on 1-beat cuts use hard cuts + hit effects; transitions on 2+ beat cuts.
  Transition duration ≈ ½ beat on fast songs (0.2–0.3 s), up to 1 beat on slow ones.

## Movement on the beat (keyframes in the spec)

- **Punch zoom on kick**: `"keyframes": {"scale": [[0, 118], [0.18, 102], [d, 100]]}` on a clip starting at a kick.
- **Beat pulse through a shot**: `"loop": "beat_pulse", "pulse_period": <beat>` (or 2×beat), `"pulse_amount": 0.06`.
- **Shake on snare**: a short clip with `"loop": "shake"`, or an effect layer from `fx_pick.py <style> --use hit` with
  `shake` in its styles, 0.25–0.4 s, starting on the snare time.
- **Stutter** (repeat a moment 2–4×): split one shot into 2–4 clips of ½ beat each with the **same `src_in`**.
- **Freeze + flash**: image of the frame (`ffmpeg -ss T -i clip.mp4 -frames:v 1 freeze.png`) for 1–2 beats,
  white flash (`4_Flash_White1`, 0.15 s) at its start, text on top.
- **Speed feel without speed ramps**: alternate pull-out/push-in keyframes across consecutive shots; real speed ramps
  aren't supported in files yet — tell the user to add Speed Ramping in Filmora on the 1–2 key shots if wanted.

## Text on the beat (with filmora-text)

Words land on kicks/downbeats: `in: "punch"` (0.15–0.2 s) or `"pop"`, last 1–2 beats, `out: "fade"`. Size by
`role` (`hit` for single words) — never a fixed number. Hooks at y 0.18–0.28 on 9:16 (off the faces); one beat of
anticipation before the drop, the key word on it. Countdowns on the 3 beats before the drop. Keep words ≤ 3 per hit.

## Effects per section (with filmora-fx-library)

```python
from fx_pick import Picker; pk = Picker(seed=3)
pk.pick("velocity", use="transition", n=8)          # calm/mid sections
pk.pick("glitch-party", use="hit", n=6, energy=(4, 5))  # drop hits
pk.pick("glitch-party", use="bar", n=3)             # one per bar in the high section
pk.pick("cinematic-trailer", use="look", n=1, strict=True)  # [] when nothing fits: then no look
pk.pick("velocity", use="hit", require=["shake"], strict=True)  # the hit on the drop
```
Use `strict=True` in drafts — a wrong-style effect is worse than none. Mid-edit picks skip intro/outro resources
automatically (`edge=True` to allow them at the very start/end). One `bar` effect at a time, only in high-energy
sections. Hits ≤ 1 per beat. Change looks only at section borders.

## Checklist before building

- Every cut time comes from `beats`/`kicks` (not rounded guesses); clips touch exactly (end of one = start of next).
- Video `src_in` leaves ≥ 0.3 s before and after for transitions; source long enough for the shot.
- A cut sits exactly on the main drop; flash/hit on it; no transition straddles it.
- Music `gain_db` -2..0 when there's no voice; SFX soft (filmora-sfx: −14 dB taps, −13 whooshes, one −10 impact on
  the drop) and not on every beat.
- Aspect matches the platform (reels 1080×1920). Total length ends on a bar line.
After building, run `check_wfp.py`, tell the user the BPM, number of shots, where the drop is, and ask them to watch it
in Filmora.
