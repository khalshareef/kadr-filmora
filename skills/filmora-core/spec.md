# Spec format (build_from_spec.py)

```json
{"name": "Project Name", "width": 1080, "height": 1920, "fps": 30, "clips": [ ... ]}
```
`name` becomes the file name (`Project Name.wfp`). width/height decide the aspect (any of 9:16, 16:9, 1:1, 4:5 …).

## Fields common to every visual clip (video, image, text, effect)

| field | default | meaning |
|---|---|---|
| `type` | — | `video` · `image` · `text` · `effect` · `audio` |
| `start`, `end` | — | timeline seconds |
| `z` | 0 | layer order; higher = on top. Unnamed clips are packed into tracks: clips that don't overlap in time may share a track, so equal z gives no order guarantee — use distinct z when order matters |
| `track` | — | name a lane to keep clips together (required for transitions). Lanes are ordered by their lowest z |
| `x`, `y` | 0.5 | position of the clip centre, 0..1 of the frame (y down) — not for `effect` |
| `scale` | 100 | % ; 100 = fit the frame (video/image) or the measured text box (text) |
| `rotation` | 0 | degrees (video/image) |
| `opacity` | 100 | 0..100 |
| `filters` | [] | list of installed filter/effect names applied to this clip only |
| `keyframes` | {} | `{"scale": [[t, v], ...], "x": ..., "y": ..., "rotation": ..., "opacity": ..., "scale_x": ...}` t = s from clip start |
| `in`, `in_duration` | — | entrance preset: `fade` `pop` `punch` `rise` `drop` `slide_left` `slide_right` `zoom` `spin` |
| `out`, `out_duration` | — | exit preset: `fade` `shrink` `grow` (default 0.35 s) |
| `loop` | — | over the whole clip: `pulse` `beat_pulse` `spin` `push` `shake` (see below) |
| `transition_out` | — | `"Name"` or `{"name": "Name", "duration": 0.4}` — transition into the next clip on the same `track` |
| `ease` | `out` | how every move between keyframes runs: `out` (fast start, soft stop) · `in` · `inout` · `linear` are written as Filmora's own curve keyframes (two editable points per move, shown as Curve in its keyframe editor); `back` (small overshoot) is sampled into short straight steps |

Presets (`in`/`out`/`loop`) merge with explicit `keyframes` per property: all points are combined and sorted, explicit
points at the same time win. Don't combine a `loop` and explicit keyframes on the **same** property (e.g. `pulse` +
scale keyframes) — the points interleave. Different properties combine fine. `scale_x` is image-only, in % like `scale`.

Loop options: `pulse` (gentle breathing; `pulse_period` 1.2 s, `pulse_amount` 0.04), `beat_pulse` (kick every
`pulse_period` s — set it to 60/BPM or a multiple; `pulse_amount` 0.08), `spin` (`spin_degrees` over the clip),
`push` (slow push-in to `push_amount` × scale, Ken-Burns), `shake` (one quick rotation shake at the clip start,
`shake_degrees` 2.5 — put a short clip at each hit).

## Per type

**video** — `path` (absolute), `src_in` (seconds into the source where the clip starts; default 0).
Clip length = end − start, so the source must have `src_in + (end − start) × speed` seconds. Muted on the timeline.
- `speed`: a number 0.1–10 (constant), `{"preset": "montage"}` (montage, hero_moment, bullet_time, jumper, flash_in,
  flash_out, customize, fast_slow_fast, slow_in, slow_out) or `{"curve": [[fraction 0..1, speed], ...]}`. The clip keeps
  its timeline start/end; the source range is solved from the speed (ramps ease smoothly between points like Filmora).
