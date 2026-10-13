---
name: filmora-troubleshoot
description: Diagnose and fix problems with generated Filmora projects — "Unable to open project", missing media or effects (red/offline clips), audio not on the timeline, wrong aspect ratio, stretched or missing text, transitions that won't apply, "Back up project" dialogs, projects not on the home screen, effects missing on another PC. Reads Filmora's own logs, re-runs the integrity checks and maps errors to fixes. Use whenever the user reports anything wrong after opening a generated .wfp, sends a screenshot of a Filmora error, or says "ما فتح المشروع", "في شي ناقص", "الصوت مش ظاهر", "النص ممطوط", "طلعلي خطأ بفيلمورا", "الإفكت أحمر", "ما بيبين بالقائمة".
---

# Filmora Troubleshoot — find the cause, fix the generator, rebuild

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or two folders above this file).
Never "fix" by driving Filmora's UI and never hand-edit the .wfp (it breaks the integrity stamps): fix the spec or the
scripts, rebuild, and ask the user to reopen. Only small user-side actions (relink, download an effect, restart
Filmora) are suggested as clicks.

## First steps (always)

1. Ask what exactly they see (a screenshot helps most) and which project.
2. `python diagnose.py "<project.wfp>"` — newest Filmora logs (noise filtered), likely causes, and `check_wfp.py`.
   `--all` scans every log, `--grep <word>` adds a search word. Logs live in `filmora_paths.py` → `log_dir`.
3. Match the symptom below, fix, rebuild with `build_from_spec.py`, tell the user what changed.

## Symptom → cause → fix

| symptom | cause | fix |
|---|---|---|
| "Unable to open project" / nothing happens | integrity stamps wrong (file edited after build, old script) — log: `project not available` | rebuild from the spec; `check_wfp.py` must say OK |
| Project not on the home screen | Filmora was open and rewrote its list | restart Filmora, or File ▸ Open Project; `register_project.py <wfp> <frames>` while Filmora is closed |
| Red / offline media, "relink" | media moved/renamed, drive letter changed, file on a network/cloud folder | put files back or rebuild with new paths; keep media local |
| Effect shows as missing / red placeholder | effect not downloaded in this Filmora (project made on another PC) | user downloads it in Filmora (Effects ▸ search name ▸ download) or rebuild after `catalog_filmora.py` |
| Music/SFX not visible on the timeline | audio placed on a video-paired track (old script) | current builder puts free audio on stand-alone audio tracks — rebuild |
| 16:9 project opens as 9:16 (or the reverse) | aspect not set on every timeline | current builder sets all; check spec width/height, rebuild |
| Text stretched / squashed | font missing → measured with another font, or box measured for wrong text | install the font or change `font`; rebuild (Playwright must work: `playwright install chromium`) |
| Text in the wrong font | font name not Filmora's "Family Style" name, or not installed for all users | use the exact name from `text_measure.font_index()`; restart Filmora after installing fonts |
| Transition missing on a cut | clips not touching on the same `track`, no source handles, or clips too short (auto-dropped: builder prints a note) | same track + exact touching times; `src_in` ≥ 0.3; longer clips or shorter transitions |
| Log: `ErrInvalidTransitionTime` / `pos_trans overlap` | two transitions overlapped on a short clip | builder now shrinks them; rebuild |
| Video clip frozen/black at its end | `src_in + duration` beyond the source length | probe the source and adjust `src_in`/`end` |
| Choppy playback | 4K/HEVC/variable-frame-rate phone footage | normal for preview; or convert: `ffmpeg -i in.mp4 -c:v libx264 -crf 16 -pix_fmt yuv420p -r 30 -c:a aac out.mp4` |
| "Back up project?" on **every** open (even backups get backed up) | project stamped with an older Filmora version | builder now stamps the installed version (`filmora_paths.installed_versions()`, read from a project Filmora saved itself) — rebuild. If it still asks: make + save any empty project in Filmora once, then rebuild |
| Keyframes ignored / jumpy | keyframe times outside the clip, or duplicates | times are seconds from clip start, inside 0..duration; builder clamps and merges |
| Wrong layer order | `z` values / effect layer below the footage | higher z = on top; effects need z above what they affect |
| Volume too loud/quiet | builder default -10 dB when no gain is given | set `gain_db` per clip (SFX -13..-14, music -2..-8) |
| Text animation missing / Filmora asks to download | preset is online-only or premium on this account | `filmora_text_anim.py search <name>` shows the source; pick a bundled one or download it once in the Animation panel |
| Light/white edge around transparent motion layers | clip rendered as straight alpha by an older renderer (Filmora reads alpha premultiplied) | re-render with the current `motion_render.py` (premultiplies automatically) |
| Sped-up clip shows the wrong part of the source | `src_in`/speed mix-up; reversed clips play the solved range backwards | check `filmora_speed.describe(clip)`; the source must hold `src_in + duration × speed` |

## Re-extracting templates (new Filmora version, JSON/parse errors, backup dialog)

The builder clones clip/track skeletons from `assets/templates.json`. If a Filmora update changes the format:
1. Ask the user to make one small project **in their current Filmora**: one image (png/jpg), one text, one audio file
   (wav/mp3), one video clip, one transition and one effect; save it and tell you its name.
2. `python extract_templates.py "<that project>.wfp"` (or without arguments to scan their projects folder).
3. Rebuild a test spec, `check_wfp.py`, and ask them to open it.
Personal paths are stripped automatically; keep the old templates.json as a backup before replacing it.

## When Filmora was updated

- Re-run `python catalog_filmora.py` (new/removed effects), then `fx_pick.py --styles` to see untagged ones
  (`note: guess`). Tag important new ones in `assets/fx_tags.json` after viewing their `thumbnail.png`.
- If projects stop opening: diagnose → re-extract templates → rebuild.

## Reporting back

Tell the user in plain words (their language, no jargon): what was wrong, what you changed, and exactly what to do
(e.g. "سكّر فيلمورا وافتحه من جديد، وافتح المشروع من القائمة"). If you couldn't find the cause, ask for a screenshot of
the problem and the newest log file (`diagnose.py` prints its name).
