---
name: filmora-fx-library
description: Choose the right Filmora effects, filters, overlays and transitions for a mood or edit style from what is actually installed on the user's PC — every resource is tagged by style, energy (1-5), use (hit, bar, clip, transition, intro, outro, look, util) and target (video, text, face). Use whenever an edit needs effects/transitions/filters/overlays, the user names a vibe ("dynamic", "cinematic", "retro", "glitchy", "soft", "romantic", "horror", "anime", "tech"), asks "what effects do I have", or says "حطلي إفكتات", "ترانزشن حلو", "فلتر سينمائي", "شو في إفكتات عندي", "بدي ستايل قلتش/ريترو/هادئ". Works with filmora-core specs.
---

# Filmora FX Library — pick effects by style, not by guessing names

All effects stay available — nothing is excluded. Tags only tell you **which ones fit** what the user asked for.
Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or two folders above this file).

## Tools

```
python fx_pick.py <style or tag words...> [--use USE] [--on video|text|face] [--kind transition|effect]
                  [-n 5] [--energy 3-5] [--seed N] [--json]
python fx_pick.py --styles            # named styles + every tag word with counts
python fx_pick.py --info "<name>"     # tags of one resource
python catalog_filmora.py search <word>        # raw search by English/Arabic name
python catalog_filmora.py list transition      # list a category: transition | overlay | filter | resFilterNew
```

In Python (keeps a no-repeat history across a whole project — use one Picker per project):
```python
from fx_pick import Picker
pk = Picker(seed=7)
cuts = pk.pick("velocity", use="transition", n=12)     # 12 different transitions (repeats only when the pool runs out)
hits = pk.pick(["glitch", "rgb"], use="hit", n=6, energy=(3, 5))
look = pk.pick("retro-vhs", use="look", n=1)[0]
```
Returned values are **slugs** — put them straight into a spec (`"name"` of an effect clip, `filters`, `transition_out`).

## Tag meanings

- **use** — where it belongs on the timeline:
  - `hit`: one beat / accent, 0.15–0.6 s (shakes, flashes, glitch hits, cracks, bursts)
  - `bar`: one musical phrase, 1–4 s (beat-reactive lights, speed lines, particles)
  - `clip`: lasts the whole clip (3D moves, slow zoom, frames/mockups)
  - `transition`: a real Filmora transition on a cut (`transition_out`)
  - `intro` / `outro`: start / end of a clip or the whole video
  - `look`: whole section or whole video (colour filters, film grain, letterbox, VHS UI, fog, rain)
  - `util`: technical helpers (sharpen, blur fill, LUT loader, text fills) — never picked unless asked
- **energy** — 1 calm … 5 violent. Match the music: chill 1–2, pop 2–4, trap/EDM drop 4–5.
- **on** — `video` (footage), `text` (only makes sense on a title clip → put it in the text's `filters`),
  `face` (needs a person: beauty, skin, clone), `any`.
- **styles** — free words: glitch, rgb, cyber, neon, cinematic, light-leak, flare, smoke, film, retro, vhs, vintage,
  tv, camera-ui, soft, warm, romantic, heart, horror, dark, anime, speed-lines, comic, fire, energy, lightning,
  particles, gold, music (beat-reactive), 3d, zoom, blur, shake, flash, velocity, split, slideshow, frame, mockup,
  social, vlog, tech, hud, weather, rain, snow, water, psychedelic, color … (`--styles` prints them all).

## Named styles

`velocity` · `glitch-party` · `cinematic-trailer` · `hype-sport` · `smooth-vlog` · `retro-vhs` ·
`kinetic-typography` · `romantic` · `horror` · `anime` · `tech` · `slideshow` · `calm`.
Arabic words also work: سريع، قلتش، سينمائي، حماسي، فلوق، هادئ، ديني، ريترو، رومانسي، رعب، انمي، تقني.
Full recipes (which effect goes on which beat) are in the filmora-edit-styles skill.

## How to apply each kind (in a filmora-core spec)

| kind | how |
|---|---|
| transition | `"transition_out": {"name": slug, "duration": 0.3-0.6}` on the outgoing clip (same `track`, touching clips) |
| hit / bar effect or overlay | `{"type": "effect", "name": slug, "start": t, "end": t+len, "z": above footage}` |
| look for a section | effect layer over the whole section, or `"filters": [slug]` on each clip |
| text effect (`on: text`) | `"filters": [slug]` on the text clip |
| face effect | `"filters": [slug]` on the clip with the person |

Durations that read well: flash 0.15–0.3 s, shake/glitch hit 0.25–0.5 s, light leak 0.8–1.5 s, transition 0.3–0.6 s
(0.2–0.3 on fast beats), overlays with built-in animation (smoke wave, film burn): 1–2 s.

## Rules of taste

- One look per section (don't stack two colour filters + film overlay + VHS UI). Max 2 effect layers at once.
- Vary hits: never the same hit effect twice in a row (Picker handles this).
- Energy follows the music: build-up → rising energy; drop → the strongest hits; verse → softer looks.
- Text effects only on texts; face effects only on clips with a person.
- `calm` for religious, educational, emotional or corporate content: no flashes, shakes, glitches or hearts.
  For Quranic content also no music or tonal SFX (ask before any sound).
- Overlays tagged with an aspect in their name (`16-9`, `9-16`, `1-1`) look best in that aspect; others are scaled.

## Unknown or new effects

Effects installed after tagging (or on another PC) get **guessed** tags from their names (`note: "guess"`). To
check one properly, look at its preview: the resource folder (`catalog.json` → slug; folder under
`<Download>/Filmora/<category>/`) has `thumbnail.png` / `previewVideo.mp4` — view the image (or a frame from the
video with ffmpeg) and decide. To add a permanent tag, edit `assets/fx_tags.json` (same fields as existing entries).
If the user wants an effect that isn't installed: tell them its name and ask them to download it inside Filmora
(Effects panel ▸ download), then run `python catalog_filmora.py` again.
