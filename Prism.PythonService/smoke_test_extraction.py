import asyncio
import fitz
from pathlib import Path
from extraction.engine import extract_claims
from extraction.grounding import ground_extraction

async def main():
    pdf_path = Path("../docs/research_papers/2303.11366v4.pdf")
    doc = fitz.open(str(pdf_path))
    paper_text = ""
    for page in doc:
        paper_text += page.get_text()
    doc.close()
    
    print(f"Paper text length: {len(paper_text)} chars")
    
    # Stage 1: extraction
    print("\n=== EXTRACTION ===")
    extraction = await extract_claims(
        paper_text=paper_text,
        chat_id="smoke-test",
        correlation_id="grounding-run-1"
    )
    print(f"Claims extracted: {len(extraction.claims)}")
    
    # Stage 2: grounding
    print("\n=== GROUNDING ===")
    grounded = await ground_extraction(
        extraction=extraction,
        paper_text=paper_text,
        chat_id="smoke-test",
        correlation_id="grounding-run-1"
    )
    
    passed = sum(1 for c in grounded if not c.missing)
    failed = sum(1 for c in grounded if c.missing)
    print(f"Claims passed grounding: {passed}")
    print(f"Claims failed grounding: {failed}")
    
    print("\n=== SAMPLE OUTPUT ===")
    for i, claim in enumerate(grounded[:3], 1):
        print(f"\n--- Claim {i} ---")
        print(f"Label: {claim.label.value}")
        print(f"Grounding: {claim.grounding_status.value}")
        print(f"Missing: {claim.missing}")
        print(f"Reason: {claim.reason}")
        print(f"Summary: {claim.claim_summary}")
        print(f"Spans passing: {sum(1 for s in claim.evidence_spans if s.grounding_status.value == 'Pass')}/{len(claim.evidence_spans)}")

if __name__ == "__main__":
    asyncio.run(main())