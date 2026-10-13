---
name: filmora-core
description: Build native, fully editable Wondershare Filmora 16 projects (.wfp) as files — video/image clips, real Filmora texts, effects, filters, overlays, transitions, music and SFX with keyframes — from a JSON spec, then validate and add them to Filmora's home screen. Use whenever the user wants something made "in Filmora", a Filmora project/timeline/.wfp, an edit they can keep tweaking in Filmora, or says "اعمل مشروع فيلمورا", "سوّيلي مونتاج على فيلمورا", "حطه بفيلمورا", "ملف wfp", "بدي أعدّل عليه بفيلمورا". Entry point of the Kadr for Filmora plugin (kadr-filmora); the other filmora-* skills add text, effects, beat sync, styles, design and troubleshooting.
---

# Filmora Core — spec → .wfp → check → register

You never touch Filmora's interface. You **write the project file**; the user opens it in Filmora and reports back.
No screen clicking, no computer-use, no UI automation of Filmora — ever. If something can't be expressed in the
file, say so and tell the user the 1–2 clicks to do it themselves.

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/` (if that variable is empty: two folders above this SKILL.md).
Call them with `python "<root>/scripts/<name>.py"`. Python 3.10+ and ffmpeg/ffprobe on PATH are required;
install the libraries once: `pip install -r <root>/requirements.txt` then `playwright install chromium`.
On Windows, when *your own* snippets print Arabic, run Python with `-X utf8` (or set `PYTHONIOENCODING=utf-8`);
the plugin scripts already do this. Relative paths work with every script (current folder first).

## Workflow (every project)

1. **First run on a machine** (or the user says «جهّز كادر» / "set up Kadr") — check `python --version` and
   `ffmpeg -version` (missing → tell them: `winget install Python.Python.3.12` / `winget install Gyan.FFmpeg`, then
   reopen the terminal), install the libraries above if `import playwright, fontTools, PIL` fails, then
   build the effect catalog (lists what this Filmora has installed):
   `python catalog_filmora.py` → prints counts per category. Re-run after the user downloads new effects in Filmora.
   `python filmora_paths.py` shows where projects, downloads and logs are.
2. **Plan** the edit: duration, aspect (9:16 reel = 1080×1920, 16:9 = 1920×1080, 1:1 = 1080×1080), fps (30 default,
   match the footage if it's 25/60), sections, what goes on which second. Probe media first:
   `ffprobe -v error -show_entries format=duration -of csv=p=0 "file"`.
3. **Write a spec** (`<name>.spec.json`, next to the output) — format in [spec.md](spec.md). Use the other skills
   for texts (filmora-text), effect choice (filmora-fx-library), beat-synced cuts (filmora-beat-edit) and
   ready-made looks (filmora-edit-styles).
4. **Build**: `python build_from_spec.py "<name>.spec.json"` → writes `<name>.wfp`, runs `check_wfp.py`, and
   registers the project in Filmora's home-screen list. Fix any error it prints before going on.
5. **Hand over** in one short message: full path of the .wfp, length, what's on the timeline, and "open it in
   Filmora (File ▸ Open Project or the home screen) and tell me what you see". Ask for a screenshot if anything
   looks off; then use filmora-troubleshoot.

## Where the project is saved

- Default: the **current working directory** — the folder the Claude Code conversation was opened in, on any drive.
- If the user asks for a permanent folder: `python filmora_paths.py set project_dir "D:/My Filmora"`
  (back to default: `... set project_dir default`). `--out "X:/path/Name.wfp"` on build wins over both.
- Media is referenced by absolute path, not copied. Tell the user not to move/rename the media after building
  (or Filmora will ask to relink). Keep media on a local drive.
- **Footage aspect ≠ project aspect** (e.g. 16:9 clips in a 9:16 reel): `scale 100` means *fit* (black bars).
  Fill scale = `100 × max(W/w, H/h) / min(W/w, H/h)` (16:9 → 9:16 ≈ 316). Options: fill (crop; check subjects stay in
  frame with `x`), or blur-background: the clip at scale 100–130 on top + the same clip (same `src_in`) at fill × 1.08
  with a blur filter (`catalog_filmora.py search blur`) on a lower z. `beat_map.py spec --fit blur|fill|fit` does this.
- **fps**: match the footage (24, 25, 30, 50, 60 — `ffprobe` r_frame_rate); 30 when mixing sources.
- Filmora rewrites its home-screen list while running: if the project doesn't appear, restart Filmora or use
  File ▸ Open Project. Registering while Filmora is closed is cleanest.

## Ground rules

- **Units**: times in seconds (timeline), x/y as 0..1 of the frame (0.5, 0.5 = centre, y grows downward),
  scale in % (100 = fit), rotation in degrees, opacity 0..100. Keyframe times are seconds **from the clip's own start**.
- **Layers**: higher `z` = on top. Effects/overlays as `type: effect` apply to everything **below** them for their
  duration — give them a z above the footage they should affect, below texts they should not.
- **Transitions** need two clips on the **same named track**, the second starting exactly at the first's end, and
  spare source footage (≥ half the transition) beyond each cut. Images always have spare footage; for video set
  `src_in` so there's room before, and don't cut at the very end of the source.
- **Audio**: give every audio clip a `gain_db` (builder default -10 dB). House defaults: SFX taps -14, whooshes -13, one
  hero impact -10 (`sfx_catalog.place()` uses these); music -4 to -8 dB under a voice, -2 to 0 alone.
  Add `fade_out` on the last music clip. A video's own sound is not placed (clips are muted) — add the audio file
  as an `audio` clip if it's needed.
- **Religious / Quranic content**: never add music, jingles or tonal SFX. Only soft, non-flashy visuals
  (fx_pick style `calm`). Ask before adding any sound at all.
- **Fonts**: a font must be installed on the PC (Windows Fonts or user fonts). `text_measure.py` finds fonts by
  Filmora's name, "Family Style" (e.g. `Alexandria Black`, `Cairo Bold`). Arabic needs an Arabic-capable font.
- **Effects** must be installed in this Filmora. `catalog_filmora.py search <word>` finds them; unknown names
  raise a clear error telling the user to download that effect in Filmora first.
- Keep everything editable: prefer real Filmora texts and effects over baked PNG/video, unless a design element
  can't be made in Filmora (then render it — see filmora-design-system).

## Script map

| Script | Use |
|---|---|
| `build_from_spec.py spec.json [--out P] [--no-register]` | spec → .wfp → check → register |
| `catalog_filmora.py` / `search <q>` / `list <category>` | installed effects catalog |
| `fx_pick.py <style...> --use hit -n 4` | choose effects that fit a style (filmora-fx-library) |
| `check_wfp.py <file.wfp>` | re-run Filmora's open-time integrity checks |
| `register_project.py <file.wfp> <frames>` | add an existing .wfp to the home screen |
| `filmora_paths.py [set project_dir <dir>]` | paths & preferences |
| `text_measure.py` | font lookup + text width (used automatically) |
| `extract_templates.py [a.wfp ...]` | rebuild `assets/templates.json` from the user's own projects (troubleshooting) |
| `filmora_wfp.py`, `filmora_fx.py` | Python API if a spec can't express something (see spec.md ▸ Python API) |

## Minimal example

```json
{"name": "Hello Reel", "width": 1080, "height": 1920, "fps": 30,
 "clips": [
  {"type": "video", "path": "D:/clips/a.mp4", "start": 0, "end": 3, "track": "main", "src_in": 1.0,
   "transition_out": {"name": "Cross_Zoom", "duration": 0.4}},
  {"type": "video", "path": "D:/clips/b.mp4", "start": 3, "end": 6, "track": "main", "src_in": 0.5},
  {"type": "effect", "name": "4_Flash_White1", "start": 2.9, "end": 3.2, "z": 5},
  {"type": "text", "text": "أهلا وسهلا", "font": "<font the user picked>", "role": "headline", "y": 0.78,
   "start": 0.3, "end": 2.8, "anim_in": "Appearing Verbatim", "anim_out": "Fade1", "z": 10},
  {"type": "audio", "path": "D:/sfx/whoosh.wav", "start": 2.8}
 ]}
