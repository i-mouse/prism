"""Unit tests for eval/step1/sections.py (1c bucket assignment) on small made-up text and offsets. No PDF, no paper."""
from eval.step1 import sections
from eval.step1.sections import Heading

THRESHOLD = 88.0
HEADINGS = [
    Heading(0, "Abstract", "abstract"),
    Heading(200, "1 Introduction", "introduction"),
    Heading(400, "2 Methods", "other"),
    Heading(700, "5 Conclusion", "conclusion"),
    Heading(800, "References", "references"),
    Heading(900, "Appendix A", "other"),
]


def place(start, *, captions=(), whole=True, score=100.0, headings=HEADINGS, length=1000):
    return sections.assign_bucket(start, length, list(headings), list(captions), whole, score, THRESHOLD)


def test_heading_kind_strips_a_section_number_and_matches_the_fixed_words():
    assert sections.heading_kind("1 Introduction") == "introduction"
    assert sections.heading_kind("2.3 Related Work") == "other"
    assert sections.heading_kind("A.1 Methods") == "other"
    assert sections.heading_kind("IV. Conclusions") == "conclusion"
    assert sections.heading_kind("5. conclusion") == "conclusion"
    assert sections.heading_kind("ABSTRACT") == "abstract"
    assert sections.heading_kind("References") == "references"
    assert sections.heading_kind("Bibliography") == "references"
    assert sections.heading_kind("Appendix B: Proofs") == "other"
    assert sections.heading_kind("Acknowledgements") == "other"


def test_heading_kind_rejects_other_lines_and_long_lines():
    assert sections.heading_kind("The model is trained on web text.") is None
    assert sections.heading_kind("") is None
    assert sections.heading_kind("1") is None
    assert sections.heading_kind("Introduction " + "x" * 80) is None          # over 80 chars


def test_find_headings_gives_line_start_offsets():
    text = "Title\nAbstract\nsome text\n1 Introduction\nbody\n"
    found = sections.find_headings(text)
    assert [(h.offset, h.line, h.kind) for h in found] == [
        (text.index("Abstract"), "Abstract", "abstract"),
        (text.index("1 Introduction"), "1 Introduction", "introduction"),
    ]


def test_find_caption_starts_matches_table_figure_and_fig():
    text = "text\nTable 3 | pairs\nmore\nFigure 2: curve\nFig. 4 shows\nTablet 3 is not a caption\n"
    starts = sections.find_caption_starts(text)
    assert starts == [text.index("Table 3"), text.index("Figure 2"), text.index("Fig. 4")]


def test_bucket_follows_the_nearest_heading():
    assert place(20).bucket == "abstract"
    assert place(250).bucket == "introduction"
    assert place(450).bucket == "body"
    assert place(720).bucket == "conclusion"
    assert place(450).confidence == "high"


def test_everything_after_the_last_references_heading_is_appendix():
    assert place(850).bucket == "appendix"
    assert place(950).bucket == "appendix"
    assert place(850).heading == "References"


def test_a_caption_overrides_the_bucket_but_not_appendix_and_keeps_the_bucket_underneath():
    p = place(450, captions=[440])
    assert (p.bucket, p.underneath) == ("table or figure caption", "body")
    assert place(850, captions=[840]).bucket == "appendix"
    assert place(450, captions=[100]).bucket == "body"                         # more than 300 chars after the caption


def test_no_heading_before_the_match_is_abstract_when_early_else_low_confidence_body():
    early = place(30, headings=[], length=1000)                                 # 3% of the paper
    assert (early.bucket, early.confidence) == ("abstract", "high")
    later = place(500, headings=[], length=1000)
    assert later.bucket == "body" and later.confidence == "low"
    assert any("no heading" in r for r in later.reasons)


def test_a_match_that_is_not_whole_is_low_confidence_and_a_weak_one_is_not_found_whole():
    fuzzy = place(250, whole=False, score=92.0)
    assert fuzzy.bucket == "introduction" and fuzzy.confidence == "low" and "not found whole" in fuzzy.reasons
    weak = place(250, whole=False, score=70.0)
    assert (weak.bucket, weak.underneath, weak.confidence, weak.position_pct) == ("not found whole", None, "low", None)
    assert place(None, whole=False, score=0.0).bucket == "not found whole"


def test_position_is_a_percentage_of_the_paper():
    assert place(250).position_pct == 25.0


def test_bucket_totals_count_every_bucket():
    totals = sections.bucket_totals(["body", "body", "appendix", "abstract"])
    assert totals["body"] == 2 and totals["appendix"] == 1 and totals["abstract"] == 1
    assert totals["conclusion"] == 0 and set(totals) == set(sections.BUCKETS)
