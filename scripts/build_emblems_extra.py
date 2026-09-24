"""
Rebuild assets/emblems_extra.js from the source art in "Faction Icons/".

assets/emblems.js (the original 25 MB emblem file) is left alone; this file adds the emblems for factions that
had none and is loaded after it. To add another faction: drop its image in "Faction Icons/", add it to MAP below
and re-run.  DDS sources are converted by Pillow.

Run from the repo root:   python scripts/build_emblems_extra.py
"""
import base64, io, os, sys
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SRC = os.path.join(ROOT, "Faction Icons")
OUT = os.path.join(ROOT, "assets", "emblems_extra.js")

# faction id (as in campaign.json) -> source file in "Faction Icons/"
MAP = {
    "Khand": "kand.png", "Rhudaur": "rhaudar.png", "Rachrohir": "rachrohir.png", "Khazad-dum": "khazdum.png",
    "Iron Hills": "iron hils.png", "Gundabad": "gundabad.png", "Ered Mithrin": "ered mithrin.png", "Ered Luin": "ered lui.png",
    "Haerrim": "haerrim.png", "Feredrim": "ferederim.png", "Drudain": "druidain.png",
    "Northern Endwaith": "N Endwaith.dds", "Southern Endwaith": "S Endwaith.png", "Harondor": "harondor.dds",
}

lines = ['"use strict";',
         "/* Emblems added after the original emblems.js was generated (source: Faction Icons/). Resized to 128x128 PNG. */"]
entries, total = [], 0
for i, (fid, fn) in enumerate(MAP.items()):
    im = Image.open(os.path.join(SRC, fn)).convert("RGBA").resize((128, 128), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    raw = buf.getvalue()
    total += len(raw)
    var = "_EMBX_%d" % i
    lines.append('const %s="data:image/png;base64,%s";' % (var, base64.b64encode(raw).decode("ascii")))
    entries.append((fid, var))
    print("%-18s <- %-16s %5.1f KB" % (fid, fn, len(raw) / 1024))
lines.append("Object.assign(EMBLEMS,{")
for fid, var in entries:
    lines.append('  "%s":%s,' % (fid, var))
    if fid.lower() != fid:
        lines.append('  "%s":%s,' % (fid.lower(), var))
lines.append("});")
with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(lines) + "\n")
print("total png %.0f KB -> %s %.0f KB" % (total / 1024, os.path.relpath(OUT, ROOT), os.path.getsize(OUT) / 1024))