```

## Speed, masks, text animations, animated effect values (all verified in Filmora 16)

- **Speed** on a video clip: `"speed": 2` (constant 0.1–10), `{"preset": "montage"}` (Filmora's ramps: montage,
  hero_moment, bullet_time, jumper, flash_in, flash_out; extra: fast_slow_fast, slow_in, slow_out) or
  `{"curve": [[0, 3], [0.5, 0.4], [1, 3]]}` (fraction of the clip, speed). `start`/`end` stay timeline seconds — the
  builder solves how much source the speed uses. `"reverse": true`, `"frame_interp": "blending"|"optical_flow"`.
- **Mask** on a video/image clip: `"mask": {"shape": "ellipse"|"rect"|"double_line"|"line"|"star"|"heart"|"text"|"image",
  "x", "y", "w", "h", "rotation", "feather", "invert", "radius", "keyframes": {"scale": [[0, 0.3], [1.5, 1]]}}` —
  x/y/w/h are fractions of the clip's own picture, not of the frame.
- **Text animation presets** (Filmora's own, ~150 bundled): `"anim_in"`, `"anim_out"`, `"anim_loop"` + `_dur` in
  seconds. `python filmora_text_anim.py list in|out|loop` / `search <word>`; many carry Filmora's premium mark.
- **Effect values over time**: on an effect layer `"params": {...}`, `"keyframes": {"Blur": [[0, 0], [1.2, 100]]}`,
  `"ease"`; on a clip filter `{"name": ..., "params": ..., "keyframes": ...}`; audio `"volume_kf": [[0, -60], [1.5, -14]]`.
Details and every field: [spec.md](spec.md).

## Also in files (verified in Filmora 16)

Blend modes (`blend`), several masks per clip (`masks`), AI Portrait Cutout (`cutout`, computed by Filmora, no
credits), native shapes and self-drawing lines (`type: shape`), split screens on the main timeline (`type: split`),
motion tracking (`follow`), Filmora's own curve keyframes (`ease`), native subtitle track + Dynamic Captions
(`subtitles`, from our own word timings). Fields: [spec.md](spec.md).

## Limits (be honest with the user)

Filmora features that need its paid AI credits (speech-to-text, AI captions, AI voice/music/image tools) are left to
the user. Captions come from our own transcription instead (filmora-text).
