---
name: filmora-text
description: Put real, editable Filmora texts into generated projects — titles, headlines, lower thirds, captions/subtitles from SRT or word timings, kinetic typography and beat-synced word hits — in Arabic or English with correct fonts, sizes, safe areas and animations. Use whenever a Filmora project needs any text, captions, subtitles, a title card, a hook line, a countdown or kinetic words, or the user says "حطلي نص", "كابشن", "ترجمة على الفيديو", "عنوان", "كتابة متحركة", "سبتايتل", "خط عربي". Works inside filmora-core specs.
---

# Filmora Text — real Filmora titles, not pictures of text

Every `type: text` clip becomes a genuine Filmora title the user can double-click and edit (wording, font, colour).
Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or two folders above this file).

## The text clip

```json
{"type": "text", "text": "سطر أول\nسطر ثاني", "font": "Cairo Bold", "size": 90, "color": "#FFFFFF",
 "x": 0.5, "y": 0.2, "start": 1.0, "end": 3.5, "in": "pop", "out": "fade", "z": 10}
```
- **Words exactly as the user wrote/said them.** Never fix dialect, spelling or word choice in captions or titles
  (e.g. keep «اللي موقف» as is). If something looks like a typo, ask — don't change it silently.
- `\n` = line break. Text is centred on (x, y). The box is measured from the real font, so nothing gets stretched.
- `font`: an installed font by Filmora's name, "Family Style": `Cairo Bold`, `Alexandria Black`, `Tajawal ExtraBold`,
  `Montserrat Black`. Check what's installed: `python text_measure.py --fonts cairo` (lowercase list; any case works in specs).
  Missing font → error; pick another installed one or ask the user to install it (then restart Filmora).
  Arabic needs an Arabic font (Cairo, Tajawal, Alexandria, Almarai, IBM Plex Sans Arabic, Noto Kufi/Naskh Arabic…).
- `color`: `#RRGGBB`. Outline, shadow, background box and gradient fills are **not** written — for contrast use a
  PNG plate under the text (filmora-design-system) or a text effect from the library (below).

## Sizes and safe areas

**Size by role, not by number** (every font draws at a different real size): put `"role"` instead of `"size"` —
`hit`, `headline`, `title`, `caption`, `label`, `sub`. The builder measures how wide the chosen font really is and
picks the number so the text looks the same size in any font (calibrated in Readex Pro / IBM Plex on 1080×1920;
landscape frames scale by the short side). Headlines/titles also follow their length: 1–2 strong words ≈ 70, a full
sentence ≈ 48 (caption ≈ 40, sub ≈ 26). That is only the starting point — **decide like a motion designer**: one
punch word can go bigger, a long line smaller; check hierarchy and breathing room on the storyboard stills, then set
`size_scale` or an explicit `size` per text. Never apply one size to everything. Fine-tune with
`"size_scale": 0.85…1.3`. An explicit `"size"` still wins. `captions.py --role caption` does the same for captions.

Lines: ≤ 22 characters per caption line on 9:16, ≤ 35 on 16:9; max 2 lines.
**Exact width before building**: `python text_measure.py "النص" --font "Cairo Bold" --size 56 --width 1080` → px and % of
the frame (Filmora renders 1 em = 1.5 × size × W / 1920 px — measured from screen; the text box is wider). Keep lines ≤ 85 % of the width and
size plates from this number (+ 8–10 % padding).
**9:16 safe area** (TikTok/Reels/Shorts UI): keep text inside x 0.08–0.86 and y 0.12–0.80. Captions y ≈ 0.68–0.74,
hooks y ≈ 0.18–0.28. Nothing important in the bottom 20 % or behind the right-side buttons.
**16:9**: captions y ≈ 0.86, titles inside 5 % margins.

## Animations

- `in`: `fade` (calm), `pop` (friendly, bouncy), `punch` (beat hit, starts big), `rise`, `drop`, `slide_left`,
  `slide_right`, `zoom`, `spin` · `in_duration` default 0.4–0.6 s (punch 0.2).
- `out`: `fade`, `shrink`, `grow` · `out_duration` default 0.35 s.
- `loop`: `pulse` (breathing title), `beat_pulse` with `pulse_period` = 60/BPM (on music), `push` (slow grow),
  `shake` (one shake at the start).
