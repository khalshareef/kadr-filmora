---
name: filmora-motion
description: Make real motion graphics for Filmora projects — line art that draws itself, shapes that assemble, data charts that grow, word chips synced to the voice, a virtual camera that flies between scenes with zoom, roll, parallax and motion blur — rendered from a time-driven HTML/SVG page into clips that sit in an editable Filmora project with native texts, captions and SFX. Use whenever the user wants motion graphics, an animated explainer, a news reel with graphics, "موشن جرافيك", "موشن حقيقي", "حركة كاميرا", "خطوط بترسم حالها", "انيميشن للخبر", or when an edit built only from static PNGs + keyframes would look like a slideshow. Works with filmora-core, filmora-text, filmora-design-system.
---

# Filmora Motion — motion graphics that look designed, not a slideshow

Filmora can't animate vector shapes from a project file, so the graphics are **rendered as clips** (one per scene)
from an HTML/SVG page whose every pixel is a pure function of time, and the editable parts (headlines, captions,
sound) stay native in Filmora. Ask the user once: "the animated graphics come as ready clips; texts and timing stay
editable" — then build.

Files: `${CLAUDE_PLUGIN_ROOT}/assets/motion/kadr-motion.js` (helpers), `assets/motion/examples/kadr_example_layers.html`
(complete 30 s 9:16 reel, 9 scenes, one camera world: voice dot → speech bubble with live voice bars, typed request,
project file that draws itself and releases four parts, editor window whose timeline fills clip by clip, feature
tiles, crane-up to the logo; 34 layers = opaque background + 33 transparent elements — start from this one),
`examples/data.js` (its voice loudness + word timings), `examples/kadr_example_design-system.md` (the design system
written before drawing it), `scripts/motion_render.py` (renderer).
The example loads `../kadr-motion.js`; in a copied page change it to `kadr-motion.js` (copied next to the page).

## Read first

- [premium-playbook.md](premium-playbook.md) — the 5-step workflow (references → study → design-system.md → stills →
  designer notes), anatomy of a strong motion brief, premium motion rules, build & QA rules.
- [styles.md](styles.md) — 10 named styles (Line-Art Explainer, AI Lab Launch, Warm Product Film, Single-Accent Dot,
  Morphing UI, Kinetic Architecture, Paper & Marker, Dark Stage, Keynote Glass, 3D Film Camera).
- [motion-doctrine.md](motion-doctrine.md) — seams/vector law, timing & speed limits, **Arabic/RTL rules**, caption
  grouping, Chromium traps, anti-slideshow lint (from ~380 studied briefs + top GitHub motion skills).
- References: prompt-motion.com (built-in browser) — motion films made with Claude, each with its prompt.

## Workflow

1. **Inputs**: voice-over (or music), design reference / palette, topic. Transcribe with word timings
   (faster-whisper `word_timestamps=True`, mark sentence ends `"break": true` for captions.py).
   **No voice?** Time scenes by reading pace instead (≈ 0.4 s per word of on-screen text + 1 s to settle, 3–6 s a
   scene), skip `data.js`/captions, and put the soft SFX on the visual events only.
2. **Palette**: take colours from the reference (sample pixels) or the named brand; show 4–6 hex swatches to the user
   **before** building. Default modern look: cream background, black line art (stroke 6–9 px, round caps), one accent.
   When nobody can answer (a scripted/unattended run), pick one style from styles.md, say which, and go on — the same
   applies to the reference/study steps of premium-playbook.md.
3. **Scene plan**: one scene per sentence/idea; times from the word timings (or reading pace). Each scene = one visual idea that
   *explains* the sentence (not decoration). Write the plan as a short table and keep it.
4. **Data for the page** (voice pieces only): `AMP` (voice loudness per frame, librosa RMS at fps, normalised) and `WORDS`
   (`[word, start, end]`) in `data.js` → bars, chips and playheads move with the real voice.
5. **Write the page** in the project folder (copy the example, replace scenes) and **copy
   `assets/motion/kadr-motion.js` next to it** — the page loads `<script src="kadr-motion.js">`, so it keeps working
   when the plugin folder moves. Then **storyboard first**:
   `python motion_render.py page.html --stills 2.2,5.8,10.9,… --out "stills/f_{t}.png"` (files like `f_002_20.png`) → look at them (contact sheet),
   fix layout, send the user the key frames.
6. **Render clips**: `python motion_render.py page.html --cuts 0,3.45,8.16,… --out "assets/motion_S{n}.mp4" --subframes 4`
   (H.264 CRF 12, real motion blur from 4 averaged subframes; about 13 s of rendering per second of video at
   1080×1920 with 4 subframes, ~4 s without). Then
   `python motion_qa.py pops assets/motion_S*.mp4` must report 0 suspicious frames; `python motion_qa.py contact "stills/*.png" --out sheet.jpg --cols 5` makes the
   contact sheet. `--alpha --out layer.mov` gives a transparent ProRes 4444 layer.
7. **Spec**: motion clips on track `motion` at frame-exact times (`round(t*fps)/fps`), native headline (y ≈ 0.56,
   `role`) + English sub with `below: <headline id>` (never a fixed y), captions (y ≈ 0.70), SFX on the visual events, voice 0 dB. Build with filmora-core.

## Background and assets are separate from the start

