"""Synthetic-input tests for the Step P LaTeX probe. No network, no real papers."""
import gzip
import io
import tarfile
import urllib.error
import urllib.request

import pytest

from eval.auditor_v2 import latex_probe as lp


# ----------------------------------------------------------------- helpers

def tex_doc(body: str) -> str:
    return "\\documentclass{article}\n\\begin{document}\n" + body + "\n\\end{document}\n"


def tab(inner: str = "1") -> str:
    return "\\begin{tabular}{c}" + inner + "\\end{tabular}"


def make_tar(files: dict, extra=()) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, content in files.items():
            ti = tarfile.TarInfo(name)
            ti.size = len(content)
            tar.addfile(ti, io.BytesIO(content))
        for ti in extra:
            tar.addfile(ti)
    return buf.getvalue()


class FakeResp:
    def __init__(self, data: bytes, status: int = 200):
        self._b = io.BytesIO(data)
        self.status = status
        self.headers = {"Content-Type": "application/x-eprint-tar"}

    def read(self, n=-1):
        return self._b.read(n)

    def geturl(self):
        return "https://arxiv.org/e-print/x"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Clock:
    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def now(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


# ----------------------------------------------------------------- text stripping

def test_strip_comments_keeps_escaped_percent():
    text = "a % gone\nb \\% kept % gone\nc \\\\% gone\n"
    out = lp.strip_comments(text)
    assert "gone" not in out
    assert "b \\% kept" in out
    assert out.splitlines()[0].strip() == "a"


def test_strip_iffalse_nested_and_else():
    text = "A \\iffalse x \\ifx y z \\fi still \\fi B \\iffalse c \\else KEEP \\fi D"
    assert lp.strip_iffalse(text).split() == ["A", "B", "KEEP", "D"]


def test_iff_is_not_an_opener():
    out = lp.strip_iffalse("\\iffalse a $x \\iff y$ b \\fi tail")
    assert out.strip() == "tail"


# ----------------------------------------------------------------- \input resolution

def test_input_resolution_in_order_and_unresolved(tmp_path):
    (tmp_path / "tables").mkdir()
    (tmp_path / "tables" / "t1.tex").write_text("T1 \\input{tables/t2}", encoding="utf-8")
    (tmp_path / "tables" / "t2.tex").write_text("T2", encoding="utf-8")
    (tmp_path / "main.tex").write_text(
        tex_doc("start \\input{tables/t1} mid \\include{missing} end % \\input{commented}"), encoding="utf-8"
    )
    stats = {"resolved": [], "unresolved": []}
    text = lp.load_resolved(tmp_path / "main.tex", tmp_path, stats)
    assert text.index("start") < text.index("T1") < text.index("T2") < text.index("mid") < text.index("end")
    assert stats["resolved"] == ["tables/t1", "tables/t2"]
    assert stats["unresolved"] == ["missing"]


def test_input_outside_base_is_unresolved(tmp_path):
    base = tmp_path / "src"
    base.mkdir()
    (tmp_path / "secret.tex").write_text("SECRET", encoding="utf-8")
    (base / "main.tex").write_text(tex_doc("\\input{../secret}"), encoding="utf-8")
    stats = {"resolved": [], "unresolved": []}
    text = lp.load_resolved(base / "main.tex", base, stats)
    assert "SECRET" not in text
    assert stats["unresolved"] == ["../secret"]


def test_input_cycle_does_not_loop(tmp_path):
    (tmp_path / "a.tex").write_text("A \\input{b}", encoding="utf-8")
    (tmp_path / "b.tex").write_text("B \\input{a}", encoding="utf-8")
    stats = {"resolved": [], "unresolved": []}
    lp.load_resolved(tmp_path / "a.tex", tmp_path, stats)
    assert stats["unresolved"] == ["a"]


def test_find_mains_reports_every_document_file(tmp_path):
    (tmp_path / "main.tex").write_text(tex_doc("x"), encoding="utf-8")
    (tmp_path / "other.tex").write_text(tex_doc("y"), encoding="utf-8")
    (tmp_path / "part.tex").write_text("no document here", encoding="utf-8")
    (tmp_path / "c.tex").write_text("% \\begin{document}\n", encoding="utf-8")
    assert lp.find_mains(tmp_path) == ["main.tex", "other.tex"]


# ----------------------------------------------------------------- table scan

def test_multirow_multicolumn_detection():
    text = tex_doc(
        "\\begin{table}\\caption{Main results}\n\\begin{tabular}{lcc}\n"
        "\\multirow{2}{*}{Model} & \\multicolumn{2}{c}{Acc} \\\\\n & A & B \\\\ 1 & 2 & 3\\\\\n"
        "\\end{tabular}\\end{table}\n"
        "\\begin{table}\\caption{Plain}" + tab() + "\\end{table}"
    )
    t = lp.scan_tables(text)["tables"]
    assert [x["caption_number"] for x in t] == [1, 2]
    assert t[0]["has_multirow"] and t[0]["has_multicolumn"]
    assert not t[1]["has_multirow"] and not t[1]["has_multicolumn"]
    assert t[0]["caption_first80"] == "Main results"


def test_table_as_image_and_custom_macros():
    text = (
        "\\newcommand{\\sd}[1]{#1}\n"
        "\\begin{table}\\caption{Img}\\includegraphics{t.png}\\end{table}\n"
        "\\begin{table}\\caption{Mac}\\begin{tabular}{c}\\sd{1.2} \\textbf{3} \\foo{4}\\end{tabular}\\end{table}"
    )
    t = lp.scan_tables(text)["tables"]
    assert t[0]["has_includegraphics"] and not t[0]["has_tabular"]
    assert t[1]["custom_macros"] == ["foo", "sd"]
    assert t[1]["custom_macros_defined_in_source"] == ["sd"]


def test_caption_order_with_captionof_wraptable_and_star():
    text = tex_doc(
        "\\begin{table}[t]\\caption{A first}" + tab() + "\\end{table}\n"
        "\\begin{center}\\captionof{table}{B second}" + tab("2") + "\\end{center}\n"
        "\\begin{wraptable}{r}{5cm}\\caption{C third}" + tab("3") + "\\end{wraptable}\n"
        "\\begin{table*}\\caption[short]{D fourth}" + tab("4") + "\\end{table*}\n"
        "\\begin{longtable}{c}\\caption{E fifth}\\\\ 5 \\end{longtable}\n"
        "\\begin{sidewaystable}\\caption{F sixth}" + tab("6") + "\\end{sidewaystable}"
    )
    t = lp.scan_tables(text)["tables"]
    assert [x["caption_number"] for x in t] == [1, 2, 3, 4, 5, 6]
    assert [x["caption_first80"][0] for x in t] == list("ABCDEF")
    assert [x["env"] for x in t] == ["table", "captionof", "wraptable", "table*", "longtable", "sidewaystable"]
    assert t[1]["body_rule"] == "enclosing:center"


def test_uncaptioned_and_subtables():
    text = tex_doc(
        "\\begin{table}" + tab() + "\\end{table}\n"
        "\\begin{table}\\caption{Main}\\begin{subtable}{.5\\textwidth}\\caption{left}" + tab() + "\\end{subtable}"
        "\\begin{subtable}{.5\\textwidth}" + tab("2") + "\\end{subtable}\\end{table}"
    )
    res = lp.scan_tables(text)
    t = res["tables"]
    assert t[0]["caption_number"] is None
    assert t[1]["caption_number"] == 1 and t[1]["caption_first80"] == "Main"
    assert t[1]["subtables"] == 2
    assert any("without \\caption" in d for d in res["doubts"])


def test_appendix_and_numbering_doubts():
    text = tex_doc(
        "\\begin{table}\\caption{A}" + tab() + "\\end{table}\n\\appendix\n"
        "\\renewcommand{\\thetable}{A\\arabic{table}}\n"
        "\\begin{table}\\caption{B}" + tab() + "\\end{table}"
    )
    res = lp.scan_tables(text)
    t = res["tables"]
    assert [x["after_appendix"] for x in t] == [False, True]
    assert any("appendix present" in d for d in res["doubts"])
    assert any("thetable redefined" in d for d in res["doubts"])


def test_commented_and_iffalse_tables_are_not_counted(tmp_path):
    (tmp_path / "main.tex").write_text(
        tex_doc(
            "% \\begin{table}\\caption{Commented}" + tab() + "\\end{table}\n"
            "\\iffalse \\begin{table}\\caption{Hidden}" + tab() + "\\end{table} \\fi\n"
            "\\begin{table}\\caption{Real}" + tab() + "\\end{table}"
        ),
        encoding="utf-8",
    )
    r = lp.scan_main(tmp_path, "main.tex", "2610.11519v1", None)
    assert [t["caption_first80"] for t in r["tables"]] == ["Real"]


# ----------------------------------------------------------------- pin check

PIN_BODY = (
    "\\begin{tabular}{lcc}\\toprule\n"
    "Model & A09 & Mean \\\\ \\midrule\n"
    "JevKT & 0.709 $\\pm$ 0.059 & .640 \\\\\n"
    "\\textbf{Seer} & \\textbf{88.09} & $+0.30$ \\\\\n"
    "\\multirow{2}{*}{Lingshu} & 44.5 / 53.3 & \\textcolor{red}{12} \\\\\n"
    "\\bottomrule\\end{tabular}"
)


def _pin(pid, value, **kw):
    return {"id": pid, "kind": "cell", "value": value, "key_uncertain": False, **kw}


def test_numeric_pin_match():
    table = {"_body": "\\caption{x}" + PIN_BODY}
    pins = [
        _pin("p1", ".709"),        # pin without leading zero, LaTeX with
        _pin("p2", "0.640"),       # LaTeX without leading zero, pin with
        _pin("p3", "88.09"),       # inside \textbf{}
        _pin("p4", "+0.30"),       # explicit plus vs math "+0.30"
        _pin("p5", "0.30"),
        _pin("p6", "44.5 / 53.3"),  # pair
        _pin("p7", "12"),          # inside \textcolor
        _pin("p8", ".059"),        # SD part
        _pin("p9", ".999", key_uncertain=True),
        _pin("p10", "-"),
        {"id": "S1", "kind": "row_count", "count": 3},
    ]
    r = lp.check_pins(table, pins)
    res = {k: v["result"] for k, v in r["pins"].items()}
    assert res["p1"] == res["p2"] == res["p3"] == res["p4"] == res["p5"] == "yes"
    assert res["p6"] == res["p7"] == res["p8"] == "yes"
    assert res["p9"] == "no" and res["p10"] == "not_numeric"
    assert (r["present"], r["total"]) == (8, 9)
    assert (r["present_gated"], r["total_gated"]) == (8, 8)
    assert r["missing_ids"] == ["p9"]
    assert r["not_numeric_ids"] == ["p10"]
    assert r["structural_not_checked"] == ["S1"]


def test_table_cells_unwrap_and_spans():
    rows = lp.table_cells("\\caption{c}" + PIN_BODY)
    assert rows[0] == ["Model", "A09", "Mean"]
    assert rows[2][0] == "Seer" and rows[2][1] == "88.09" and rows[2][2] == "+0.30"
    assert rows[3][0] == "Lingshu"


def test_scan_main_with_input_and_gate_pins(tmp_path):
    (tmp_path / "tables").mkdir()
    (tmp_path / "tables" / "t1.tex").write_text(
        "\\begin{table}\\caption{Gate table}" + PIN_BODY + "\\end{table}", encoding="utf-8"
    )
    (tmp_path / "main.tex").write_text(tex_doc("\\input{tables/t1}"), encoding="utf-8")
    pins = {
        "gate_tables": {"X-T1": {"table_id": "X-T1", "paper_id": "2610.11519v1", "caption_number": 1},
                        "X-T2": {"table_id": "X-T2", "paper_id": "2610.11519v1", "caption_number": 2},
                        "Y-T1": {"table_id": "Y-T1", "paper_id": "other", "caption_number": 1}},
        "pins_by_table": {"X-T1": [_pin("a", "88.09"), _pin("b", "1.11")], "X-T2": [_pin("c", "1")]},
    }
    r = lp.scan_main(tmp_path, "main.tex", "2610.11519v1", pins)
    assert r["inputs_resolved"] == 1 and r["inputs_unresolved"] == []
    gates = {g["table_id"]: g for g in r["gate_tables"]}
    assert set(gates) == {"X-T1", "X-T2"}
    assert gates["X-T1"]["found"] and gates["X-T1"]["has_multirow"]
    assert gates["X-T1"]["pin_check"]["missing_ids"] == ["b"]
    assert not gates["X-T2"]["found"]
    assert all("_body" not in t for t in r["tables"])


# ----------------------------------------------------------------- archives

def test_safe_extract_refuses_traversal_and_links(tmp_path):
    link = tarfile.TarInfo("link.tex")
    link.type = tarfile.SYMTYPE
    link.linkname = "/etc/passwd"
    data = make_tar({"../evil.txt": b"x", "sub/ok.tex": b"ok", "/abs.tex": b"x"}, extra=[link])
    dest = tmp_path / "out" / "src"
    r = lp.safe_extract(data, dest)
    reasons = {x["name"]: x["reason"] for x in r["rejected"]}
    assert reasons["../evil.txt"] == "path traversal"
    assert reasons["/abs.tex"] == "absolute path"
    assert reasons["link.tex"] == "link"
    assert r["extracted"] == 1
    assert (dest / "sub" / "ok.tex").read_bytes() == b"ok"
    assert not (tmp_path / "out" / "evil.txt").exists()
    assert not (dest / "link.tex").exists() and not (dest / "link.tex").is_symlink()


def test_process_archive_tar_gz(tmp_path):
    raw = gzip.compress(make_tar({"main.tex": tex_doc("x").encode()}))
    r = lp.process_archive(raw, tmp_path)
    assert r["format"] == "tar.gz" and r["source_available"] and r["extracted_files"] == 1
    assert (tmp_path / "src" / "main.tex").exists()


def test_process_archive_single_gz_tex(tmp_path):
    raw = gzip.compress(tex_doc("only file").encode())
    r = lp.process_archive(raw, tmp_path)
    assert r["format"] == "gz-single-tex" and r["source_available"]
    assert "only file" in (tmp_path / "src" / "main.tex").read_text()


@pytest.mark.parametrize(
    "raw,fmt",
    [
        (b"%PDF-1.5 binary", "pdf-only"),
        (gzip.compress(b"%PDF-1.7 binary"), "pdf-only"),
        (b"<!DOCTYPE html><html></html>", "html"),
        (b"\x00\x01 random bytes", "unknown"),
    ],
)
def test_no_source_is_recorded_not_an_error(tmp_path, raw, fmt):
    r = lp.process_archive(raw, tmp_path)
    assert r["format"] == fmt
    assert r["source_available"] is False
    assert not (tmp_path / "src").exists()


# ----------------------------------------------------------------- fetch (fake opener, no network)

ID1, ID2 = "2610.11519v1", "2610.11132v1"
GOOD = gzip.compress(make_tar({"main.tex": tex_doc("x").encode()}))


def test_fetch_rejects_id_not_on_list(tmp_path):
    with pytest.raises(ValueError):
        lp.fetch_all(["2610.99999v1"], tmp_path, opener=lambda *a, **k: FakeResp(GOOD))


def test_fetch_rate_limit_user_agent_and_record(tmp_path):
    clk = Clock()
    seen = []

    def opener(req, timeout=None):
        seen.append((req.full_url, req.get_header("User-agent")))
        return FakeResp(GOOD)

    recs = lp.fetch_all([ID1, ID2], tmp_path, opener, clk.sleep, clk.now)
    assert seen == [(f"https://arxiv.org/e-print/{ID1}", lp.USER_AGENT), (f"https://arxiv.org/e-print/{ID2}", lp.USER_AGENT)]
    assert clk.sleeps == [5.0]
    assert recs[0]["status"] == "downloaded" and len(recs[0]["sha256"]) == 64
    assert (tmp_path / ID1 / f"{ID1}.src").read_bytes() == GOOD
    assert (tmp_path / ID1 / "src" / "main.tex").exists()


def test_fetch_never_redownloads_existing_file(tmp_path):
    (tmp_path / ID1).mkdir()
    (tmp_path / ID1 / f"{ID1}.src").write_bytes(GOOD)

    def opener(*a, **k):
        raise AssertionError("network used")

    clk = Clock()
    rec = lp.fetch_all([ID1], tmp_path, opener, clk.sleep, clk.now)[0]
    assert rec["status"] == "already_on_disk" and rec["source_available"]
    assert (tmp_path / ID1 / "src" / "main.tex").exists()


def test_fetch_404_not_retried_and_recorded(tmp_path):
    calls = []

    def opener(req, timeout=None):
        calls.append(1)
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b""))

    clk = Clock()
    rec = lp.fetch_all([ID1], tmp_path, opener, clk.sleep, clk.now)[0]
    assert len(calls) == 1 and 60.0 not in clk.sleeps
    assert rec["status"] == "failed" and rec["http_status"] == 404 and rec["source_available"] is False


