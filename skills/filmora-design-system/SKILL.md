---
name: filmora-design-system
description: Visual design rules and graphic assets for generated Filmora projects — colour palettes, font pairing for Arabic and English, safe areas per platform, layout grids, and custom motion-graphics elements (text plates, lower-third bars, glowing frames, backgrounds, icons, panels) rendered as crisp transparent PNGs and animated with keyframes. Use whenever an edit needs a consistent look, brand colours, a background, a box behind text, motion graphics, a layout with the speaker small in the centre, or the user says "صمم", "ألوان", "خلفية", "موشن جرافيك", "بوكس ورا النص", "هوية بصرية", "خط", "شكل احترافي". Works with filmora-core and filmora-text.
---

# Filmora Design System — consistent, readable, on-brand

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or two folders above this file).
Prefer native Filmora texts/effects (editable). Render a PNG only for shapes Filmora can't write from a file:
plates/boxes, bars, frames, glows, icons, illustrated panels, gradient backgrounds.

## 1. Pick a palette (max 1 background + 1 text + 1–2 accents)

| name | background | text | accent(s) | fits |
|---|---|---|---|---|
| Dark Lime (tech/AI) | #070B14 → #132036 | #FFFFFF | #C6FF3D, #3DE0FF | explainers, tech, motion pieces |
| Calm Sand (edu/religious) | #F4EFE6 / #1E2A2A | #1E2A2A / #F4EFE6 | #C9A45C | lessons, quotes, Islamic content |
| Cinema Teal-Orange | #0B1416 | #F2F2F2 | #FF8A3D, #2EC4B6 | trailers, travel |
| Neon Party | #0A0614 | #FFFFFF | #FF2E88, #00E5FF, #FFE600 | glitch/party edits |
| Clean Vlog | footage | #FFFFFF | #FFD166 | vlogs, lifestyle |
| Retro VHS | footage | #F5F5DC | #FFDD00, #FF3B3B | retro edits |
| Romantic | footage | #FFFFFF | #F7C6D0, #D4AF37 | weddings, birthdays |

If the user has a brand (logo/colours/fonts), use theirs and ask once for the hex codes or a logo file to sample.
Contrast: text on footage always gets help — a plate (55–65 % black) or a strong colour block behind it.

## 2. Fonts

| use | Arabic | English |
|---|---|---|
| headline / hook | Alexandria Black, Cairo Black, Tajawal ExtraBold | Montserrat Black, Anton, Bebas Neue |
| body / captions | Cairo Bold, Tajawal Bold, IBM Plex Sans Arabic SemiBold | Inter SemiBold, Montserrat Bold |
| elegant / quotes | Amiri, Noto Naskh Arabic, Aref Ruqaa | Playfair Display, Cormorant |
| trailer | Alexandria, Reem Kufi | Cinzel, Bebas Neue |

Max 2 families per video. Only installed fonts work (check with text_measure, see filmora-text).

## 3. Layout & safe areas

- **9:16 (1080×1920)**: platform UI covers the bottom ~20 % and the right ~12 %. Keep text/faces in x 0.08–0.86,
  y 0.12–0.80. Hook zone y 0.15–0.30, caption zone y 0.66–0.76.
- **16:9 (1920×1080)**: title-safe = 5 % margins; lower thirds at y 0.80–0.88, left-aligned blocks at x ≈ 0.25.
- **1:1 / 4:5**: 6 % margins, captions y ≈ 0.82.
- **Speaker small in the centre** (talking head + motion): video `scale` 55–65, y 0.50, rounded frame PNG around it,
  graphics/titles in the bands above (y 0.10–0.28) and below (y 0.72–0.88); background = rendered `bg` PNG.
- Grid: align things to thirds; same margin everywhere; one focal point per moment.

## 4. Render elements (render_png.py)

```
python render_png.py plate --w 900 --h 150 --color "#000000" --opacity 0.55 --radius 36 --out plate.png
python render_png.py bar   --w 700 --h 110 --color "#070B14" --accent "#C6FF3D" --out lower_third.png
python render_png.py bg    --w 1080 --h 1920 --color "#132036" --to "#070B14" --grid --out bg.png
python render_png.py frame --w 700 --h 1240 --color "#C6FF3D" --radius 40 --stroke 8 --out frame.png
python render_png.py glow  --w 600 --h 600 --color "#3DE0FF" --out glow.png
python render_png.py html  my_panel.html --w 1080 --h 1920 --out panel.png     # anything custom (SVG/CSS)
python render_png.py svg   icon.svg --w 300 --h 300 --out icon.png
```
Put PNGs in an `assets/` folder next to the spec (absolute paths in the spec). Rendered at 2× for sharpness.

**Exact placement — easiest**: render the element on a **full-frame canvas** (custom HTML page of W×H with the
element absolutely positioned, transparent elsewhere) → in the spec `scale 100, x 0.5, y 0.5` puts it exactly where
it is in the HTML. Use this for static layouts and panels.

**16:9 explainer layout**: hero image left (x 0.30), supporting icon/visual right (x 0.70), section title y ≈ 0.13,
caption + plate y ≈ 0.87, background `bg` PNG with slow push.

**Element-sized PNG** (for elements you animate, or any third-party PNG — use its pixel size, the formula is a ratio): Filmora fits the image into the frame first, then applies scale:
`scale = 100 × target_width / (w × min(W / w, H / h))` with w, h = the element's size you passed to render_png
(not the 2× pixels) and W, H = project size. Example: 900×150 plate on 1080×1920 → fit = min(1.2, 12.8) = 1.2 →
for 900 px wide on screen: scale = 100 × 900 / (900 × 1.2) = 83.3. Position with x/y (centre).

## 5. Motion for graphics (keyframes)

- Plates/bars enter 0.1 s **before** their text and leave 0.1 s after; `in: "slide_left"` or scale_x wipe:
  `"keyframes": {"scale_x": [[0, 0], [0.25, S]]}` (image-only; S = its scale).
- Frames/panels: `in: "zoom"` 0.5 s, then `loop: "pulse"` (amount 0.02) for life.
- Glows: opacity 0 → 70 → 0 over 1–2 s behind key words; `loop: "pulse"`.
- Backgrounds: `loop: "push"` with push_amount 1.05 over the whole video so it's never static.
- Stagger groups: each element 0.06–0.1 s after the previous one; same easing family everywhere.
- Stamps/badges ("NEW", "✓", numbers): `in: "punch"` + a `hit` effect + a soft click SFX (-14 dB).

## 6. Consistency checklist

- Text is **flat and clean**: one solid colour, no stroke/outline, no glow, no drop shadow (strokes look dated —
  house style). Contrast comes from the palette or a plate behind the text, never from an outline.

- One palette, max two font families, one corner radius, one stroke width across all elements.
- Same entrance style for the same kind of element (all captions pop, all titles rise…).
- Text never touches frame edges; nothing important in platform UI zones.
- Respect the user's footage: soft/flat footage stays soft — graphics carry the style, not heavy grading.
- Religious content: calm palette, no flashy motion, no music/tonal SFX; Quranic text copied exactly from a
  verified source.
