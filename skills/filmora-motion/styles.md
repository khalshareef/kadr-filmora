# Motion style library

Each style = feeling · look · type · signature moves · banned. Pick one with the user (show the closest
prompt-motion.com examples as references), copy its block into the project's design-system.md, then adapt to the brand.
Fonts are always chosen by the user from their installed fonts (font_scout.py); the type line is only a direction.

## 1. Line-Art Explainer (the bundled example reel)
Feeling: calm, clever, hand-made news explainer. Look: cream canvas, black line art (6–9 px, round caps), one accent,
dot grid with parallax. Moves: strokes that draw themselves; pop-with-overshoot icons; world-canvas camera flights with
roll + zoom dip + directional blur; voice-driven bars; playhead timelines; accent circle wipe into the CTA.
Banned: gradients, glows, 3D, stock photos.

## 2. AI Lab Launch
Feeling: confident, minimal, "taste". Look: white canvas, black ink, one typeface, real images; liquid-glass controls
(frosted body, refracted edge band, sheen, rim, soft lift shadow) over a slow pastel aura so glass shows on white.
Moves: captions typed word by word on the voice; image collages that drift; 16th-note image bursts into the drop;
3×3 grid fly-in; result card restyling on each beat; final burst of images converging into the logo.
Banned: selection-box highlights, white flashes, 3D, beat slams.

## 3. Warm Product Film (one continuous take)
Feeling: playful, appetising, app-store hero. Look: warm white (#f5f5f2-ish), black UI, two punchy accents (lime +
orange), iridescent glow ring around the input. Moves: push into the composer → typing → send ripple → button grows into
an object → accent flood fills frame (0.35 s) → cards burst from centre → shared-element return → button expands into
the page → word-by-word statement on black → mark + wordmark wipe. Banned: crossfades, blur-ins, 3D, particles,
reversing camera, holds > 1 s.

## 4. Single-Accent Dot System
Feeling: precise motion-design flex. Look: off-white canvas, near-black scenes, bold type, ONE vivid accent dot.
Moves: the dot connects every scene — sits on a letter, jumps to draw a spring graph (same spring function drives dot and
curve), grows into a circle that fills the frame, morphs square → pill, orbit of words, halftone field reveal, returns
to the start (loop). Banned: gradients, glows, particles, any motion not tied to an on-screen element.

## 5. Morphing UI Shape
Feeling: Dribbble-level UI craft. Look: light warm-grey canvas, black/white components, one UI font, optional accent.
Moves: one shape never cuts — button → loader → check → island → player → slider → toggle → tabs → chart → ⌘K → toast →
button; a cursor drives every change; edges ride separate springs so they stretch; content swaps with a short blur.
Banned: bouncy easing, glows, mismatched icon strokes, dead time.

## 6. Kinetic Architecture (typography as structure)
Feeling: editorial monument, spoken word. Look: deep colour ground, paper text, one structural accent; high-contrast
serif + heavy grotesque + small mono marks. Moves: words get physical roles (lintel, load, support, opening, platform)
built from the real letterforms; baseline bends under load; a counter becomes an aperture; one earned moment of perfect
stillness (≥ 400 ms); critically damped settling. Banned: protest clichés, decorative motion, unreadable deformation.

## 7. Paper & Marker
Feeling: founder whiteboard energy. Look: paper-light canvas, marker notes that draw on (stroke-dashoffset), huge
condensed kinetic type, hard light/dark switches. Moves: a new idea every 1.5–2 s, squash/stretch, overlap, smear,
follow-through; a sound on every hit; drums drop on the dark switch. Banned: on-screen jargon, invented numbers,
generic push/slide transitions, boxed logos.

## 8. Dark Stage Brand Film
Feeling: premium music/product ad. Look: rounded near-black stage (~80% × 75% of frame) over an atmospheric brand-colour
background; white type, grey secondary, brand accent for emphasis. Moves: icon grows in with minimal overshoot; masked
vertical text reveals; UI rises with a slight perspective tilt that settles frontal; one hero artwork keeps its identity
through search → detail → zoom; brand-colour flood; covers converge into the logo. Banned: particles, shockwave rings,
lens flares, shake, crossfades.

## 9. Keynote Glass
Feeling: Apple-keynote soft and bright. Look: near-white page, haze blues, deep-blue sky gradient, frosted glass cards
and prompt boxes. Moves: every shot enters already moving (exponential ease-out) and leaves accelerating or on a blur
ramp; cursor that turns toward where it goes and grows on hover; whip-tilt through a light flash; giant frosted titles.
Banned: purple/orange (if the palette is blue), crossfades, frozen frames.

## 10. 3D Film Camera (three.js in the page)
Feeling: cinematic product space. Look: soft daylight, key/fill/rim lights, environment reflections, fog, physical
materials. Moves: one named film move per shot (dolly, crane, orbit, rack focus); a signature pull-back shot designed
first; things react to each other via springs. Renders through the same `render(t)` contract (seed everything).
Banned: default materials, floating labels, glows everywhere, slowly spinning object as the whole idea.

Mixing: a project may borrow one signature move from another style, never more — the design system must stay coherent.

## More styles from the study (short)

- **11. Single-Accent Dot Take** (built as "One Dot Listens"): warm off-white, near-black, one green dot that is the
  voice pulse → waveform pen → chip light → caret → list cursor → flood → graph pen → playhead → button. No corner text.
- **12. Risograph Print**: off-white paper, 2 fluorescent spot inks with grain, 1–2 px misregistration, overprint
  (multiply). Carries non-Latin scripts beautifully — strong for Arabic posters/titles.
- **13. Instrument / Oscilloscope**: phosphor grid, one bright trace, mono readouts (corner text allowed only here).
- **14. Powers-of-Ten Zoom**: start from one dot, windows spawn, zoom out across scales and dive back into a device.
- **15. Hand-Made Surfaces**: pencil, marker, paper cut-outs, boiling lines on twos; warm and human. Shadow theatre
  (خيال الظل) variant for contemplative vertical stories — fits religious reels without music.
- **16. Mosaic / Zellige Flock**: tiles lift, flip and fly into shapes or calligraphy, then click back — Islamic
  geometric aesthetic, visual-only (no tonal sound needed).
- **17. Stage in Canvas**: rounded content stage floating on an atmospheric colour field; centred small picture with
  motion around it (matches the user's talking-head preference).
- **18. Storybook Data Explainer**: simulate the real phenomenon with real numbers, one formal idea per scene,
  characters and callbacks.
