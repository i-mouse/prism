"""One-off check: across the saved TEI files, did any <note> lack <s>
children (i.e. would the v1-vs-v2 note-fallback difference have actually
been exercised)? Read-only, uses only the already-saved TEI (no network).
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib

NS = {"tei": "http://www.tei-c.org/ns/1.0"}
TEI_DIR = Path(__file__).resolve().parent / "grobid_tei"

dev_eval = lib.load_dev_eval()
filenames = sorted({f for f, _ in lib.iter_dev_rows(dev_eval)})

total_notes = 0
notes_without_s = 0
notes_without_s_with_multiple_p = 0

for filename in filenames:
    tei_path = TEI_DIR / f"{filename}.tei.xml"
    root = ET.fromstring(tei_path.read_text(encoding="utf-8"))
    text_el = root.find("tei:text", NS)
    notes = text_el.findall(".//tei:note", NS) if text_el is not None else []
    for note in notes:
        total_notes += 1
        s_children = note.findall(".//tei:s", NS)
        if not s_children:
            notes_without_s += 1
            p_children = note.findall("tei:p", NS)
            if len(p_children) > 1:
                notes_without_s_with_multiple_p += 1

print(f"total notes across 12 papers: {total_notes}")
print(f"notes without any <s> child (fallback path triggered): {notes_without_s}")
print(f"of those, notes with >1 <p> child (where v1 vs v2 differ): {notes_without_s_with_multiple_p}")