def test_fetch_transient_error_retries_once_after_60s(tmp_path):
    calls = []

    def opener(req, timeout=None):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.URLError("reset")
        return FakeResp(GOOD)

    clk = Clock()
    rec = lp.fetch_all([ID1], tmp_path, opener, clk.sleep, clk.now)[0]
    assert len(calls) == 2 and 60.0 in clk.sleeps
    assert rec["status"] == "downloaded"


def test_fetch_second_transient_error_gives_up(tmp_path):
    calls = []

    def opener(req, timeout=None):
        calls.append(1)
        raise urllib.error.URLError("down")

    clk = Clock()
    rec = lp.fetch_all([ID1], tmp_path, opener, clk.sleep, clk.now)[0]
    assert len(calls) == 2 and rec["status"] == "failed"


def test_redirect_to_arxiv_hosts_allowed_other_hosts_refused_and_recorded(tmp_path):
    h = lp._ArxivRedirect()
    req = urllib.request.Request("https://arxiv.org/e-print/x")
    for ok in ("https://arxiv.org/e-print/y", "https://export.arxiv.org/e-print/y", "https://cdn.arxiv.org/z"):
        assert h.redirect_request(req, io.BytesIO(b""), 302, "Found", {}, ok).full_url == ok
    for bad in ("https://evilarxiv.org/x", "https://arxiv.org.evil.com/x", "https://example.com/x"):
        with pytest.raises(urllib.error.HTTPError):
            h.redirect_request(req, io.BytesIO(b""), 302, "Found", {}, bad)

    def opener(r, timeout=None):  # the real opener raises this when a redirect is refused
        return h.redirect_request(r, io.BytesIO(b""), 302, "Found", {}, "https://example.com/x")

    clk = Clock()
    rec = lp.fetch_all([ID1], tmp_path, opener, clk.sleep, clk.now)[0]
    assert rec["status"] == "failed" and rec["http_status"] == 302
    assert "redirect outside arxiv.org refused" in rec["error"] and "example.com" in rec["error"]
    assert 60.0 not in clk.sleeps


