"""Auto-derives prompt version from content hash.

Reads the prompt files and returns a stable 12-char hash. Used
to tag each extraction run in document_extractors.Fields jsonb
so extraction runs can be attributed to specific prompt states.
"""
import hashlib
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

def get_prompt_version() -> str:
    """Returns a 12-character SHA-256 hash of the current prompt files.

    Reads extract_claims_system.md and extract_claims_fewshot.json,
    hashes their combined bytes, returns first 12 chars for readability.
    """
    system_path = PROMPTS_DIR / "extract_claims_system.md"
    fewshot_path = PROMPTS_DIR / "extract_claims_fewshot.json"

    if not system_path.exists():
        raise FileNotFoundError(f"System prompt not found at {system_path}")
    if not fewshot_path.exists():
        raise FileNotFoundError(f"Few-shot examples not found at {fewshot_path}")

    combined = system_path.read_bytes() + fewshot_path.read_bytes()
    return hashlib.sha256(combined).hexdigest()[:12]
