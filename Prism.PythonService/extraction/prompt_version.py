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


def get_prompt_version(fewshot_fix: bool | None = None, fewshot_shapes: bool | None = None) -> str:
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
    """
    if fewshot_fix is None:
        fewshot_fix = settings.extractor_fewshot_fix
    if fewshot_shapes is None:
        fewshot_shapes = settings.extractor_fewshot_shapes

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

    return hashlib.sha256(combined).hexdigest()[:12]
