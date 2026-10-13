# Premium motion playbook

Distilled (in our own words) from Duncan Rogoff's "Turn Claude Into a Motion Design GENIUS" and the public prompt library
at prompt-motion.com (motion films made with Claude, each posted with its prompt). Use it for every motion piece.

## The 5-step workflow (never skip 1–4)

1. **References first.** Don't let Claude guess a style. Browse prompt-motion.com (built-in browser; filters: Product UI,
   Kinetic type, Charts, Diagrams, Shapes, Particles, Characters, Photos, Phone, Music, Code) or the user's own examples.
   Pick 2 the user likes + up to 3 more with the same feel; for each keep: link, author, the prompt, a few frames
   (save posters/frames into the project's `references/`). Say which ones you rejected and why.
2. **Study them.** Write notes per reference: colours, type, layouts, how text and cards move, pacing, sound. Then one
   ranked list of "moves worth stealing" (user's favourites first) and what to leave out for this brand. Be honest.
3. **Design system file** (`design-system.md` in the project): the feeling in one line · look (palette hex, ink, accent,
   grain/texture) · type (families/weights from font_scout, roles) · 4–5 signature moves · motion rules · a menu of 10+
   layouts · a banned list · where each rule came from. Keep the user's brand colours. Every scene fills the frame,
   nothing overlaps, no two neighbouring scenes share a layout.
4. **Stills before video.** Render one poster frame per scene type (motion_render `--stills`), make a contact sheet,
   check yourself first (readable, nothing overlapping or too close to the edge, real assets only), then show the user.
5. **Notes like a designer.** The user says what they see in plain words ("too much copy", "buttons look like AI slop",
   "make it one continuous camera shot", "not premium"). Apply the note, and **write it into design-system.md,
   replacing the old rule** (never keep two conflicting rules).

## Anatomy of a strong motion brief (how the best prompts are built)

`inputs` (what to ask the user + defaults) → `direction` (format, fps, the look, signature idea, motion rules, banned
list) → `structure` (scene/beat list with timings or beat numbers) → `sound` (music drop, ducking, one SFX per event)
→ `build` (one HTML page, `seek(t)`, render/encode, checks) → `gotchas` (known failure modes) → `start` (what to show
before building: beat map + 4–8 stills). Write our own scene plans in this shape and keep them in the project.

## Motion rules that separate premium from slop

- **One concept, one continuous take.** Each scene is *made out of* the previous one: shapes, type and colour transform
  into the next scene (shared-element handoffs: a button grows into the page, a dot becomes a graph, a colour floods
  from one object and shrinks into another). Crossfades and random transitions read as templates.
- **A signature element** travels through the whole film (one accent dot, one card, one glass pill) and returns at
  the end; the last frame can match the first so it loops.
- **Camera**: one named move per shot (dolly, push-in, crane, orbit, rack focus), eased in/out; push 1.00→1.04 per
  scene and start the next scene at the zoom the previous one ended (no zoom snap); never zoom in and out back-to-back;
  never reverse direction; interpolate zoom in log space. Shots enter already moving and leave accelerating.
- **Easing**: closed-form springs (critically damped or a tiny overshoot) for pops and settles; exponential ease-out
  for arrivals; never linear for objects; no bouncy/elastic easing except one deliberate element.
- **Blur follows speed and direction** on fast moves; render with motion-blur subframes (4–8 per frame, averaged).
- **Text**: rises from a mask line or types word by word on the voice; outgoing text leaves before incoming text takes
  the same space; one emphasised word per line (accent colour or gradient), never a highlight box behind a word.
- **Nothing pops in**: fades ≥ 0.3 s (0.05 s looks like a pop). Holds ≤ 0.5–1 s; something changes on every beat.
- **Floods/fills** must pass all four corners and take ≈ 0.35 s, or they look like a flash.
- **Rhythm**: land scene changes on phrase starts / downbeats; music drop on the strongest line; image switches on
  16th notes only in deliberate bursts.
- **Banned by default**: particle bursts, glows on everything, lens flares, camera shake, RGB split, white flashes,
  crossfades, generic gradients, selection-box highlights, beat-snapped slams, holds > 1 s, anything template-like.

## Build & QA rules

- One HTML page; every pixel a pure function of time (`render(t)`/`seek(t)`); seeded randomness; declare all state
  before the first seek; set z-order on every layer.
- Renders: 60 fps for fast UI pieces (30 fps is fine for explainers); motion blur with `--subframes 4` (8 for very fast
  moves); H.264 CRF 12.
- Before the full render: contact sheet of stills; scan frame differences for single-frame pops; check every fast
  moment frame by frame; check text readability in every scene.
- Sound: one SFX per visual event placed by its measured peak (trim long risers around the peak); duck music under the
  voice (voice ≈ 9 dB above music in 300 Hz–4 kHz); loudness −14 LUFS. Word timings: split the voice at pauses ≥ 100 ms
  and transcribe each part (single-pass Whisper can be ~0.5 s late).
- Religious/Quranic content keeps the user's rules (no music, no tonal SFX).
