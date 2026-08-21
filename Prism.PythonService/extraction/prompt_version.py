"""Auto-derives prompt version from content hash.

Reads the prompt files and returns a stable 12-char hash. Used
to tag each extraction run in document_extractors.Fields jsonb
so extraction runs can be attributed to specific prompt states.
"""
import hashlib
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

PROMPT_FILENAMES = (
    "extract_metadata_system.md",
    "extract_metadata_fewshot.json",
    "extract_claims_system.md",
    "extract_claims_fewshot.json",
    "audit_claim_system.md",
    "structure_verdict_system.md",
)


def get_prompt_version() -> str:
    """Returns a 12-character SHA-256 hash of the current prompt files.

    Reads all prompt files across both extraction stages (metadata, and
    the extractor/auditor/structurer trio for claims), hashes their
    combined bytes in a fixed order, returns first 12 chars for readability.
    """
    combined = b""
    for filename in PROMPT_FILENAMES:
        path = PROMPTS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found at {path}")
        combined += path.read_bytes()

    return hashlib.sha256(combined).hexdigest()[:12]
