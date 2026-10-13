---
name: filmora-sfx
description: Choose and place sound effects for Filmora projects from the user's own SFX library — a catalog that listens to every file (duration, peak time, loudness, brightness, bell/chime detection, separate hits inside multi-take files) and picks soft, relaxing Foley for each visual event (tap, click, pop, paper, cloth, wood, plastic, camera, whoosh, impact, riser, glitch, type, ui), lining the sound's peak up with the frame. Use whenever an edit or motion piece needs SFX, sound design, "أصوات", "مؤثرات صوتية", "ساوند افكت", "فولي", "ووش", or the user points to a sound library. Works with filmora-core specs.
---

# Filmora SFX — soft Foley from the user's own library

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or two folders above this file). Needs librosa + numpy.

## Policy (user rule — keep it)

- **Soft Foley first**: plastic and wooden taps/clicks, paper, cloth, camera shutter/clicks, soft whooshes. The result
  should feel relaxing, ASMR-like.
- **Never** bells, chimes, dings, "bling" UI tones or harsh sounds — unless a sound is genuinely soft (`--allow-tonal`
  only when the user asks).
- No guns, fights, explosions, sci-fi or magic sounds for ordinary events (the picker excludes them unless the event
  is `impact`, `glitch` or `magic`).
- Quiet: −14 dB default for taps/clicks, −12 to −13 for whooshes, −10 for one hero impact. Not on every cut: about one
  sound per visual event that matters.
- Religious/Quranic content: no music, no tonal SFX; ask before adding any sound.

## Catalog

```
python sfx_catalog.py scan "D:/Sound Effects" "D:/Foley"     # first time (remembers the folders); later: python sfx_catalog.py scan
python sfx_catalog.py stats                                   # tags in the library
python sfx_catalog.py pick tap --n 5 [--max-dur 1.5]          # best soft matches for an event
```
Each sound: duration, peak, loudness, brightness, tonality (bell detector), tags from its own file/folder names
(container names like "… Library" or "… Bundle" are ignored), a soft score, and **hits** — single takes found inside
files that contain a row of takes (typical for UI/Foley packs). Catalog file: `%LOCALAPPDATA%/kadr/sfx_catalog.json`.
Scanning ~5,000 files takes ~10 minutes the first time; later scans only analyse new/changed files.

## Placing sounds in a spec (Python)

```python
from sfx_catalog import place
used = set()                                   # one set per project → no sound repeats
clips.append(place("whoosh", 7.86, -13, used))  # camera flight
clips.append(place("tap", 12.5, -14, used))     # bubble pops
clips.append(place("camera", 30.55, -12, used)) # button press
```
`place()` returns an audio clip with `src_in` (the chosen hit inside the file), `duration` (that hit + a short tail)
and `start` shifted so the hit's **peak lands exactly on the event time**. `None` if nothing fits — then skip it.

## Event → sound map (defaults)

| visual event | event word | feel |
|---|---|---|
| element pops in / icon lands | `tap` / `pop` | soft wood or plastic tap |
| button press, toggle, cursor click | `click` / `camera` | plastic click, shutter |
| card/page slides, panel opens | `paper` / `cloth` | paper slide, cotton swish |
| camera flight, scene change | `whoosh` | short soft whoosh (0.3–0.8 s) |
| typing, word chips | `type` / `tap` | tiny clicks, keep very quiet (−18 dB) |
| hero moment / drop | `impact` | one soft low hit, never a blast |

## Checks

- Listen-free sanity: after building, list the chosen files (paths + soft score) for the user in one short block.
- No two identical sounds back-to-back; whooshes not longer than the camera move; nothing louder than the voice.
