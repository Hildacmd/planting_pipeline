# -*- coding: utf-8 -*-
"""Insert stage notes into the Colab notebooks.

Every note is a markdown cell tagged `"autonote": True` in its metadata and placed immediately
above the code cell whose source contains the note's anchor. Re-running the script strips the
previous notes first, so it is idempotent and safe after editing the code cells.

    python docs_notes/annotate.py            # annotate every notebook that has notes
    python docs_notes/annotate.py 01_planting_window.ipynb
    python docs_notes/annotate.py --check    # report coverage, write nothing
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

NOTES = {}
for mod in ("notes_core", "notes_masks", "notes_runners", "notes_methodology"):
    try:
        NOTES.update(__import__(mod).NOTES)
    except ImportError:
        pass


def md_cell(text):
    lines = text.strip("\n").split("\n")
    src = [l + "\n" for l in lines[:-1]] + [lines[-1]]
    return {"cell_type": "markdown", "metadata": {"autonote": True}, "source": src}


def annotate(path, notes, check=False):
    nb = json.load(open(path))
    cells = [c for c in nb["cells"] if not c.get("metadata", {}).get("autonote")]
    out, used = [], set()
    for c in cells:
        if c["cell_type"] == "code":
            src = "".join(c["source"])
            for i, (anchor, text) in enumerate(notes):
                if i not in used and anchor in src:
                    out.append(md_cell(text))
                    used.add(i)
                    break
        out.append(c)
    missed = [a for i, (a, _) in enumerate(notes) if i not in used]
    name = os.path.relpath(path, ROOT)
    print(f"{name:<52} {len(used)}/{len(notes)} notes placed"
          + (f"  MISSING ANCHORS: {missed}" if missed else ""))
    if not check:
        nb["cells"] = out
        json.dump(nb, open(path, "w"), indent=1, ensure_ascii=False)
        open(path, "a").write("\n")
    return not missed


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check = "--check" in sys.argv
    targets = args or sorted(NOTES)
    ok = True
    for t in targets:
        p = t if os.path.isabs(t) else os.path.join(ROOT, t)
        if not os.path.exists(p):
            print(f"{t:<52} NOT FOUND"); ok = False; continue
        ok &= annotate(p, NOTES[t], check)
    sys.exit(0 if ok else 1)