- Custom moves: `"keyframes": {"y": [[0, 0.3], [0.5, 0.25]], "opacity": [[0, 0], [0.2, 100]], "rotation": [...]}`.
- Text effects from the library go in the text's `filters`:
  `python fx_pick.py --on text -n 8` (glow, glitch exit, particle converge/dissipate, colour fill, neon…).
- **Filmora's own presets** (shown in its Animation panel, so the user can swap them later): `anim_in`, `anim_out`,
  `anim_loop` + `_dur` — e.g. `Appearing Verbatim` / `Disappear Verbatim` (letter by letter, good for Arabic),
  `Typewriter Pops Out`, `Fade1`, `Up Dir Insert`, `Wavy Appearance`, `Heartbeat` (loop). Find more:
  `python filmora_text_anim.py search <word>`. Use either a preset or a keyframe `in` for the same moment, not both.

## Captions from subtitles

```
python captions.py subs.srt --spec "Reel.spec.json" --font "Cairo Bold" --size 56 --y 0.72 --max-chars 22 [--in fade]
python captions.py words.json --spec "Reel.spec.json" --karaoke --highlight "#C6FF3D"
```
- Accepts SRT, VTT, or word-level JSON `[{"word","start","end"}]`. Re-running replaces the old captions.
- Splits long cues into balanced pieces (prefers breaking after punctuation), merges pieces under `--min-dur` 0.6 s;
  defaults `--max-chars 22 --max-words 6`. Best results: write SRT cues already phrase-sized.
- Entrance: `--in pop` (default) / `fade` (calm, educational, religious) / `rise` / `punch`; `--out fade` optional.
- Grouping rules worth following when hand-editing: new group at a pause ≥ 0.5 s, sentence end, comma + 0.25 s, or
  6 words / 2.5 s; one group on screen; never animate Arabic letter by letter (whole words / lines only).
- `--offset` shifts all times (e.g. when the voice starts later on the timeline).
- `--karaoke` (needs word JSON): each spoken word pops above the line in the highlight colour.
- Native alternative: spec `"subtitles"` writes ONE editable Filmora subtitle track (and Dynamic Captions with the
  spoken word highlighted from `words`) instead of separate text clips — see filmora-core spec.md.
- No subtitles yet? If `faster-whisper` is installed, transcribe with word timestamps; otherwise ask the user for an
  SRT (Filmora's own Auto Captions can export one). Always show the user the caption text to confirm the wording
  before building — they check it closely.

## Recipes

- **Hook (first 2 s)**: 2–5 words, size 100+, `in: "punch"`, y 0.22, strong colour on one key word (split into two
  text clips side by side or stacked lines with different colours).
- **Kinetic typography**: one word or short phrase per beat/phrase, alternating size (90 / 140) and y position
  (0.42 / 0.55), `in: "punch"` on kicks, `out: "fade"` 0.15 s; keep each word ≥ 0.35 s on screen.
- **Countdown**: three clips «٣ ٢ ١» or "3 2 1" one beat each before the drop, size 160, `in: "punch"`.
- **Lower third**: name (size 56, bold) + role (size 40, regular) stacked at y 0.80 / 0.84 on 16:9, `in: "slide_left"`,
  PNG bar behind them.
- **Quote / ayah / hadith card**: calm only — `in: "fade"` 0.8 s, no shakes or glitch effects, no music.
  Quranic text must be copied exactly from a verified source (with its diacritics), never typed from memory.

## Checks before building

- **Fonts are the user's choice**: render specimens of their installed fonts (`font_scout.py specimen`) and let them pick
  for each project; never reuse a previously *tested* font as if it were chosen.
- Sublines use `below: <headline id>` (never a fixed y offset); colours are contrast-checked by the builder.

- The builder keeps every text inside the frame (7 % side / 3 % top-bottom margin, at its biggest keyframe scale and
  every position — Filmora draws a little wider than measured). A 3+ word line wider than 78 % of the frame (or one that
  would have to shrink) is split into two balanced lines that grow **downward** (top edge stays, `below` sublines follow);
  otherwise the size is reduced. It prints `note: ...` — tell the user; better: shorten the line.

- Every caption inside the safe area; no two captions overlapping on the same row (captions.py trims overlaps).
- Reading time: ≥ 0.6 s for 1–2 words, ≈ 0.25 s per word beyond that.
- Text z above effect layers (otherwise glitch/flash effects also hit the text — sometimes wanted for hits).
- Fonts installed; Arabic text uses an Arabic font.