Design every motion piece as **layers from the first line of code**, never as one flat video that is split later: the
background (paper, gradient, grid) lives in its own group and renders as its own opaque clip; every asset group is
drawn on a **transparent page** (no body/page colour, no background rect inside an asset group) and renders as its
own transparent clip; texts stay native Filmora titles. The user then moves, times or swaps any element in Filmora.
Edges: Filmora always reads ProRes alpha as premultiplied, so `motion_render.py` premultiplies every transparent clip
(straight alpha gave the old light fringe; verified clean on Filmora snapshots). One clip per scene is still possible
when the user asks for a single flat clip. To make layers: wrap each element group with `lay(name, sceneGroup, sceneIndex)`
(`data-layer`), list them in `KADR.layers` (`{name, start, end, opaque?}`; background `opaque: true`) and provide
`KADR.solo(name)` (show only that layer; `null` = all). Then
`python motion_render.py page.html --layers assets/layers` → `NN_<name>.mov` (ProRes 4444 alpha, camera + blur baked in)
+ `layers.json`. In the spec: background z 0, element layers z 1.xx by order **inside their scene** (scenes don't
overlap on the canvas, so they share tracks), HUD z 8, texts above. `--only a,b` re-renders single layers.
Everything stays on the main timeline — **no compound clips** (house rule: people get lost inside them).
Name layers by meaning (`S4_bubble_chat`, `S5_bars_result`) — the file name is what the user sees on the clip.

## Page contract

```html
<script src="kadr-motion.js"></script><script src="data.js"></script>  <!-- both copied next to the page -->
<svg width="1080" height="1920"> … <g id="para"/> <g id="camwrap" filter="url(#mblur)"><g id="cam"/></g> <g id="hud"/> </svg>
<script>
const { E, prog, pop, fade, draw, tr, lerp, clamp, mapr, $ } = KADR_HELPERS;
function render(t) { /* set every attribute from t — no CSS animations, no timers, no randomness */ }
window.KADR = { width: 1080, height: 1920, fps: 30, duration: 31.77, render };
</script>
```
Never name a global `top`, `window`, `name`, `status` (browser globals) — page errors are printed by the renderer.

## Motion vocabulary (use several per scene)

- **Line drawing**: paths with `pathLength="1"`, `draw(el, prog(t, t0, t1))`; stagger parts 0.1–0.2 s; fill fades in
  after the stroke is ~60 % drawn.
- **Pop with overshoot**: `tr(el, {s: pop(t, t0, 0.45)})` for icons, chips, bubbles, buttons.
- **Growth from a base**: bars `tr(bar, {sy: prog(t,…,'back'), origin: 'bottom'})`.
- **Typing lines / RTL**: horizontal strokes drawn from right to left for Arabic text placeholders.
- **Live audio**: bar heights from `AMP` with a bell profile and small per-bar delays.
- **Playhead / progress**: position = `mapr(t, a, b, x0, x1)`; RTL timelines run right → left.
- **Highlight on speech**: element colour switches while `WORDS[i]` is being spoken.
- **Wipes**: a circle of the accent colour growing from the focal point (`prog(..,'in')`) into the last scene.
- **Loops for life**: slow orbit rotation, dashed connectors with moving `stroke-dashoffset`, travelling dots.
- Easing: `out` for entrances, `inout` for camera and moves, `back` for pops/growth, never linear for objects.
  Better: `spring(t, t0, f, z)` (closed-form, z=1 no overshoot), `springs(t, [[t0,v],…])` for values that change target,
  `expOut` for arrivals that enter already moving, `zoomLerp` for zoom in log space.
- Never switch an SVG filter between 0 and >0 (blur floor 0.01) and keep camera drift/roll terms continuous across
  flights — both cause one-frame pops.

## Camera (what makes it feel like real motion design)

- Lay scenes on one **world canvas** (origins ≥ 1300 px apart); the camera group transform is
  `translate(cx_screen cy_screen) rotate(r) scale(z) translate(-x -y)`.
- **Holds**: slow push-in 1.00 → 1.05 across the scene plus a tiny drift (±12 px) and roll (±0.6°).
- **Flights**: start 0.3 s before the cut, end 0.25 s after; position eased `inout`; zoom dips ~0.3 in the middle;
  roll ±4° alternating; **directional motion blur** with an SVG `feGaussianBlur stdDeviation="bx by"` proportional
  to speed (≈ 26 px peak along the travel direction).
- **Opening**: start zoomed in 1.3 and pull back to 1.0 in 0.9 s. **Parallax**: background dot grid moves at 0.45×.
- Put a soft whoosh (−13 dB) at every flight start; headlines enter after the camera lands and leave before it flies.
- **Sound = soft Foley** (house default): plastic/wood taps for pops, paper slides for cards, camera shutter/clicks for
  buttons, soft whooshes for camera moves; relaxing, ASMR-like. No bells, chimes, dings or bling tones (unless very soft).

## Layout (9:16)

Graphics in y 250–950 (centre ≈ 640); native headline y 0.56, English sub `below` it, captions y 0.70; HUD (label,
scene counter, progress bar) at y 90–130. Keep everything clear of the bottom 20 %.

## Text inside the graphics

Small labels/words that are part of a graphic (chips, bubbles, legend) are SVG `<text>` with installed fonts
(`font-family: 'Readex Pro'; font-weight: 700; direction: rtl`). Headlines and captions stay native Filmora texts —
flat solid colour, no stroke (house style), eased `rise`/`pop`.

## Quality bar (check the storyboard against it)

- Every scene has a clear focal object, motion on entry, life while holding, and a camera move out.
- One accent colour used for meaning (the new/good thing), not decoration. Black line weight consistent.
- No empty frame: the next scene's first element appears as the camera lands.
- Nothing static for more than ~1.5 s; nothing moving without a reason.
- Texts never overlap graphics; captions never under the headline.
