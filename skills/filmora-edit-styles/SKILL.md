---
name: filmora-edit-styles
description: Ready-made editing styles and techniques for generated Filmora projects — Velocity, Glitch Party, Cinematic Trailer, Hype/Sport, Smooth Vlog, Retro VHS, Kinetic Typography, Romantic/Wedding, Memories Slideshow, Calm/Educational talking head — plus moves like punch zoom on the kick, shake on the snare, black flash before the drop, stutter, freeze-frame + flash, light leak on the chorus, split screen and Ken Burns. Use whenever the user names a look or vibe for an edit, asks "make it look like…", wants a trend style, or says "بدي ستايل", "خليه سينمائي", "ستايل تيك توك", "إيديت حماسي", "ستايل قديم/ريترو", "فلوق ناعم", "خليه ترند". Builds on filmora-core, filmora-fx-library, filmora-beat-edit and filmora-text.
---

# Filmora Edit Styles — recipes that turn a spec into a look

A style = **cut rhythm + camera moves + transitions + hits + one look + text treatment + sound**.
Pick one, follow its recipe in [recipes.md](recipes.md), then build with filmora-core.
Effect names always come from `fx_pick.py` (what's installed on *this* PC) — recipe names are examples only.
When nothing installed fits a recipe slot, leave the slot empty (`strict=True`) rather than using an off-style effect.

## Choosing a style

| user says / content | style | energy |
|---|---|---|
| fast, cars, sport, gym, "velocity", "ستايل تيك توك" | **Velocity** or **Hype/Sport** | 4–5 |
| party, gaming, electronic music, "قلتش" | **Glitch Party** | 4–5 |
| trailer, epic, story intro, travel film, "سينمائي" | **Cinematic Trailer** | 2–4 |
| daily vlog, travel diary, lifestyle, "ناعم" | **Smooth Vlog** | 1–3 |
| nostalgia, 90s, family videos, "قديم/ريترو" | **Retro VHS** | 1–3 |
| quotes, lyrics, announcements, "كتابة متحركة" | **Kinetic Typography** | 2–4 |
| wedding, love, birthday, "رومانسي" | **Romantic** | 1–2 |
| photos of a trip/person, "ذكريات" | **Memories Slideshow** | 1–2 |
| talking head, lesson, religious, corporate | **Calm / Educational** | 1 |

If unsure, ask one question: "شو الإحساس اللي بدك ياه: حماسي، سينمائي، ناعم، ولا قديم؟" — and the platform (aspect).

## Universal techniques (spec snippets)

`d` = clip duration, `B` = seconds per beat (from beat_map), `t` = a beat/kick time.

- **Punch zoom on the kick** — clip starting on a kick:
  `"keyframes": {"scale": [[0, 118], [0.18, 102], [d, 100]]}`
- **Push / pull alternation** (speed feel): odd clips `[[0,100],[d,110]]`, even clips `[[0,110],[d,100]]`.
- **Ken Burns** (photos): `"loop": "push", "push_amount": 1.12` plus a small x drift `"keyframes": {"x": [[0,0.48],[d,0.52]]}`.
- **Shake on the snare** — effect layer 0.25–0.4 s at the snare time:
  `pk.pick("shake", use="hit", n=1, energy=(3,5))`; or `"loop": "shake"` on a short clip.
- **Black flash before the drop** — `{"type":"effect","name": <black flash>, "start": drop-0.12, "end": drop+0.05}`
  (`fx_pick.py flash black --use hit`), with a **cut exactly on the drop** and a hit on it. White flash (0.15 s) for
  punchy cuts in the middle of a section.
- **Stutter** — 3 clips of ½ B each with the same `src_in`, then the 4th continues normally; add a hit on the 4th.
- **Freeze + flash** — export the frame: `ffmpeg -ss <src time> -i clip.mp4 -frames:v 1 freeze.png`, place it as an
  image for 1–2 beats with a white flash on its first 0.15 s, scale 100→106, title on top.
- **Light leak on the chorus / section change** — `pk.pick("light-leak", use="transition", n=1)` as `transition_out`,
  or a light-leak overlay effect 0.8–1.5 s centred on the cut.
- **Whip pan between scenes** — fast wipe/whip transitions (`fx_pick.py velocity --use transition`) 0.25–0.35 s.
- **Split screen** — effects tagged `split` (`fx_pick.py split -n 5`: 3D multi-panel, comic panels, TV wall) as an
  effect layer for 1–2 bars over one clip. Real split-screen templates with different clips per panel aren't
  supported yet: alternative = two/three video clips scaled to 50 % / 33 % and positioned (x/y) side by side.
- **Picture-in-picture / small centred picture** — video clip `scale` 55–70, `y` 0.5, with a PNG panel or blurred copy
  of the same clip underneath (blurred background: same clip, same `src_in`, at fill scale × 1.08 with a blur filter at
  lower z — fill scale formula in filmora-core; 16:9 footage in 9:16 ≈ 340).
- **Speed ramp** — not writable yet. Fake it with push-in keyframes + a motion-blur hit at the fast part, and tell the
  user: "select the clip ▸ Speed ▸ Speed Ramping ▸ Montage/Hero" for the 1–2 key shots.
- **Letterbox** — a cinema-bars overlay (`fx_pick.py letterbox --use look`) over the whole video, or for the intro only.
- **Colour look** — one filter (`use: look`, `color` in styles) as an effect layer over a whole section, z just above
  the footage. Footage shot soft/flat on purpose keeps a very light look or none.

## Sound design (with any style)

- **Soft Foley first** (house default): plastic and wooden taps/clicks, camera shutter, paper and fabric, soft
  whooshes — the sound should feel relaxing. **No** bells, chimes, dings or bling UI tones. Search the sound library
  by these words (filmora-sfx) and pick the gentlest takes.
- Whoosh on transitions (−13 dB), soft taps/clicks on text hits (−14 dB), one impact on the drop (−10 dB), riser
  into drops; music at -2..0 dB alone, -6..-8 dB under a voice.
- Not on every cut: SFX on ≈ 1 of 3 transitions + every drop.
- Sound files come from a local sound library (ask where it is if none is catalogued) — never download random audio.
- Religious/Quranic content: no music, no tonal SFX, no jingles (ask before any sound).

## Workflow

1. Confirm style + aspect + length + music section (if any).
2. Music → `beat_map.py analyze` (filmora-beat-edit) · no music → plan by sentences/phrases.
3. Draft: `beat_map.py spec … --style <style>` for music edits, or hand-write the spec for talking heads/slideshows.
4. Apply the recipe (recipes.md): cut rhythm, moves, transitions, hits, look, text, sound.
5. Build (filmora-core), tell the user what to look at, iterate on their feedback.
