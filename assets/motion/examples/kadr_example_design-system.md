# Kadr for Filmora — official example · design system

**Feeling in one line:** calm, clever and hand-made. You talk, one orange dot carries what you said, and an editable
Filmora project builds itself around it.
**Style word:** *line-art explainer* (styles.md #1) + one borrowed move from #4 Single-Accent Dot (the dot connects every
scene). Nothing else is mixed in.

## Concept
- **One concept:** the orange dot is your voice (your intent). It is a voice pulse, then a caret, the send button, the
  pen that writes the file, a courier between the four parts, the playhead, a spring curve, a split handle, and at the
  end the full stop of the «كادر» wordmark. The last frame comes back to the first (a dot), so the film loops.
- **Kadr = frame:** four viewfinder brackets first frame the voice bubble (on «فيلمورا»), then clamp around the composer
  on «كادر», and come back as the logo frame.
- **One continuous world** on a cream canvas with a parallax dot grid. Travel always goes **leftward (RTL)**, then
  **up** for the conclusion (logo).

## Look
| token | hex | use |
|---|---|---|
| cream | `#F0EEE6` | background and every shape fill (shapes sit on the canvas as line art) |
| ink | `#141413` | all line art, text inside graphics |
| orange | `#D97757` | the ONE accent: the dot, voice, "active / edited / now" |
| warm grey | `#B4AC9D` | secondary strokes (connectors, side panels, axes, ruler); grid dots = `#C9C1B2` at 55 % |

- Stroke 7 px (main), 9–10 px (kadr brackets), 5–6 px (secondary), 3–4 px (grey detail). Round caps and joins everywhere.
- Flat: no glow, no shadow, no gradients, no textures.
- **Type inside graphics** (few words only; headlines and captions are native Filmora texts):
  Arabic bold = `KadrHead`, Arabic medium = `KadrBody`, command = `KadrMono`. These are **placeholders** (Readex Pro /
  Cascadia Mono). The user picks the real fonts from specimens before the final render; change the 3 `@font-face` lines.

## Layout (9:16, 1080×1920)
- Graphics live in **y 230–1110** (camera centre y 670). Nothing in a hold goes below y ≈ 1070.
- Reserved for native texts added later: Arabic headline y ≈ 0.62–0.66 (1190–1270), English subline `below` it,
  dynamic captions y ≈ 0.80. Side safe area: ≥ 55 px.

## Signature moves
1. **Draw-on with the dot as the pen**: outlines draw themselves, and the dot rides the drawing tip.
2. **Shared-element handoffs** instead of cuts: bubble → composer, caret → send button, file → editor window, four part
   tiles → the four timeline clips, four feature tiles → a grid of everything → back into the dot.
3. **Camera flights**: sine ease, 0.7–0.75 s, roll ±3.5°, zoom dip 22 %, directional blur from the real screen speed.
   One gentle push-in on the editor (1.03 → 1.08) that keeps the whole window inside the frame — never crop the
   editor. Holds push 1.00 → 1.05 with a little drift and roll. Zoom is continuous (log space).
4. **Word-locked beats**: every reveal lands on its spoken word (table below). Live voice from `AMP` wherever a voice
   is shown (S1 bars, sounds tile, preview, captions tile, end pulse).
5. **Springs**: closed-form, critically damped or a small overshoot. The one deliberate wobble is the spring curve in S7.

## Motion rules
- Easing: `expOut`/`out` for arrivals, sine in-out for flights and hops, springs for pops and settles; linear only for
  time itself (playheads).
- Speed cap: the dot ≤ ~90 px/frame on screen (checked frame by frame), camera ≤ ~70 px/frame. Fast moves get blur.
- Arabic is revealed **as whole words** (typing word by word, wordmark rising from a mask), never letter by letter.
  Latin command text may type character by character.
- Fades ≥ 0.15–0.3 s; nothing pops in on a single frame. Blur never switches between 0 and >0 (0.01 floor).

## Banned (with the replacement)
particle bursts → tiles that multiply and collapse back · glow/shadows → flat fills on cream · crossfades → shared-element
morphs · white flashes → none · camera shake → soft drift · selection boxes behind words → the active chip fills
orange · letter-by-letter Arabic → word by word · corner labels / timecodes / HUD → none · a second accent colour → none ·
brand logos of Claude or Filmora → plain words and a generic editor · holds > 1 s without something moving.

