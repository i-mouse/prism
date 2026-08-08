import os

os.environ["LLM_EXTRACTION_MODEL"] = "gemini-3.6-flash"
os.environ["LLM_AUDIT_MODEL"] = "gemini-3.1-flash-lite"
os.environ["AI_API_KEY"] = "AIzaSyAW5L5vau-aTrE1X1Y8NK43a4oMpoOE8Ec"

import asyncio
import fitz
from pathlib import Path

from extraction.engine import extract_claims, extract_metadata
from extraction.grounding import ground_extraction

import asyncio
import fitz
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("../.env.local")

from extraction.engine import extract_claims, extract_metadata
from extraction.grounding import ground_extraction


async def main():
    pdf_path = Path("../docs/research_papers/2303.11366v4.pdf")
    doc = fitz.open(str(pdf_path))
    paper_text = ""
    for page in doc:
        paper_text += page.get_text()
    doc.close()

    print(f"Paper text length: {len(paper_text)} chars\n")

    # Stage 1a: metadata extraction (Prompt 1)
    print("=== METADATA EXTRACTION (Prompt 1) ===")
    metadata_response = await extract_metadata(
        paper_text=paper_text,
        chat_id="smoke-test",
        correlation_id="metadata-run-1"
    )
    m = metadata_response.metadata
    print(f"research_objective: {m.research_objective[:100]}...")
    print(f"headline_conclusion: {m.headline_conclusion[:100]}...")
    print(f"sample_characteristics: {m.sample_characteristics[:100]}...")
    print(f"baselines_compared: {m.baselines_compared[:100]}...")
    print(f"ablation_studies: {m.ablation_studies[:100]}...")
    print(f"experimental_confounds: {m.experimental_confounds[:100]}...")
    print(f"author_acknowledged_limitations: {m.author_acknowledged_limitations[:100]}...")
    print(f"extrapolated_implications: {m.extrapolated_implications[:100]}...")
    print(f"empirical_results: {m.empirical_results[:100]}...")

    # Stage 1b: claims extraction (Prompt 2)
    print("\n=== CLAIMS EXTRACTION (Prompt 2) ===")
    extraction = await extract_claims(
        paper_text=paper_text,
        chat_id="smoke-test",
        correlation_id="claims-run-1"
    )
    print(f"Claims extracted: {len(extraction.claims)}")

    # Stage 2: grounding
    print("\n=== GROUNDING ===")
    grounded = await ground_extraction(
        extraction=extraction,
        paper_text=paper_text,
        chat_id="smoke-test",
        correlation_id="claims-run-1"
    )

    passed = sum(1 for c in grounded if not c.missing)
    failed = sum(1 for c in grounded if c.missing)
    print(f"Claims passed grounding: {passed}")
    print(f"Claims failed grounding: {failed}")

    print("\n=== SAMPLE CLAIMS ===")
    for i, claim in enumerate(grounded[:3], 1):
        print(f"\n--- Claim {i} ---")
        print(f"Label: {claim.label.value}")
        print(f"Grounding: {claim.grounding_status.value}")
        print(f"Summary: {claim.claim_summary}")
        print(f"Spans passing: {sum(1 for s in claim.evidence_spans if s.grounding_status.value == 'Pass')}/{len(claim.evidence_spans)}")


if __name__ == "__main__":
    asyncio.run(main())