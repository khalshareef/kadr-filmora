# Motion doctrine, Arabic rules and Chromium traps

Our own summary of what we learned from ~380 public motion briefs (prompt-motion.com and an Arabic curation of Opus
motion prompts) and the strongest open-source motion skills on GitHub (HyperFrames — Apache-2.0, cinetic — MIT,
product-film-skill — MIT, brag — MIT). Use with premium-playbook.md and styles.md.

## Why some briefs work and others don't

The same one-line "make a showreel, go all out" brief was run dozens of times with wildly different results. What made
results consistent was always the same five things: **one concept**, **a banned list (with a replacement for each
ban)**, **a beat or phrase grid**, **a fixed build method**, **a review step before the full render**. Our skills
always supply all five.

## Seams (scene → scene)

- **Vector law**: how scene A leaves decides how scene B enters — same axis, same direction, matched speed; cut while
  both sides are still moving. Never cut on a still frame.
- One dominant **current direction** for the whole film; other directions carry meaning (up = conclusion,
  push forward = going deeper, pull back = arrival/summary).
- 2–3 transition types per film, repeated on purpose. **Shared-element handoffs** beat every effect: the dot becomes the
  graph pen, the button becomes the page, the colour flood carries the text. No crossfades.
- **No idle wobble**: between entry and exit every second is owned by something meaningful (a staged reveal, a camera
  move with intent, a cursor action, an animated sequence). Pause on any frame — something should be mid-flight.
- Give a climax 0.3–0.75 s of stillness before it lands.

## Timing & speed

- Move duration ≈ 0.35 s + 1.35 ms per pixel travelled; secondary moves run at 55–75 % of the primary's duration.
- Readable text moves ≤ 3 px/frame; nothing faster than ~60–80 px/frame (blur can't save it — redesign the move).
- Never fade *out* on an expo-out curve (it lingers); exits accelerate.
- Hook in 1–1.5 s; the subject named by ~2 s; about one new idea per 1.5–2.5 s; no logo intro.
- Spring settles: closed form, tiny overshoot (≤ ~2–5 %); a value that changes target several times = sum of springs.
- Pace calm music and narration **by phrase and energy**, never by an invented beat grid; on rhythmic music lock only
  1–3 big moments hard to the beat per 15–25 s and let other reveals drift ±0.15 s toward strong cues.

## Arabic / RTL (our edge — nobody else handles it)

- **Never animate Arabic letter by letter**: letters join, transformed glyphs break. Reveal whole words or lines; wipes
  run right → left; typing reveals word by word.
- Emphasis by colour or weight on a whole word — never a box behind it.
- Pre-break lines yourself (fixed lines), measure only after fonts load, no full stops on screen in titles.
- Check glyph coverage of the chosen font for every character (some display fonts miss ـ, ء, Arabic digits).
- 9:16: hook text in the top third, the action in the centre, small chips low; recompose 16:9 ideas, never crop them.
- Religious content: phrase grid from the narration instead of music; no tonal SFX. Visual devices that fit: mosaic /
  zellige tiles that flock into shapes, shadow-theatre / paper cut-outs, slow continuous camera moves.

## Captions (group rules; see filmora-text)

New group at: a pause ≥ 0.5 s, a sentence end, a comma + ≥ 0.25 s, a discourse reset ("بس", "يعني", "so"), or 6 words /
2.5 s. Minimum 2 words and 0.5 s; one group on screen; in = first word − 0.08 s; out = min(next in − 0.05, last word end
+ 0.6 s). Max 2–3 caption styles per clip and one "crown" line.

## Chromium traps (our renderer is Chromium)

| symptom | cause | fix |
|---|---|---|
| one-frame pop | an SVG filter switching between 0 and > 0, or a camera term that isn't continuous | keep a 0.01 floor; make every term a continuous function of t |
| text stair-steps / vertical snap at the end of a rise | fractional left/top + transform pixel snapping | animate transforms only; let the final frame land on whole pixels |
| blur jumps in steps | blur radii quantised ~0.5 px | finish entrance blur at 60 % of the move |
| ghost copies | `will-change` + animated blur, or too few subframes on fast moves | no will-change on camera-scaled layers; 8 subframes for fast moves |
| shape freezes | negative SVG width/height/r | clamp to ≥ 0 |
| gradient banding | 8-bit gradients | add grain/dither; avoid large smooth gradients |
| page background in "transparent" layers | body/html background is painted even with omit_background | clear it for alpha renders (motion_render does) |
| light fringe around alpha edges in Filmora | Filmora reads alpha as premultiplied, Chromium gives straight | solved: motion_render premultiplies every alpha clip |

## Anti-slideshow lint (check the storyboard)

No two neighbouring scenes with the same layout or treatment · static cards ≤ ⅓ of the runtime · not only Ken Burns ·
no opacity-toggled sections · ≤ 3 text levels on screen · corner labels / tiny eyebrow text / timecodes only when the
style justifies them (they read as AI tells) · every element earns its place.

## Style words switch whole looks

One precise style word changes everything (e.g. "Risograph" → grainy spot inks, misregistration, overprint;
"oscilloscope" → phosphor grid, one bright trace). Keep a style word in every design-system.md.

## Ideas worth keeping for later

Powers-of-ten zoom as a story spine; a single persistent element (player bar, dot, card) linking scenes; "only the
subject's own assets" (no stock); a live counter + question hook for satisfying 9:16 shorts; real phenomenon
simulations for explainers; saving an approved edit as a reusable named style.