## Scene plan (times from words.json; VO 30.2 s)
| # | time | words → what moves | camera |
|---|---|---|---|
| S1 | 0.00–3.64 | frame 0: the dot is already splitting into 13 live voice bars (hook) · bubble draws itself 0.12–0.95 · «فيلمورا» 1.58 kadr brackets snap round the bubble · «بتحكي» 3.0 bubble breath | opening pull-back 1.35 → 1.0, then push |
| S2 | 3.64–7.80 | bars collapse into the dot (3.3) · bubble **morphs into the composer** · «كادر» 3.92 brackets clamp onto it · «بتكتب» 4.52 request types word by word, the dot as caret leading · «لـClaude» 5.64 model chip pops · «العادي» 7.32 caret becomes the orange send button, pressed 7.55 | same shot, slow push 1.0 → 1.06 |
| — | 7.60–8.35 | dot launches from the send button and leads | **flight left** to the file |
| S3 | 7.90–10.74 | «بكتبلك» the dot pens the file outline (8.25–9.15) · fold · 5 lines print right→left 9.2–10.0 · «فيلمورا» 9.48 `.wfp` tag pops · «كامل» 10.14 dot inflates into a ✓ badge | hold, push 1.0 → 1.05 |
| S4 | 10.74–13.94 | file shrinks down · dot hops tile to tile, each part pops on its word: «مقاطع» 10.74 clip · «ونصوص» 11.50 text · «وإفكتات» 12.26 effects · «وأصوات» 13.10 sounds (live bars); connectors draw; active glyph orange | hold |
| S5 | 13.98–16.48 | dot hops onto the file · cursor double-clicks 14.40/14.54 · **file morphs into the editor window** 14.6 (opens empty) · the four parts tuck into the media bin 14.62–15.2 while title bar, preview (a live mini of S1), sliders and ruler draw on · then they drop one by one from the bin and **become the four clips** 15.4–16.4 · dot drops to the playhead | hold |
| S6 | 16.48–20.10 | whole editor stays in frame · «وكل إشي فيه» ripple lift across all clips · «تعدّله» 17.82 cursor grabs the title clip and drags it (orange while edited) · «كأنك عملته» trims the audio clip longer · «بإيدك» 19.54 release ripple; playhead runs | gentle push 1.03 → 1.08 (window never cropped) |
| — | 19.60–20.30 | the playhead dot leads | **flight left** |
| S7 | 20.10–24.66 | 4 tiles, each lands on its word: «قص» 20.10 beat-cut (playhead dot cuts the clip on each beat) · «ترجمة» 21.40 word chips light on the real spoken words · «موشن» 22.66 dot draws a spring curve · «وتقسيم» 23.58 frame, «شاشة» 24.14 dot draws the divider and a portrait pushes in | hold, push 1.0 → 1.05 |
| S8 | 24.72–26.06 | «أي إشي بدك» the 4 shrink into the middle of a 4×4 grid, 12 more tool tiles pop outward · «إياه» 25.6 everything collapses into the dot | hold |
| — | 25.85–26.55 | the dot rises first | **crane up** |
| S9 | 26.06–30.20 | brackets start opening during the crane-up (25.9) · wordmark rises from a mask · dot hops to the end of the word and lands with a squash (26.78) · «ببلاش» 27.44 command chip draws, «مجاني» pops · «وجاهز تجرّبه» `/plugin install kadr-filmora@kadr` types · «الآن» chip press, frame tick · «شكراً» dot pulses with the voice | hold, push 1.0 → 1.07 |

World: A (0,0) S1–S2 · B (−1300,120) S3–S6 · C (−2600,0) S7–S8 · D (−2600,−1300) S9.

## Layers (motion_render --layers; DOM order = z order)
`bg` (opaque: cream + parallax grid) · `S1-2_bubble_to_composer` · `S1-2_kadr_frame` · `S1_voice_bars` ·
`S2_typed_request` · `S2_model_chip` · `S2_send_button` · `S3-5_file_to_window` · `S3_written_lines` · `S3_wfp_tag` ·
`S5_editor_panels` · `S5_preview_voice` · `S6_clip_video/title/effect/audio` · `S6_playhead` · `S4_connectors` ·
`S4_part_clips/texts/effects/sounds` · `S7_tile_beat_cut/captions/motion/split` · `S8_more_tiles` · `S9_logo_frame` ·
`S9_wordmark` · `S9_install_chip` · `hero_dot` · `S2_send_arrow` · `S3_done_check` · `cursor`.
Each layer has its own time window; the page hides it outside the window, so the stills match the layered output.

## Sound plan (next round)
Voice 0 dB, no music needed (or a very soft bed if the user wants). Soft Foley only: whoosh −13 dB on the three flights
and the push-in; plastic/wood taps −14 dB on the pops (4 parts, 4 features, chips); a paper slide for the file; a soft
click for the send button, the double-click and the drag/trim; a camera shutter on the logo landing. No bells or chimes.

## Notes log
- Round 1: storyboard stills only.
- Round 2 (approved storyboard): staged the window opening (parts go to the media bin first), logo frame opens
  during the crane, bars from frame 0, editor never cropped (rules above replaced). Rendered 34 layers with 4 subframes
  (pops 0), built `Kadr Example.wfp` with native texts, dynamic captions and 14 soft Foley sounds.