def test_redirect_outside_arxiv_is_refused():
    h = lp._ArxivRedirect()
    req = urllib.request.Request("https://arxiv.org/e-print/x")
    with pytest.raises(urllib.error.HTTPError):
        h.redirect_request(req, io.BytesIO(b""), 302, "Found", {}, "https://evil.example.com/x")
    with pytest.raises(urllib.error.HTTPError):
        h.redirect_request(req, io.BytesIO(b""), 302, "Found", {}, "http://arxiv.org/e-print/x")


# ----------------------------------------------------------------- S-row selection

def _row(rid, label="supported", claim="Method is best on all datasets", notes="see Table 4", ev=None, why=""):
    return {"id": rid, "expected_label": label, "claim_text_verbatim": claim, "scoring_notes": notes,
            "expected_evidence_sections": ev if ev is not None else ["Section 4"], "why_this_case": why}


def _dev(*papers):
    return {"papers": [{"paper_id": pid, "expected_matrix": rows} for pid, rows in papers]}


def _mm(dev, shared=None, skip=()):
    rows = {}
    for p in dev["papers"]:
        for r in p["expected_matrix"]:
            if r["id"] in skip:
                continue
            # real dev map shape: persisted_claim_id null, claim_fingerprint names the matched run-1 claim
            rows[r["id"]] = {"persisted_claim_id": None, "claim_fingerprint": f"c-{r['id']}",
                             "confirmed_no_match": False}
    for rid, cid in (shared or {}).items():
        rows[rid]["claim_fingerprint"] = cid
    return {"rows": rows}


