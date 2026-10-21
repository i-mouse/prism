"""Experiment 3 pre-check D, candidate 1: GROBID sentences.

POSTs each of the 12 dev PDFs to a LOCAL GROBID instance
(http://localhost:8070, started by the user; no docker commands run here)
at /api/processFulltextDocument with segmentSentences=1, parses the
returned TEI XML, and classifies the 119 dev rows the same way Check A did
(classify() imported from check_a.py, WHOLE/SPLIT/MERGED/NOT_FOUND
unchanged) against normalize_for_match-normalised segments.

Segments are collected from four sources, counted separately:
  - abstract: every <s> under teiHeader/profileDesc/abstract
  - body: every <s> under text/body, excluding any <s> that is also inside
    a <note> or a <figure> (counted once, under note/caption instead)
  - caption: per <figure>, its <figDesc> text, <head> text, <label> text -
    each a separate segment if present and non-empty
  - note: per <note> (footnotes), its <s> children if any, else the
    note's own text as one segment (fallback requested for notes only)

No LLM calls - GROBID is a local, user-started extraction service, not an
LLM. No splitter/window tuning against dev rows.
"""
import importlib.metadata
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib
from check_a import classify

import requests

GROBID_URL = "http://localhost:8070/api/processFulltextDocument"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def local_text(el) -> str:
    return "".join(el.itertext()).strip()


def parse_tei(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    text_el = root.find("tei:text", NS)
    header_el = root.find("tei:teiHeader", NS)

    abstract_sents: list[str] = []
    if header_el is not None:
        abstract_el = header_el.find(".//tei:profileDesc/tei:abstract", NS)
        if abstract_el is not None:
            abstract_sents = [local_text(s) for s in abstract_el.findall(".//tei:s", NS) if local_text(s)]

    note_elems = text_el.findall(".//tei:note", NS) if text_el is not None else []
    note_sents: list[str] = []
    note_s_ids: set[int] = set()
    for note in note_elems:
        s_children = note.findall(".//tei:s", NS)
        if s_children:
            for s in s_children:
                note_s_ids.add(id(s))
                txt = local_text(s)
                if txt:
                    note_sents.append(txt)
        else:
            txt = local_text(note)
            if txt:
                note_sents.append(txt)

    figure_elems = text_el.findall(".//tei:figure", NS) if text_el is not None else []
    figure_s_ids: set[int] = set()
    caption_sents: list[str] = []
    for fig in figure_elems:
        for s in fig.findall(".//tei:s", NS):
            figure_s_ids.add(id(s))
        for tag in ("tei:figDesc", "tei:head", "tei:label"):
            el = fig.find(tag, NS)
            if el is not None:
                txt = local_text(el)
                if txt:
                    caption_sents.append(txt)

    body_sents: list[str] = []
    body_el = text_el.find("tei:body", NS) if text_el is not None else None
    if body_el is not None:
        for s in body_el.findall(".//tei:s", NS):
            if id(s) in note_s_ids or id(s) in figure_s_ids:
                continue
            txt = local_text(s)
            if txt:
                body_sents.append(txt)

    return {
        "abstract": abstract_sents,
        "body": body_sents,
        "caption": caption_sents,
        "note": note_sents,
    }


def main():
    print(f"requests version: {importlib.metadata.version('requests')}")

    dev_eval = lib.load_dev_eval()
    rows = list(lib.iter_dev_rows(dev_eval))
    filenames = sorted({f for f, _ in rows})
    assert len(filenames) == 12, f"expected 12 dev papers, got {len(filenames)}"

    source_counts: dict[str, dict] = {}
    combined_cache: dict[str, list[tuple[str, str]]] = {}
    runtime: dict[str, float] = {}

    for filename in filenames:
        pdf_path = lib.PDF_DIR / filename
        t0 = time.perf_counter()
        with open(pdf_path, "rb") as f:
            resp = requests.post(
                GROBID_URL,
                files={"input": (filename, f, "application/pdf")},
                data={"segmentSentences": "1"},
                timeout=300,
            )
        elapsed = time.perf_counter() - t0
        runtime[filename] = elapsed
        resp.raise_for_status()
        parsed = parse_tei(resp.text)
        source_counts[filename] = {k: len(v) for k, v in parsed.items()}
        combined = (
            [("abstract", s) for s in parsed["abstract"]]
            + [("body", s) for s in parsed["body"]]
            + [("caption", s) for s in parsed["caption"]]
            + [("note", s) for s in parsed["note"]]
        )
        combined_cache[filename] = combined
        print(f"{filename}: runtime={elapsed:.1f}s "
              f"abstract={len(parsed['abstract'])} body={len(parsed['body'])} "
              f"caption={len(parsed['caption'])} note={len(parsed['note'])} "
              f"total={len(combined)}")

    refusal_labels = {"not_supported", "partially_supported"}
    counts = {"WHOLE": 0, "SPLIT": 0, "MERGED": 0, "NOT_FOUND": 0}
    refusal_counts = {"WHOLE": 0, "SPLIT": 0, "MERGED": 0, "NOT_FOUND": 0}
    non_whole_detail = []
    n_refusal = 0

    for filename, row in rows:
        combined = combined_cache[filename]
        seg_norms = [lib.normalize_for_match(s) for _, s in combined]
        claim_norm = lib.normalize_for_match(row["claim_text_verbatim"])
        label = row["expected_label"]
        is_refusal = label in refusal_labels
        if is_refusal:
            n_refusal += 1
        cls, idxs = classify(claim_norm, seg_norms)
        counts[cls] += 1
        if is_refusal:
            refusal_counts[cls] += 1
            if cls != "WHOLE":
                shown = [(combined[i][0], seg_norms[i][:300]) for i in idxs]
                non_whole_detail.append((row["id"], filename, cls, shown))

    total = len(rows)
    whole_pct = 100.0 * counts["WHOLE"] / total
    print()
    print("=== Check D candidate 1: GROBID sentences ===")
    print(f"Total dev rows: {total}; refusal-family rows: {n_refusal}")
    print(f"overall: WHOLE={counts['WHOLE']} SPLIT={counts['SPLIT']} MERGED={counts['MERGED']} "
          f"NOT_FOUND={counts['NOT_FOUND']}  WHOLE%={whole_pct:.1f}  "
          f"bar(>=95%)={'PASS' if whole_pct >= 95.0 else 'FAIL'}")
    print(f"refusal-family ({n_refusal} rows): WHOLE={refusal_counts['WHOLE']} "
          f"SPLIT={refusal_counts['SPLIT']} MERGED={refusal_counts['MERGED']} "
          f"NOT_FOUND={refusal_counts['NOT_FOUND']}")
    print()
    print(f"--- non-WHOLE refusal-family rows ({len(non_whole_detail)}) ---")
    for rid, filename, cls, shown in non_whole_detail:
        print(f"  {rid} ({filename}) -> {cls}")
        for j, (src, seg) in enumerate(shown):
            print(f"    segment[{j}] (source={src}): {seg!r}")
    print()
    print("--- per-paper source counts ---")
    for filename in filenames:
        print(f"  {filename}: {source_counts[filename]}")
    print()
    print("--- per-paper runtime (seconds) ---")
    for filename in filenames:
        print(f"  {filename}: {runtime[filename]:.1f}")


if __name__ == "__main__":
    main()
