---
name: filmora-sfx
description: Choose and place sound effects for Filmora projects from the user's own SFX library — a catalog that listens to every file (duration, peak time, loudness, brightness, bell/chime detection, separate hits inside multi-take files) and picks soft, relaxing Foley for each visual event (tap, click, pop, paper, cloth, wood, plastic, camera, whoosh, impact, riser, glitch, type, ui), lining the sound's peak up with the frame. Use whenever an edit or motion piece needs SFX, sound design, "أصوات", "مؤثرات صوتية", "ساوند افكت", "فولي", "ووش", or the user points to a sound library. Works with filmora-core specs.
---

# Filmora SFX — soft Foley from the user's own library

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or two folders above this file). Needs librosa + numpy.

## Policy (house defaults — keep them)

- **Soft Foley first**: plastic and wooden taps/clicks, paper, cloth, camera shutter/clicks, soft whooshes. The result
  should feel relaxing, ASMR-like.
- **Never** bells, chimes, dings, pings, notification/message tones, jingles, glockenspiel/xylophone/marimba, files
  named "tonal" or with a musical key (`_Am`, `_F#`) — the picker drops them unless `allow_tonal` (only when the user
  asks).
- No guns, fights, war/medieval, vehicles, machines (garage/pneumatic), sci-fi, magic/game-reward or gore sounds for
  ordinary events; ambiences, loops and long field recordings are skipped or pushed down.
- Quiet: −14 dB taps/clicks, −13 whooshes, −18 typing, −10 for one hero impact (these are `place()`'s defaults).
  Not on every cut: about one sound per visual event that matters.
- Religious/Quranic content: no music, no tonal SFX; ask before adding any sound.

## Catalog

```
python sfx_catalog.py scan "D:/Sound Effects" "E:/Foley"     # first time (remembers the folders); later: python sfx_catalog.py scan
python sfx_catalog.py stats                                   # tags in the library
python sfx_catalog.py pick tap --n 6                          # ranked picks + WHY each was chosen
python sfx_catalog.py pick whoosh --n 6 --max-dur 0.8         # no longer than the camera move
python sfx_catalog.py pick click --exclude Arcade --exclude "Digital Click \d+" --seed my-project
```
Each sound: duration, peak, loudness, brightness, tonality (bell detector), a soft score, and **hits** — single takes
found inside files that contain a row of takes (typical for UI/Foley packs). Catalog file:
`%LOCALAPPDATA%/kadr/sfx_catalog.json`. Scanning ~5,000 files takes ~10 minutes the first time; later scans only
analyse new/changed files. Name words, the tonal-name filter and the soft score are recomputed at pick time, so
picker improvements never need a rescan.

**Matching is by the file's own name or its parent folder.** Library/vendor/pack container folders ("… Library",
"… Bundle", "… Collection", "Sound Effects", "SFX", "One Shots", "Loops and Kits", "Vol. 2", "WAV") are ignored;
other pack folder names only add penalties (e.g. a "Fighting" or "Sci-Fi" pack). Extra container names for a
user's library: `"sfx_ignore_folders": ["My Vendor Name"]` in `%LOCALAPPDATA%/kadr/config.json`.

Reading a `pick` line: `2.27  0.15s@0.00  Generic Click Wood Tiny 07  wood@name+1.00 +tiny,wood soft1.00(br-0.04 …)`
= score, length@start of the hit that will be used, name, then why: matched word and where (`name`/`dir`), preferred
words, penalties (`pack:fight`, `amb:rain`, `long9s`, `-digital`), soft score and its parts (`br` brightness, `tn`
tonal, `ld` loudness, `ln` length, `hw` harsh words like metal/axe/glass, `gw` gentle words).

## Placing sounds in a spec (Python)

```python
from sfx_catalog import place
used = set()                                              # one set per project → each FILE used once
clips.append(place("whoosh", 7.86, used=used, max_dur=0.7))  # camera flight of 0.7 s
clips.append(place("tap", 12.5, used=used))                  # icon lands
clips.append(place("camera", 30.55, used=used, exclude=["Wood"]))
```
`place(event, t, gain=None, used=None, allow_tonal=False, max_hit=None, tail=0.25, exclude=(), max_dur=None, seed=None)`
returns an audio clip with `src_in` (the chosen hit inside the file), `duration` (that hit + a short tail, never longer
than `max_dur`) and `start` shifted so the hit's **peak lands exactly on the event time**. `None` if nothing fits —
then skip it.

- **Same ranking as `pick`**, and reproducible: the tie-break is seeded by the event name (pass `seed=` — e.g. the
  project name — for a different but still repeatable order). `place()` takes the best file not in `used`.
- **No repeats per file**: `used` stores file paths. Only when every candidate is used does it reuse a file (a
  different hit of it) and prints a warning — then add a variant event word or relax `exclude`.
- `exclude`: substrings or regexes matched against the path (case-insensitive).
- `max_dur`: longest usable sound; whooshes default to 1.2 s (swish 0.8 s) — pass the camera-move length.
- `gain` None → the event's default (see Policy). Old positional calls `place("tap", 12.5, -14, used)` still work.

## Event → sound map (defaults)

| visual event | event word | feel |
|---|---|---|
| element pops in / icon lands | `tap` / `pop` | soft wood or plastic tap, mouth pop |
| button press, toggle, cursor click | `click` / `ui` / `camera` | plastic/wood click (camera = shutter if the library has one, else a small plastic click) |
| card/page slides, panel opens | `paper` / `cloth` | page turn, book open/close, cotton swish |
| camera flight, scene change | `whoosh` / `swish` | short soft airy whoosh / cloth swish |
| typing, word chips | `type` / `tap` | tiny clicks, very quiet (−18 dB) |
| hero moment / drop | `impact` | one soft low thud/stomp, never metal or a blast |

`riser`, `glitch`, `magic`, `notification` exist but are not house style — only when the user asks
(`notification` needs `allow_tonal`).

## Checks

- Listen-free sanity: after building, list the chosen files (paths + why line) for the user in one short block.
- If `pick` prints a `note:` (no shutter in the library, too few sounds), tell the user what was used instead.
- No two identical sounds back-to-back; whooshes not longer than the camera move; nothing louder than the voice.
