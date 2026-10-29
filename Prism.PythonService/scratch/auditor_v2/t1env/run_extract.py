"""Auditor v2 T1 extractor driver. The ONLY file that imports docling / pymupdf4llm / pymupdf.

Subcommands (run with the t1env interpreter, e.g.
`uv run --project <t1env> --no-sync python -I run_extract.py <cmd> ...`):

  versions                         record exact versions + settings -> scratch/auditor_v2/t1_versions.json
  check-labels --pins P [--apply]  pre-run pin label check against PDF text (prints yes/no only)
  extract --extractor E --run R    run one extractor on the 12 dev PDFs -> out/E/R/raw/ + runtimes.json
  normalise --extractor E --run R  raw -> common schema -> out/E/R/normalised/
  diff --extractor E               byte-compare normalised run_a vs run_b

Settings are fixed in SETTINGS below (decisions.md 2026-10-28 "T1 - Settings" + Nitin's answers
2026-10-29: Docling accelerator CPU, CPU torch; pymupdf4llm's own output only).

Rules written down BEFORE the first run (identical for run_a and run_b):

pymupdf4llm tables (own output only: to_json(..., table_output="html", use_ocr=False)):
  * each entry of box.table["html_tables"] is one table, in the order pymupdf4llm emits boxes/pages.
    A table box with no html_tables falls back to its own `extract` text matrix (1x1 cells, no header flags).
  * HTML parsed for rowspan/colspan. Header rows = leading run of rows whose cells are all <th>, minus
    trailing rows that are a single full-width <th> (those are section rows) when more than one row is in
    the run. A single full-width <th> row below the header run is a section row. pymupdf4llm gives no
    row-header flag, so is_row_header is false everywhere.
  * caption: among non-table boxes on the same page whose text starts "Table N" or "Tab. N" followed
    by one of  : . |  (so prose such as "Table 3 lists ..." is not a caption), with horizontal overlap with the
    table bbox, pick the nearest one above (gap = table.y0 - box.y1) or below (gap = box.y0 - table.y1);
    tie -> above. No candidate -> caption null.
  * footnotes: boxes of boxclass "footnote" on the same page with  table.y1 - 2 <= box.y0 <= table.y1 + 60
    and horizontal overlap with the table.
Docling: caption_text(doc), footnotes via TableItem.footnotes, page via prov[0].page_no, cells from
  TableItem.data.table_cells with its own column_header / row_header / row_section flags.
Both: cell text = whitespace-collapsed; cells sorted by (row, col); no bboxes/timings in normalised files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent            # .../Prism.PythonService/scratch/auditor_v2/t1env
AUD = HERE.parent                                  # .../scratch/auditor_v2
PYSVC = HERE.parents[2]                            # .../Prism.PythonService
ROOT = HERE.parents[3]                             # repo root
PDF_DIR = ROOT / "docs" / "research_papers"
OUT = AUD / "out"
VERSIONS_FILE = AUD / "t1_versions.json"
DEFAULT_PINS = ROOT / "docs" / "evals" / "auditor_rd" / "t1_pins_2026-10-28.json"

PAPERS = {
    "P1": "2610.11519v1", "P2": "2610.11132v1", "P3": "2610.11135v1", "P4": "2610.10871v1",
    "P5": "2610.11291v1", "P6": "2610.11312v1", "P7": "2610.10590v1", "P8": "2610.12124v1",
    "P9": "2610.12375v1", "P10": "2610.12176v1", "P11": "2610.12114v1", "P12": "2610.12168v1",
}
EXTRACTORS = ("pymupdf4llm", "docling")
SCHEMA_VERSION = 1

SETTINGS = {
    "docling": {
        "pipeline_options": (
            "PdfPipelineOptions(do_ocr=False, do_table_structure=True, "
            "table_structure_options=TableStructureOptions(do_cell_matching=True, mode=TableFormerMode.ACCURATE), "
            "accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU))"
        ),
        "converter": "DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=<above>)})",
        "call": "converter.convert(str(pdf)).document",
        "tables": "doc.tables -> TableItem.data.table_cells; caption_text(doc); footnotes[*].resolve(doc).text; prov[0].page_no",
        "accelerator": "cpu (fixed; recorded setting, not a quality setting)",
        "num_threads": "library default (4)",
        "torch_build": "CPU-only (download.pytorch.org/whl/cpu)",
        "ocr": "off",
        "table_model": "TableFormer V1, ACCURATE (library default mode)",
    },
    "pymupdf4llm": {
        "call": "pymupdf4llm.to_json(str(pdf), table_output='html', use_ocr=False)",
        "layout": "on (pymupdf4llm imports pymupdf.layout by default; use_layout(True))",
        "tables": "box.table['html_tables'][*]['html'] parsed for rowspan/colspan; own header (<th>) tagging",
        "ocr": "off (use_ocr=False)",
        "caption_rule": "nearest 'Table N'/'Tab. N' + one of : . | text box above/below on same page, horizontal overlap, tie -> above",
        "footnote_rule": "boxclass footnote on same page, table.y1-2 <= y0 <= table.y1+60, horizontal overlap",
    },
}

_KEEP_PKGS = [
    "docling", "docling-slim", "docling-core", "docling-ibm-models", "docling-parse",
    "pymupdf4llm", "pymupdf", "pymupdf-layout", "onnxruntime", "torch", "torchvision",
]


def _keys():
    """Shared label/caption helpers (stdlib-only module of the product repo)."""
    if str(PYSVC) not in sys.path:
        sys.path.insert(0, str(PYSVC))
    from eval.auditor_v2 import table_keys
    return table_keys


def _ver(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not installed"


def _dump(path: Path, obj, sort_keys: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(obj, sort_keys=sort_keys, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def _collapse(s) -> str:
    return " ".join((s or "").split())


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _hf_home() -> Path:
    return HERE / "models"


# -------------------------------------------------------------------- versions

def tool_version_string(extractor: str, pk: dict) -> str:
    if extractor == "pymupdf4llm":
        return (
            f"pymupdf4llm (code inside pymupdf {pk['pymupdf']}; pymupdf4llm {pk['pymupdf4llm']} shim; "
            f"pymupdf-layout {pk['pymupdf-layout']}; onnxruntime {pk['onnxruntime']})"
        )
    return (
        f"docling {pk['docling']} (docling-core {pk['docling-core']}; docling-ibm-models "
        f"{pk['docling-ibm-models']}; docling-parse {pk['docling-parse']}; torch {pk['torch']})"
    )


def cmd_versions(args) -> int:
    pk = {n: _ver(n) for n in _KEEP_PKGS}
    doc = {
        "recorded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": pk,
        "tools": {e: tool_version_string(e, pk) for e in EXTRACTORS},
        "settings": SETTINGS,
        "product_reader": "PyMuPDF 1.26.7 (product venv, unchanged, not used by T1)",
        "hf_home": str(_hf_home()),
        "note": "pymupdf4llm 2.0 on PyPI is an empty shim; the 4llm code ships inside pymupdf 2.0 (tested as pymupdf 2.0, not 1.28.x).",
    }
    _dump(VERSIONS_FILE, doc)
    print(json.dumps({"packages": pk, "python": sys.version.split()[0], "platform": doc["platform"]}, indent=2))
    return 0


def _load_versions() -> dict:
    if not VERSIONS_FILE.exists():
        raise SystemExit(f"missing {VERSIONS_FILE}; run `versions` first")
    return json.loads(VERSIONS_FILE.read_text(encoding="utf-8"))


# -------------------------------------------------------------------- extract

def _dir_mb(p: Path) -> float:
    total = 0
    for f in p.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass
    return round(total / (1 << 20), 1)


def _extract_docling(pdf: Path, converter) -> dict:
    doc = converter.convert(str(pdf)).document
    tables = []
    for item in doc.tables:
        foot = []
        for ref in item.footnotes:
            try:
                foot.append(_collapse(ref.resolve(doc).text))
            except Exception as exc:  # recorded, not hidden
                foot.append(f"<unresolved footnote: {type(exc).__name__}>")
        tables.append({
            "page": item.prov[0].page_no if item.prov else None,
            "caption": _collapse(item.caption_text(doc)),
            "footnotes": foot,
            "num_rows": item.data.num_rows,
            "num_cols": item.data.num_cols,
            "cells": [
                {
                    "row": c.start_row_offset_idx, "col": c.start_col_offset_idx,
                    "row_span": c.row_span, "col_span": c.col_span, "text": c.text,
                    "column_header": bool(c.column_header), "row_header": bool(c.row_header),
                    "row_section": bool(c.row_section),
                }
                for c in item.data.table_cells
            ],
        })
    return {"tables": tables}


def _box_text(box: dict) -> str:
    parts = []
    for line in box.get("textlines") or []:
        for span in line.get("spans") or []:
            parts.append(span.get("text", ""))
    return _collapse(" ".join(parts))


def _extract_pymupdf4llm(pdf: Path) -> dict:
    import pymupdf4llm
    data = json.loads(pymupdf4llm.to_json(str(pdf), table_output="html", use_ocr=False))
    pages = []
    for page in data["pages"]:
        boxes = []
        for box in page["boxes"]:
            entry = {"boxclass": box["boxclass"], "bbox": [box["x0"], box["y0"], box["x1"], box["y1"]]}
            if box["boxclass"] == "table":
                tbl = box.get("table") or {}
                items = tbl.get("html_tables")
                if items:
                    entry["tables"] = [{"bbox": it["bbox"], "html": it["html"], "extract": it.get("extract")} for it in items]
                else:
                    entry["tables"] = [{"bbox": tbl.get("bbox") or entry["bbox"], "html": None, "extract": tbl.get("extract")}]
            else:
                entry["text"] = _box_text(box)
            boxes.append(entry)
        pages.append({"page": page["page_number"], "boxes": boxes})
    return {"pages": pages}


def cmd_extract(args) -> int:
    e, run = args.extractor, args.run
    os.environ.setdefault("HF_HOME", str(_hf_home()))
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    out = OUT / e / run
    runtimes = {"extractor": e, "run": run, "papers": {}}
    t0 = time.perf_counter()
    converter = None
    if e == "docling":
        from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode, TableStructureOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        opts = PdfPipelineOptions(
            do_ocr=False,
            do_table_structure=True,
            table_structure_options=TableStructureOptions(do_cell_matching=True, mode=TableFormerMode.ACCURATE),
            accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU),
        )
        converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
    runtimes["init_seconds"] = round(time.perf_counter() - t0, 3)
    for paper_id in sorted(set(PAPERS.values())):
        pdf = PDF_DIR / f"{paper_id}.pdf"
        t1 = time.perf_counter()
        raw = _extract_docling(pdf, converter) if e == "docling" else _extract_pymupdf4llm(pdf)
        runtimes["papers"][paper_id] = round(time.perf_counter() - t1, 3)
        raw["pdf_sha256"] = _sha256(pdf)
        _dump(out / "raw" / f"{paper_id}.json", raw)
        print(f"{e} {run} {paper_id} {runtimes['papers'][paper_id]}s", flush=True)
    runtimes["total_seconds"] = round(sum(runtimes["papers"].values()) + runtimes["init_seconds"], 3)
    hub = _hf_home() / "hub"
    runtimes["hf_cache_mb"] = _dir_mb(hub) if hub.exists() else 0.0
    _dump(out / "runtimes.json", runtimes)
    return 0


# ------------------------------------------------------------------ normalise

class _TableHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self._row, self._cell = [], None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tr":
            self._row = []
            self.rows.append(self._row)
        elif tag in ("td", "th"):
            self._cell = {"tag": tag, "rs": int(a.get("rowspan") or 1), "cs": int(a.get("colspan") or 1), "parts": []}
        elif tag == "br" and self._cell is not None:
            self._cell["parts"].append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._cell["text"] = _collapse("".join(self._cell.pop("parts")))
            self._row.append(self._cell)
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["parts"].append(data)


def _cells_from_html(html: str):
    parser = _TableHTML()
    parser.feed(html)
    occupied, cells, n_cols = set(), [], 0
    for ri, row in enumerate(parser.rows):
        ci = 0
        for cell in row:
            while (ri, ci) in occupied:
                ci += 1
            for dr in range(cell["rs"]):
                for dc in range(cell["cs"]):
                    occupied.add((ri + dr, ci + dc))
            cells.append({"row": ri, "col": ci, "row_span": cell["rs"], "col_span": cell["cs"],
                          "text": cell["text"], "tag": cell["tag"]})
            ci += cell["cs"]
            n_cols = max(n_cols, ci)
    return cells, len(parser.rows), n_cols


def _flag_html_cells(cells, n_rows, n_cols):
    by_row = {}
    for c in cells:
        by_row.setdefault(c["row"], []).append(c)

    def all_th(r):
        row = by_row.get(r, [])
        return bool(row) and all(c["tag"] == "th" for c in row)

    def full_th(r):
        row = by_row.get(r, [])
        return len(row) == 1 and row[0]["tag"] == "th" and row[0]["col_span"] == n_cols and n_cols >= 2

    h = 0
    while h < n_rows and all_th(h):
        h += 1
    while h > 1 and full_th(h - 1):
        h -= 1
    out = []
    for c in sorted(cells, key=lambda c: (c["row"], c["col"])):
        out.append({
            "row": c["row"], "col": c["col"], "row_span": c["row_span"], "col_span": c["col_span"],
            "text": c["text"], "is_column_header": c["row"] < h, "is_row_header": False,
            "is_section_row": c["row"] >= h and full_th(c["row"]),
        })
    return out


def _overlap_x(a, b) -> bool:
    return a[0] < b[2] and a[2] > b[0]


_CAPTION_START = re.compile(r"^\s*(?:Table|Tab\.)\s*\d+\s*[:.|]", re.IGNORECASE)


def _pymupdf_caption_and_footnotes(page: dict, tbbox) -> tuple:
    best, best_key = None, None
    foot = []
    for box in page["boxes"]:
        if box["boxclass"] == "table":
            continue
        text, bb = box.get("text", ""), box["bbox"]
        if not _overlap_x(bb, tbbox):
            continue
        if _CAPTION_START.match(text):
            if bb[3] <= tbbox[1] + 2:
                key = (tbbox[1] - bb[3], 0)
            elif bb[1] >= tbbox[3] - 2:
                key = (bb[1] - tbbox[3], 1)
            else:
                continue
            if best_key is None or key < best_key:
                best, best_key = text, key
        if box["boxclass"] == "footnote" and tbbox[3] - 2 <= bb[1] <= tbbox[3] + 60 and text:
            foot.append((bb[1], text))
    return best or "", [t for _, t in sorted(foot)]


def _normalise_pymupdf(raw: dict) -> list:
    tk = _keys()
    tables = []
    for page in raw["pages"]:
        for box in page["boxes"]:
            if box["boxclass"] != "table":
                continue
            for t in box["tables"]:
                if t["html"]:
                    cells, n_rows, n_cols = _cells_from_html(t["html"])
                    cells = _flag_html_cells(cells, n_rows, n_cols)
                else:
                    matrix = t["extract"] or []
                    cells = [
                        {"row": r, "col": c, "row_span": 1, "col_span": 1, "text": _collapse(v),
                         "is_column_header": False, "is_row_header": False, "is_section_row": False}
                        for r, row in enumerate(matrix) for c, v in enumerate(row) if v is not None
                    ]
                    n_rows, n_cols = len(matrix), max((len(r) for r in matrix), default=0)
                caption, foot = _pymupdf_caption_and_footnotes(page, t["bbox"])
                tables.append(_finish(tk, len(tables), page["page"], caption, foot, n_rows, n_cols, cells))
    return tables


def _normalise_docling(raw: dict) -> list:
    tk = _keys()
    tables = []
    for t in raw["tables"]:
        cells = sorted(
            ({
                "row": c["row"], "col": c["col"], "row_span": c["row_span"], "col_span": c["col_span"],
                "text": _collapse(c["text"]), "is_column_header": c["column_header"],
                "is_row_header": c["row_header"], "is_section_row": c["row_section"],
            } for c in t["cells"]),
            key=lambda c: (c["row"], c["col"]),
        )
        tables.append(_finish(tk, len(tables), t["page"], t["caption"], t["footnotes"], t["num_rows"], t["num_cols"], cells))
    return tables


def _finish(tk, index, page, caption, footnotes, n_rows, n_cols, cells) -> dict:
    table = {
        "table_index": index, "page": page, "caption_text": caption,
        "caption_number": tk.caption_number(caption), "footnotes": footnotes,
        "n_rows": n_rows, "n_cols": n_cols, "cells": cells,
    }
    return tk.table_with_keys(table)


def cmd_normalise(args) -> int:
    e, run = args.extractor, args.run
    versions = _load_versions()
    base = OUT / e / run
    for paper_id in sorted(set(PAPERS.values())):
        raw = json.loads((base / "raw" / f"{paper_id}.json").read_text(encoding="utf-8"))
        tables = _normalise_docling(raw) if e == "docling" else _normalise_pymupdf(raw)
        _dump(base / "normalised" / f"{paper_id}.json", {
            "schema_version": SCHEMA_VERSION, "paper": paper_id, "pdf_sha256": raw["pdf_sha256"],
            "extractor": e, "version": versions["tools"][e], "settings": SETTINGS[e], "tables": tables,
        })
        print(f"normalised {e} {run} {paper_id}: {len(tables)} tables")
    return 0


def cmd_diff(args) -> int:
    if str(PYSVC) not in sys.path:
        sys.path.insert(0, str(PYSVC))
    from eval.auditor_v2.t1_score import first_diffs
    e = args.extractor
    bad = 0
    for paper_id in sorted(set(PAPERS.values())):
        a = OUT / e / "run_a" / "normalised" / f"{paper_id}.json"
        b = OUT / e / "run_b" / "normalised" / f"{paper_id}.json"
        if a.read_bytes() == b.read_bytes():
            print(f"{paper_id}: identical")
            continue
        bad += 1
        d = first_diffs(json.loads(a.read_text(encoding="utf-8")), json.loads(b.read_text(encoding="utf-8")))
        print(f"{paper_id}: DIFFERENT {d}")
    print(f"{e}: {'identical' if not bad else str(bad) + ' papers differ'}")
    return 0 if not bad else 1


# --------------------------------------------------------------- check-labels

_GLYPH_RULES = [  # (ascii token, replacement variants)
    ("delta", ["Δ", "∆"]),
    ("lambda", ["λ"]),
    ("+-", ["±"]),
    ("->", ["→"]),
    ("<-", ["←"]),
]


def _variants(label: str) -> list:
    """All labels obtained by replacing, per token type present, every occurrence with one variant
    (or leaving the token). The unchanged label is excluded."""
    results = [label]
    for token, repl in _GLYPH_RULES:
        nxt = []
        for cur in results:
            nxt.append(cur)
            if re.search(re.escape(token), cur, re.IGNORECASE):
                for r in repl:
                    nxt.append(re.sub(re.escape(token), r, cur, flags=re.IGNORECASE))
        results = nxt
    return [v for v in dict.fromkeys(results) if v != label]


def _pin_labels(pin: dict) -> list:
    """(role, label) pairs for the label strings a pin relies on. Values are not labels."""
    out = []
    for role in ("row_key_path", "column_key_path"):
        out += [(role, x) for x in pin.get(role) or []]
    for k, v in (pin.get("match") or {}).items():
        out.append(("match:" + k, v))
    for key in ("names", "fragments"):
        out += [(key, x) for x in pin.get(key) or []]
    if pin.get("contains") and pin["kind"] != "label_absent":
        out.append(("contains", pin["contains"]))
    out += [("group", g) for g in (pin.get("groups") or {})]
    return out


def _replace_label(pin: dict, old: str, new: str) -> None:
    for role in ("row_key_path", "column_key_path", "names", "fragments"):
        if pin.get(role):
            pin[role] = [new if x == old else x for x in pin[role]]
    if pin.get("match"):
        pin["match"] = {k: (new if v == old else v) for k, v in pin["match"].items()}
    if pin.get("groups"):
        pin["groups"] = {(new if g == old else g): n for g, n in pin["groups"].items()}
    if pin.get("contains") == old:
        pin["contains"] = new


def cmd_check_labels(args) -> int:
    import pymupdf  # PDF text only; nothing from the PDFs is printed
    tk = _keys()
    path = Path(args.pins)
    doc = json.loads(path.read_text(encoding="utf-8"))
    roles = {t["table_id"]: t for t in doc["tables"]}
    texts = {}

    def pdf_text(paper_id: str) -> str:
        if paper_id not in texts:
            with pymupdf.open(PDF_DIR / f"{paper_id}.pdf") as pdf:
                texts[paper_id] = tk.normalize_label(" ".join(p.get_text("text") for p in pdf))
        return texts[paper_id]

    stops, fixes = [], []
    for pin in doc["pins"]:
        t = roles[pin["table_id"]]
        gated = t["role"] == "gate" and (pin["breaking"] or not pin["key_uncertain"])
        text = pdf_text(t["paper_id"])
        for role, label in _pin_labels(pin):
            norm = tk.normalize_label(label)
            if norm in text:
                status = "yes"
            elif tk.strip_markers(norm) and tk.strip_markers(norm) in text:
                status = "yes (marker rule)"
            else:
                found = [v for v in _variants(label) if tk.normalize_label(v) in text]
                if len(found) == 1:
                    status = f"variant {'+'.join('U+%04X' % ord(ch) for ch in found[0] if ord(ch) > 127)}"
                    fixes.append((pin, label, found[0]))
                elif not found:
                    status = "NO (no variant present)"
                    if gated:
                        stops.append(pin["id"])
                else:
                    status = f"NO ({len(found)} variants present)"
                    if gated:
                        stops.append(pin["id"])
            print(f"{pin['id']:<12} {'gated' if gated else 'report'} {role:<16} {ascii(label):<40} {status}")
    if stops:
        print("STOP: gated pins with an absent or ambiguous label: " + ", ".join(sorted(set(stops))))
        return 2
    if args.apply:
        for pin, old, new in fixes:
            _replace_label(pin, old, new)
            entry = {"pin_id": pin["id"], "old": old, "new": new}
            doc.setdefault("pdf_glyph_fix", []).append(entry)
            pin.setdefault("pdf_glyph_fix", []).append({"old": old, "new": new})
        _dump(path, doc, sort_keys=False)
        print(f"applied {len(fixes)} glyph fixes; logged under pdf_glyph_fix")
    else:
        print(f"{len(fixes)} glyph fixes would be applied (dry run)")
    return 0


# ----------------------------------------------------------------------- main

def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("versions").set_defaults(fn=cmd_versions)
    p = sub.add_parser("check-labels")
    p.add_argument("--pins", default=str(DEFAULT_PINS))
    p.add_argument("--apply", action="store_true")
    p.set_defaults(fn=cmd_check_labels)
    for name, fn in (("extract", cmd_extract), ("normalise", cmd_normalise)):
        p = sub.add_parser(name)
        p.add_argument("--extractor", required=True, choices=EXTRACTORS)
        p.add_argument("--run", required=True, choices=("run_a", "run_b"))
        p.set_defaults(fn=fn)
    p = sub.add_parser("diff")
    p.add_argument("--extractor", required=True, choices=EXTRACTORS)
    p.set_defaults(fn=cmd_diff)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