def test_select_s_rows_tiny_dev_set():
    dev = _dev(
        ("2610.11519v1", [
            _row("P1-S10"), _row("P1-S2"), _row("P1-S1"),
            _row("P1-S3"),                                   # shares its claim with a refusal row
            _row("P1-R1", label="partially_supported", notes="Table 4"),
            _row("P1-S4", claim="We also tried it"),         # no scope word
            _row("P1-S5", notes="no cite", why="Table 3"),   # why_this_case never selects
            _row("P1-S6", notes="no cite", ev=["Table 5"]),  # evidence field cite counts
        ]),
        ("2610.11132v1", [_row("P2-S1", claim="consistently outperforms", notes="Tables 1-2"), _row("P2-S2", claim="many models")]),
        ("2610.11135v1", [_row("P3-S1", claim="works for both", notes="Table 9"), _row("P3-S2")]),
    )
    mm = _mm(dev, shared={"P1-R1": "c-P1-S3"})
    mm["rows"]["P3-S2"] = {"persisted_claim_id": None, "claim_fingerprint": None, "confirmed_no_match": True}  # fails (a)
    out = lp.select_s_rows(dev, mm)

    ids = [r["row_id"] for r in out["selected"]]
    # first per paper in paper order, then fill by (natural) row id: S1 < S2 < S6 < S10
    assert ids[:3] == ["P1-S1", "P2-S1", "P3-S1"]
    assert ids[3:6] == ["P1-S2", "P1-S6", "P1-S10"]
    via = {r["row_id"]: r["via"] for r in out["selected"]}
    assert via["P1-S1"] == "first-per-paper" and via["P1-S2"] == "fill"
    # fewer than 8 -> criterion (c) relaxed: P1-S4 and P2-S2 have a, b, d but no scope word
    assert out["counts"]["criterion_c_relaxed"] is True
    assert via["P1-S4"] == "relaxed-no-scope-word"
    assert "P1-S5" not in ids and "P1-S3" not in ids and "P3-S2" not in ids
    assert [r["row_id"] for r in out["shared_claim_rows"]] == ["P1-S3"]
    assert out["shared_claim_rows"][0]["shared_with_refusal_rows"] == ["P1-R1"]
    by_id = {r["row_id"]: r for r in out["selected"]}
    assert by_id["P2-S1"]["tables_cited"] == ["1", "2"]
    assert by_id["P2-S1"]["scope_words"] == ["consistently", "outperforms"]
    assert by_id["P1-S6"]["tables_cited"] == ["5"]
    assert "P2-S2" not in [r["row_id"] for r in out["selected"][:6]]


