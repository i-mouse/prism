"""Auto-derives prompt version from content hash.

Reads the prompt files and returns a stable 12-char hash. Used
to tag each extraction run in document_extractors.Fields jsonb
so extraction runs can be attributed to specific prompt states.
"""
import hashlib
from pathlib import Path

from config import settings

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

PROMPT_FILENAMES = (
    "extract_metadata_system.md",
    "extract_metadata_fewshot.json",
    "extract_claims_system.md",
    "extract_claims_fewshot.json",
    "audit_claim_system.md",
    "structure_verdict_system.md",
    "audit_system.txt",
    "audit_fewshot.json",
)

# Non-prompt files whose text still reaches the LLM. schemas.py's Field
# descriptions are sent to the structurer as part of response_schema=ClaimLLM,
# so editing them changes model input just like editing a prompt file.
# Hashed after the prompt files, in this order.
EXTRA_HASHED_FILES = (
    Path(__file__).parent / "schemas.py",
)

# Experiment 2 (redesigned): the claim-shape few-shot file and its system-prompt
# addendum. Hashed only when fewshot_shapes is on - these files don't exist in
# the extractor's rendering at all when the flag is off, so their bytes must
# not affect the flag-off hash.
SHAPES_PROMPT_FILENAMES = (
    "extract_claims_fewshot_shapes.json",
    "extract_claims_system_shapes.md",
)

# Experiment 3 - pass-2 windowed extractor prompt. Hashed only when
# extractor_second_pass is on - this file doesn't exist in the pipeline's
# rendering at all when the flag is off, so its bytes must not affect the
# flag-off hash. Deliberately does not touch schemas.py: the pass-2 wrapper
# model (extraction/pass2.py::SentenceListLLM) lives outside schemas.py so
# this experiment never risks moving the flag-off hash.
SECOND_PASS_PROMPT_FILENAMES = (
    "extract_claims_pass2_system.md",
)

# Clean-extraction attempt - the new pass-2 prompt plus the filter's own
# system prompt. Hashed ONLY when both extractor_second_pass and
# extractor_pass2_clean are on, and - per docs/decisions.md's "Clean-
# extraction attempt amended: new pass-2 prompt + filter - 2026-10-17" -
# these two files are hashed INSTEAD OF SECOND_PASS_PROMPT_FILENAMES in
# that case, not in addition to it: the clean pass-2 prompt replaces the old
# one, it doesn't run alongside it. extractor_second_pass on with
# extractor_pass2_clean off is unaffected (today's second-pass-only hash,
# unchanged); extractor_second_pass off is unaffected regardless of
# extractor_pass2_clean's value (these files are never read at all).
CLEAN_PASS2_PROMPT_FILENAMES = (
    "extract_claims_pass2_v2_system.md",
    "extract_claims_pass2_clean_system.md",
)


def get_prompt_version(
    fewshot_fix: bool | None = None,
    fewshot_shapes: bool | None = None,
    extractor_second_pass: bool | None = None,
    extractor_pass2_clean: bool | None = None,
) -> str:
    """Returns a 12-character SHA-256 hash of the current prompt files.

    Reads all prompt files across both extraction stages (metadata, and
    the extractor/auditor/structurer trio for claims), then the files in
    EXTRA_HASHED_FILES, hashes their combined bytes in a fixed order,
    returns first 12 chars for readability.

    fewshot_fix: Experiment 2's extractor few-shot "note" field fix changes
    extractor behavior (extraction/prompt_loader.py::_is_negative_example)
    without changing any of the hashed files' bytes. None (default) reads
    settings.extractor_fewshot_fix; pass True/False explicitly to force a
    variant. Off reproduces exactly today's hash (no bytes appended). On
    appends a literal marker so the two variants never collide.

    fewshot_shapes: Experiment 2 (redesigned)'s claim-shape few-shot examples.
    None (default) reads settings.extractor_fewshot_shapes; pass True/False
    explicitly to force a variant. Off leaves the hash exactly as it is with
    fewshot_shapes absent from the computation (SHAPES_PROMPT_FILENAMES'
    bytes are not read, no marker appended). On reads SHAPES_PROMPT_FILENAMES'
    bytes (after the fewshot_fix marker, if any) and appends its own literal
    marker.

    extractor_second_pass: Experiment 3's pass-2 windowed extractor. None
    (default) reads settings.extractor_second_pass; pass True/False
    explicitly to force a variant. Off leaves the hash exactly as it is
    today (SECOND_PASS_PROMPT_FILENAMES' bytes are not read, no marker
    appended). On reads SECOND_PASS_PROMPT_FILENAMES' bytes (after the
    fewshot_fix/fewshot_shapes markers, if any) and appends its own literal
    marker - UNLESS extractor_pass2_clean is also on, in which case
    CLEAN_PASS2_PROMPT_FILENAMES' bytes are read instead (see below).
    schemas.py is never touched by this flag.

    extractor_pass2_clean: the clean-extraction attempt's new pass-2 prompt
    plus filter prompt. None (default) reads settings.extractor_pass2_clean;
    pass True/False explicitly to force a variant. Has no effect at all when
    extractor_second_pass is off (matching the live pipeline: the clean flag
    alone changes nothing - see extraction/engine.py::extract_claims). When
    both are on, CLEAN_PASS2_PROMPT_FILENAMES' bytes are read INSTEAD OF
    SECOND_PASS_PROMPT_FILENAMES' bytes (after the fewshot_fix/fewshot_shapes
    markers, if any) and its own literal marker is appended - the old
    second-pass-only hash is intentionally unreachable in that combination.
    """
    if fewshot_fix is None:
        fewshot_fix = settings.extractor_fewshot_fix
    if fewshot_shapes is None:
        fewshot_shapes = settings.extractor_fewshot_shapes
    if extractor_second_pass is None:
        extractor_second_pass = settings.extractor_second_pass
    if extractor_pass2_clean is None:
        extractor_pass2_clean = settings.extractor_pass2_clean

    combined = b""
    paths = [PROMPTS_DIR / filename for filename in PROMPT_FILENAMES] + list(EXTRA_HASHED_FILES)
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found at {path}")
        combined += path.read_bytes()

    if fewshot_fix:
        combined += b"\x00extractor_fewshot_fix=1"

    if fewshot_shapes:
        for filename in SHAPES_PROMPT_FILENAMES:
            path = PROMPTS_DIR / filename
            if not path.exists():
                raise FileNotFoundError(f"Prompt file not found at {path}")
            combined += path.read_bytes()
        combined += b"\x00extractor_fewshot_shapes=1"

    if extractor_second_pass and extractor_pass2_clean:
        for filename in CLEAN_PASS2_PROMPT_FILENAMES:
            path = PROMPTS_DIR / filename
            if not path.exists():
                raise FileNotFoundError(f"Prompt file not found at {path}")
            combined += path.read_bytes()
        combined += b"\x00extractor_second_pass=1\x00extractor_pass2_clean=1"
    elif extractor_second_pass:
        for filename in SECOND_PASS_PROMPT_FILENAMES:
            path = PROMPTS_DIR / filename
            if not path.exists():
                raise FileNotFoundError(f"Prompt file not found at {path}")
            combined += path.read_bytes()
        combined += b"\x00extractor_second_pass=1"

    return hashlib.sha256(combined).hexdigest()[:12]
