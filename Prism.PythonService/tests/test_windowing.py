"""Unit tests for extraction/windowing.py's make_windows - Experiment 3's
pass-2 windowing geometry (6000-char windows, 1500-char overlap), ported
from docs/evals/exp3_prechecks/check_d_windows.py."""
from extraction.windowing import OVERLAP, STEP, WINDOW_SIZE, make_windows


def test_empty_text_returns_no_windows():
    assert make_windows("") == []


def test_text_shorter_than_window_returns_single_window():
    text = "x" * 100
    windows = make_windows(text)
    assert windows == [text]


def test_text_exactly_window_size_returns_single_window():
    text = "x" * WINDOW_SIZE
    windows = make_windows(text)
    assert len(windows) == 1
    assert windows[0] == text


def test_consecutive_windows_overlap_by_overlap_chars():
    text = "".join(str(i % 10) for i in range(WINDOW_SIZE + STEP + 1))
    windows = make_windows(text)
    assert len(windows) >= 2
    # The last OVERLAP chars of window[0] equal the first OVERLAP chars of window[1].
    assert windows[0][-OVERLAP:] == windows[1][:OVERLAP]


def test_last_window_may_be_shorter_and_reaches_the_end():
    text = "x" * (WINDOW_SIZE + 100)
    windows = make_windows(text)
    assert len(windows) == 2
    assert len(windows[0]) == WINDOW_SIZE
    assert len(windows[1]) < WINDOW_SIZE
    assert text.endswith(windows[-1])


def test_windows_reconstruct_the_full_text_with_overlap_accounted_for():
    text = "".join(str(i % 10) for i in range(3 * STEP + 200))
    windows = make_windows(text)
    reconstructed = windows[0]
    for w in windows[1:]:
        reconstructed += w[OVERLAP:]
    assert reconstructed == text