def test_select_caps_at_ten_in_paper_order():
    dev = _dev(*[(f"id{n}", [_row(f"P{n}-S1"), _row(f"P{n}-S2")]) for n in range(1, 13)])
    out = lp.select_s_rows(dev, _mm(dev))
    assert [r["row_id"] for r in out["selected"]] == [f"P{n}-S1" for n in range(1, 11)]
    assert out["counts"]["criterion_c_relaxed"] is False


def test_select_fills_to_ten_by_row_id():
    dev = _dev(*[(f"id{n}", [_row(f"P{n}-S{k}") for k in range(1, 5)]) for n in range(1, 4)])
    out = lp.select_s_rows(dev, _mm(dev))
    ids = [r["row_id"] for r in out["selected"]]
    assert ids == ["P1-S1", "P2-S1", "P3-S1", "P1-S2", "P1-S3", "P1-S4", "P2-S2", "P2-S3", "P2-S4", "P3-S2"]
    assert out["counts"]["a_b_c_d"] == 12


def test_scope_word_wildcards_and_boundaries():
    dev = _dev(("id1", [
        _row("P1-S1", claim="Results are consistent with theory"),
        _row("P1-S2", claim="It outperformed the baseline"),
        _row("P1-S3", claim="Many models were tested"),
        _row("P1-S4", claim="Any model works"),
        _row("P1-S5", claim="Best-in-class results"),
    ]))
    out = lp.select_s_rows(dev, _mm(dev))
    words = {r["row_id"]: r["scope_words"] for r in out["selected"]}
    assert words["P1-S1"] == ["consistent"] and words["P1-S2"] == ["outperformed"]
    assert words["P1-S4"] == ["any"] and words["P1-S5"] == ["best"]
    assert words["P1-S3"] == []
    assert {r["row_id"]: r["via"] for r in out["selected"]}["P1-S3"] == "relaxed-no-scope-word"


def test_extract_table_refs():
    assert lp.extract_table_refs("see Table 4 and Tables 1-3, Table A.2; Fig. 3") == ["4", "1", "2", "3", "A2"]
    assert lp.extract_table_refs("Tab. 7 / no tables here; Variable 5") == ["7"]
    assert lp.extract_table_refs("") == []
