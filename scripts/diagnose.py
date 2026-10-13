"""Explain why Filmora had trouble with a generated project: scans Filmora's newest logs for meaningful errors
(skipping harmless noise), maps known ones to causes/fixes, and re-runs check_wfp on the project.

    python diagnose.py                      # newest log only
    python diagnose.py "My Reel.wfp"        # + integrity check of that project
    python diagnose.py --all --grep relink  # every log in the folder, extra search word
"""
import argparse, glob, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import filmora_paths  # noqa: E402

NOISE = [r"SetEffectChainMaskEnabled first", r"Clip is not missing", r"\[Info\]", r"\[Debug\]", r"\[Trace\]",
         r"Pump(Video|Audio)Frame\(\) waiting", r"FindClipWithTransition", r"get decoder capability failed",
         r"key 'adjustLayer' not found", r"SetCachePath error"]   # seen in perfectly working sessions
KNOWN = [  # regex -> explanation (first match per message wins)
    (r"not found any description file|Get Effect Info failed! path",
     "Filmora couldn't read a description file of that resource. Harmless if the effect shows and renders in the preview; "
     "if it appears as missing, re-download that effect inside Filmora."),
    (r"ErrInvalidTransitionTime|pos_trans overlap",
     "Two transitions overlap: a clip is shorter than the halves of its incoming + outgoing transitions. Shorten the "
     "transitions or lengthen the clip (build_from_spec.py now shrinks them automatically) and rebuild."),
    (r"project not available|unable to open project",
     "Integrity stamps don't match (project_source / timeline key 140). The file was edited after saving or built by an "
     "old script. Rebuild with build_from_spec.py; never hand-edit the .wfp."),
    (r"(file|media).{0,40}(not exist|not found|missing|offline)|relink",
     "A media file moved, was renamed or is on a disconnected drive. Put it back at the same path or rebuild the spec with "
     "the new path (or relink inside Filmora)."),
    (r"(effect|filter|resource|transition).{0,60}(not found|missing|download|placeholder)",
     "An effect isn't installed in this Filmora (e.g. project built on another PC). Download it in Filmora's Effects "
     "panel, or rebuild after `catalog_filmora.py` so only installed effects are used."),
    (r"font.{0,40}(not found|missing|fallback|replace)",
     "A text font isn't installed; Filmora substitutes it. Install the font (then restart Filmora) or change `font`."),
    (r"json|parse|deseriali",
     "The project JSON couldn't be read — usually a template mismatch with this Filmora version. Run "
     "extract_templates.py on a project saved by this Filmora version, then rebuild."),
    (r"version|upgrade|backup",
     "Version/backup notice. The 'Back up project' dialog is harmless (templates come from an older Filmora); fix it "
     "by re-extracting templates from a project saved in the current version."),
    (r"decode|codec|hevc|unsupported",
     "Media codec problem (HEVC/10-bit/VFR phone video). Convert: ffmpeg -i in.mp4 -c:v libx264 -crf 16 -pix_fmt yuv420p "
     "-r 30 -c:a aac out.mp4, then use out.mp4."),
]


def scan(files, extra=None):
    hits = {}
    for f in files:
        for line in open(f, encoding="utf-8", errors="replace"):
            if any(re.search(n, line) for n in NOISE):
                continue
            if not re.search(r"\[(Error|Warn|Fatal)", line) and not (extra and re.search(extra, line, re.I)):
                continue
            msg = re.sub(r"^\[[^\]]*\]\[\d+\]\[[^\]]*\]", "", line.strip())[:240]
            hits[msg] = hits.get(msg, 0) + 1
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?"); ap.add_argument("--all", action="store_true"); ap.add_argument("--grep")
    a = ap.parse_args()
    d = filmora_paths.log_dir()
    if not d or not os.path.isdir(d):
        print("Filmora log folder not found (is Filmora installed for this user?)")
    else:
        logs = sorted(glob.glob(os.path.join(d, "*.log")), key=os.path.getmtime, reverse=True)
        logs = logs if a.all else logs[:2]
        print("logs:", *[os.path.basename(x) for x in logs], sep="\n  ")
        hits = scan(logs, a.grep)
        causes = set()
        for msg, n in sorted(hits.items(), key=lambda kv: -kv[1])[:40]:
            print(f"{n:4}x {msg}")
            causes |= {next((why for rx, why in KNOWN if re.search(rx, msg, re.I)), None)} - {None}
        print("\nlikely causes:" if causes else "\nno known problem patterns in the logs.")
        for c in causes:
            print(" -", c)
    if a.project:
        print("\nintegrity check:")
        subprocess.run([sys.executable, os.path.join(HERE, "check_wfp.py"), a.project])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
