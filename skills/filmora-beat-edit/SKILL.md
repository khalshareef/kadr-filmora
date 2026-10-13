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
python beat_map.py spec beats.json --media "D:/clips" --name "My Edit" --style velocity --size 1080x1920        [--words "يلا!,حفلة!" --font "Cairo Black"] [--fit auto|fit|fill|blur] [--fps auto] [--end 30]
python build_from_spec.py "My Edit.spec.json"
```
Analyse the **whole song first** (no --start) to see its map, then analyse the chosen part again with
`--start/--duration` (more accurate tempo for that part; padded 1 s each side so the grid reaches both edges).
`analyze` prints tempo, drops, breaks and energy sections — **read them back to the user in one line** and confirm
the section (most reels: 15–30 s around the hook/drop). `spec` pre-cuts the music to that region, so everything starts at 0.

`spec` gives a solid first draft: shots on the grid (bar before a drop = every beat, bar after a break = one held
shot), punch zoom on kicks, push/pull otherwise, transitions only on cuts of 2+ beats, a black flash into every drop
plus two hits, a bar effect on every other bar of high sections, a look on breaks, `--words` on the drops.
`--fit auto` handles footage of another aspect (blurred copy behind; `fill` = crop to fill, `fit` = bars) and
`--fps auto` matches the footage. Then **improve the spec by hand** (below) — the draft is a starting point.

## What's in beats.json

| key | meaning |
|---|---|
| `tempo`, `beat` | BPM and seconds per beat (`beat` = 60/BPM; a bar = 4 beats) |
| `beats` | every beat time · `downbeats` = bar starts (beat 1) |
| `kicks` | low-band onsets (bass drum) → punch zoom, cut, flash |
| `snares` | high-band onsets (snare/clap/hat) → shake, glitch, text pop |
| `energy` | 0..1 per beat (smoothed over a bar) |
| `sections` | runs of `low` / `mid` / `high` energy with start/end |
| `drops` | energy jumps up (the hit after a build-up) · `breaks` = energy falls (pause, breakdown) |

The detector is good but not perfect: if the user hears a drop somewhere else, trust the user and edit the times.
`python beat_map.py cuts beats.json --every 2 --end 30` prints just the cut grid (auto | 1 | 2 | 4 beats).

## Cutting rules (what the grid does and what to adjust)

- Cut length follows energy: **high = 1 beat, mid = 2 beats, low = 4 beats (1 bar)**; the bar before a drop goes to
  every beat (build-up). For half-time feel use `--every 2` everywhere.
- Very fast shots (< 0.35 s) need very readable footage (close-ups, big motion). Put wide/slow shots on long cuts.
- **The drop** gets the strongest shot of the whole edit, a black flash 0.12 s before it, then a hit effect.
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

Words land on kicks/downbeats: `in: "punch"` (0.15–0.2 s) or `"pop"`, last 1–2 beats, `out: "fade"`. Countdowns on
the 3 beats before the drop. Keep words ≤ 3 per hit on fast songs.

## Effects per section (with filmora-fx-library)

```python
from fx_pick import Picker; pk = Picker(seed=3)
pk.pick("velocity", use="transition", n=8)          # calm/mid sections
pk.pick("glitch-party", use="hit", n=6, energy=(4, 5))  # drop hits
pk.pick("glitch-party", use="bar", n=3)             # one per bar in the high section
pk.pick("cinematic-trailer", use="look", n=1)       # break / outro look
```
One `bar` effect at a time, only in high-energy sections. Hits ≤ 1 per beat. Change looks only at section borders.

## Checklist before building

- Every cut time comes from `beats`/`kicks` (not rounded guesses); clips touch exactly (end of one = start of next).
- Video `src_in` leaves ≥ 0.3 s before and after for transitions; source long enough for the shot.
- Music `gain_db` -2..0 when there's no voice; SFX on hits -10 dB (default) and not on every beat.
- Aspect matches the platform (reels 1080×1920). Total length ends on a bar line.
After building, tell the user the BPM, number of shots, where the drop is, and ask them to watch it in Filmora.
