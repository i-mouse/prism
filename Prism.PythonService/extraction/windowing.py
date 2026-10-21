"""Splits raw PyMuPDF-extracted paper text into fixed-size overlapping windows
for Experiment 3's pass-2 extractor calls.

Ports the exact windowing geometry chosen in the Exp 3 pre-checks
(docs/evals/exp3_prechecks/check_d_windows.py): fixed-size character
windows, no sentence splitting. Pure function, no I/O.
"""

WINDOW_SIZE = 6000
OVERLAP = 1500
STEP = WINDOW_SIZE - OVERLAP  # 4500


def make_windows(text: str) -> list[str]:
    """Splits text into WINDOW_SIZE-char windows overlapping by OVERLAP chars.

    The last window may be shorter than WINDOW_SIZE. A text shorter than or
    equal to WINDOW_SIZE returns a single window containing the whole text.
    An empty string returns an empty list.
    """
    windows: list[str] = []
    n = len(text)
    if n == 0:
        return windows

    start = 0
    while start < n:
        windows.append(text[start:start + WINDOW_SIZE])
        if start + WINDOW_SIZE >= n:
            break
        start += STEP
    return windows
