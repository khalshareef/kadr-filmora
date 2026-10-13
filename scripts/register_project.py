"""Add (or refresh) a project in Filmora's home-screen list (ProjectLibarays.xml — Filmora's own spelling).

    python register_project.py "G:/My Projects/Reel.wfp" <duration_in_frames>
    python register_project.py "Reel" <duration_in_frames>        # bare name -> project folder (filmora_paths.py)

Works for projects on any drive. Filmora rewrites this list while it runs: register while Filmora is closed,
or tell the user to restart Filmora. A backup of the list is kept as ProjectLibarays.xml.bak.
"""
import os, sys, time
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import filmora_paths  # noqa: E402


def register(project, frames):
    lib = filmora_paths.library_xml()
    path = os.path.abspath(filmora_paths.resolve_project(project)).replace("\\", "/")
    name = os.path.splitext(os.path.basename(path))[0]
    s = open(lib, encoding="utf-8").read()
    open(lib + ".bak", "w", encoding="utf-8").write(s)
    tag = f"<Path>{escape(path)}</Path>"
    i = s.find(tag)
    if i != -1:                                   # drop the old entry for this path
        a = s.rfind("<Media>", 0, i)
        b = s.find("</Media>", i) + len("</Media>")
        s = s[:a].rstrip(" ") + s[b:].lstrip("\r\n")
    now = int(time.time())
    entry = (f"        <Media>\n            <FileId></FileId>\n            <Type>1</Type>\n            <Name>{escape(name)}</Name>\n"
             f"            {tag}\n            <Thumbnail></Thumbnail>\n            <CreateTime>{now}</CreateTime>\n"
             f"            <ModifyTime>{now}</ModifyTime>\n            <Duration>{int(frames)}</Duration>\n            <Slug></Slug>\n"
             f"            <NewGenerated>false</NewGenerated>\n        </Media>\n")
    k = s.find("<Medias>") + len("<Medias>")
    k = s.find("\n", k) + 1
    s = s[:k] + entry + s[k:]
    open(lib, "w", encoding="utf-8").write(s)
    return path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("registered", register(sys.argv[1], sys.argv[2]))