- `reverse: true` (Filmora's Reverse Speed), `frame_interp`: `"sampling"` (default) | `"blending"` | `"optical_flow"`.
  Reversed clips count time from the end of the media (handled automatically — keyframes still use seconds from the clip start).
- Transform/opacity keyframes stay at their timeline positions on sped clips (re-based automatically).

**image** — `path` (png/jpg/webp; PNG with alpha keeps transparency). Stays for start..end.

**mask** (video and image) — `"mask": {"shape": ..., ...}`: shapes `ellipse` (alias circle), `rect` (rounded with
`radius`), `double_line` (a band), `line` (one straight edge), `star`, `heart`, `text` (`text`, `font` = the user's
font), `image` (`image`: white-on-transparent PNG or 1..40 = Filmora's built-in shapes). `x`, `y` = centre and `w`,
`h` = size as fractions of the clip's OWN picture (not the frame; `h` omitted = circle/square); `rotation` degrees,
`feather` 0..1, `invert` (keep the outside), `keyframes`: {x|y|w|h|scale|rotation|feather|radius: [[t, v], ...]}
(seconds from the clip start). One mask per clip.

**text** — real Filmora text, editable later:
`text` (use `\n` for line breaks), `font` (installed, "Family Style", default `Arial`), `role` (`hit` `headline`
`title` `caption` `label` `sub` — the builder picks the size for that font; `size_scale` tunes it) or an explicit
`size`, `color` `"#RRGGBB"`. Alignment is centred.
`id` + `below: "<id>"` (+ optional `gap` px) puts a text under another text's real block (e.g. an English subline
under a 2-line headline). The builder also checks each text's colour against what is really underneath (sampled frame)
and switches to near-white/near-black below 3:1 contrast (spec `"contrast": false` or text `"contrast": false` to opt out).
Outline, shadow and background boxes are not written — use a PNG plate under the text (filmora-design-system) or
tell the user to add them in Filmora.
Filmora's own animation presets: `anim_in`, `anim_out`, `anim_loop` (English or Arabic panel name, e.g.
`"Appearing Verbatim"`, `"Typewriter Pops Out"`, `"Fade1"`, `"Up Dir Insert"`, `"Heartbeat"`) with optional
`anim_in_dur` / `anim_out_dur` / `anim_loop_dur` seconds (in+out are shrunk to fit the clip; a loop repeats to the
end). List them: `python filmora_text_anim.py list in` / `search typewriter`. Presets not downloaded yet are marked
— the user downloads them once in Filmora's Animation panel. They can be combined with `in`/`out` keyframe presets,
but one of each is usually enough.

**effect** — `name` of an installed effect / overlay / filter (slug, English title or Arabic title). Becomes an
adjustment-style effect layer that applies to everything below it during start..end.
`params`: {name: value} (names/ranges: `catalog_filmora.py search <name>`), `keyframes`: {param: [[t, value], ...]}
(seconds from the effect's start), `ease`: linear | ease_in | ease_out | ease_in_out | smooth | back | hold (eases are
baked into short straight steps). Clip `filters` take the same: `"filters": ["Name", {"name": ..., "params": ...,
"keyframes": ..., "ease": ...}]`.

**audio** — `path` (wav/mp3/m4a), `start`, optional `duration` (trim), `gain_db` (default **-10**), `fade_out` (s),
`volume_kf`: [[t, dB], ...] (−100..+20 dB, seconds from the clip start) for fades and dips.
Overlapping audio clips get separate audio tracks automatically.

## Naming effects

Any of: slug (`4_Glitch_Block2`), English title (`Glitch Block 2`), Arabic title. Slugs are unambiguous — prefer
them (fx_pick.py prints slugs). `python catalog_filmora.py search glitch` to look up names.

## Layout recipe (typical reel)

```
z 0   main footage on track "main" (transitions here)
z 2   b-roll / picture-in-picture
z 5   effect layers & overlays (affect z 0-2 only)
z 8   PNG plates behind text
z 10  texts (captions, titles)
audio music (gain -6) + SFX (-10) on their own tracks
```

## Python API (when the spec can't express it)

```python
import sys; sys.path.insert(0, r"<root>/scripts")
from filmora_fx import FxProject
p = FxProject("Name", 1080, 1920, 30)
a = p.video_clip("D:/a.mp4", 0, 3, src_in=1.0, filters=["Old_Movie_2"])
b = p.video_clip("D:/b.mp4", 3, 6, src_in=0.5)
p.transition(a, "Cross_Zoom", 0.4)                       # a must end where b starts, same lane
p.add_lane([a, b])
p.add_lane([p.fx("4_Flash_White1", 2.9, 3.2)])           # lanes added later sit on top
p.add_lane([p.title_clip("Hi", 0.3, 2.8, font="Cairo Bold", font_size=90, text_width=1.2, y=0.8)])
p.add_audio_lane([p.audio_clip("D:/sfx/whoosh.wav", 2.8, gain_db=-10)])
path, end_ticks = p.save("G:/out/Name.wfp")              # then run check_wfp.py and register_project.py
```
`text_width` = width of the text at 1 px font size (get it from `text_measure.measure([(line, font)])[0]`).
Keyframe lists on clips: `kf_scale`, `kf_x`, `kf_y`, `kf_rot`, `kf_opacity` = `[(t, v), ...]`.
