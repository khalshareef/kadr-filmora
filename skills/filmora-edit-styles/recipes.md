# Style recipes

Each recipe: **rhythm · moves · transitions · hits · look · text · sound**. `pk` = `fx_pick.Picker(seed)` — use one
picker per project so nothing repeats. B = beat length.

## Velocity
- Rhythm: 1 beat in high sections, ½ beat stutters before the drop, 2 beats in verses. Sharp, readable shots.
- Moves: punch zoom on every kick; push/pull alternation; on the drop shot `scale [[0,130],[0.12,104],[d,100]]`.
- Transitions: `pk.pick("velocity", use="transition")` — cross zoom, warp zoom, fast zoom, whip — 0.2–0.35 s, on
  2-beat cuts only; hard cuts on 1-beat cuts.
- Hits: motion-blur / zoom-lens / shake hits on snares (≤ 1 per beat), black flash into the drop, white flash on
  every 4th bar.
- Look: none or a light contrast look; optional speed-lines `bar` effect on the drop phrase.
- Text: 1–3 words, `punch`, size 120+, white + one accent colour, centred.
- Sound: whoosh on transitions, impact on the drop.

## Glitch Party
- Rhythm: 2 beats in the intro, 1 beat after the first drop, stutters on fills.
- Moves: beat_pulse (period = B, amount 0.06) on long shots; rotation shake on snares.
- Transitions: `pk.pick("glitch-party", use="transition")` — RGB drift, glitch blocks, fast RGB, distort glitch.
- Hits: glitch / RGB / slice / stripe-flash hits on snares; one `bar` effect per bar in high sections
  (`pk.pick("glitch-party", use="bar")`: beat-reactive lights, holo scan, colourful flicker).
- Look: a neon/cyber look (`pk.pick(["neon","cyber"], use="look")`) or colourful negative for the drop bar only.
- Text: glitch text effects (`fx_pick.py glitch --on text`), neon colours (#C6FF3D, #FF2E88, #00E5FF).
- Sound: glitch/stutter SFX on 1 of 3 hits, impact on drops.

## Cinematic Trailer
- Rhythm: long shots (2–4 bars) building to faster cuts (1 beat) at the climax; a black hold (0.5–1 s) before the title.
- Moves: slow push-in on every shot (`loop: push`, 1.06–1.1); no shakes except at impacts.
- Transitions: fade through black, light leaks, film burn, smoke cover transition — 0.6–1.2 s; hard cuts in the climax.
- Hits: white/flare flash on impacts, lens flare overlay across the title; smoke/fog `look` overlay at low opacity.
- Look: letterbox (cinema bars) + one cinematic colour filter (`pk.pick("cinematic-trailer", use="look")`,
  e.g. teal-orange / epic contrast); film grain optional.
- Text: few words, wide tracking style fonts (Montserrat, Cinzel, Alexandria), `fade` 0.8 s, centred, between shots on
  black ("في عالم…"); final title with a flare.
- Sound: braams/impacts on hits, riser before the title, music with fade out.

## Hype / Sport
- Like Velocity but heavier: energy 4–5, shake + fire/energy hits, speed lines `bar` on the best action.
- Freeze + flash on the best moment with the player name/score as text.
- Look: high contrast; fire particles overlay on the drop phrase.
- Text: big condensed bold font, uppercase (English), countdown before the drop.

## Smooth Vlog
- Rhythm: 2–4 beats per shot (or by sentence); match cuts on movement.
- Moves: gentle push (1.05) or drift; no punch zooms.
- Transitions: dissolve, blur dissolve, push/slide, light leak — 0.5–0.8 s; on ⅓ of the cuts, hard cuts elsewhere.
- Hits: none or a soft light leak on section changes.
- Look: warm/natural look (`pk.pick("smooth-vlog", use="look")`), optional camera-UI/REC overlay for a camcorder feel.
- Text: location/date lower-thirds, handwritten or clean sans, `fade`/`rise`.
- Sound: soft whooshes only on light leaks; music -6 dB under talking.

## Retro VHS
- Rhythm: 2–4 beats; occasional "tape skip" stutter (2 × ½ beat with same src_in).
- Moves: tiny shakes, no zoom punches.
- Transitions: VHS static / TV static overlay 0.3 s on cuts, TV switch-off at the end.
- Look: VHS REC date overlay or camcorder UI + old film/noise grain + faded colour filter for the whole video
  (`pk.pick("retro-vhs", use="look", n=3)` → pick one UI, one texture, one colour).
- Text: date stamp style (monospace, white/yellow, top-left), `fade`.
- Sound: tape click/static at cuts (-14 dB), music slightly low-passed by the user if wanted.

## Kinetic Typography
- Text is the hero: one word/phrase per beat or per spoken word (captions.py with word JSON, `--max-words 1–2`).
- Alternate size (90/140), y (0.42/0.55), colour (white / accent) every word; `punch` in, `fade` out 0.15 s.
- Background: one slow clip or a solid/gradient PNG (filmora-design-system); beat_pulse on the background.
- Hits: text effects (`fx_pick.py kinetic-typography --on text`) on key words only.

## Romantic / Wedding
- Rhythm: 4 beats / one phrase per shot; slow.
- Moves: slow push and drift; Ken Burns on photos.
- Transitions: dissolve, soft romantic fade, petals, light leak — 0.8–1.2 s.
- Look: soft glow / warm filter; heart or bokeh overlays at most once per minute.
- Text: script or elegant serif font, names + date, `fade` 1 s, gold or white.
- Sound: no hits; music fade in/out.

## Memories Slideshow
- Photos 2–3 s each (or 2 bars), Ken Burns alternating direction; videos 3–5 s.
- Frames/polaroid/photobook effects (`pk.pick("slideshow", use="clip")`) on every 3rd–4th photo, not all.
- Transitions: dissolve / slide / film burn; one look for everything (warm/faded).
- Text: title card at start, date/place captions, closing line.

## Calm / Educational (talking head, lessons, religious)
- Rhythm by sentences: cut silences, breaths, false starts and repeated phrases (from the transcript); jump cuts
  hidden by alternating scale 100 / 110 on consecutive segments.
- Moves: very slow push (1.03–1.05) on long segments; no shakes/flashes/glitches.
- Transitions: none or short dissolve between topics.
- Look: none (respect soft/flat footage) or `Natural Enhance`-type very light correction.
- Text: exact-wording captions (filmora-text), key-word highlight in one accent colour, section titles.
- Graphics: small centred picture with motion panels above/below (filmora-design-system) when the user wants motion.
- Sound: religious/Quranic → no music, no tonal SFX. Others: soft music -18..-22 dB under voice, or none.
