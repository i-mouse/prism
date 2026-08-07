import asyncio
import fitz  # PyMuPDF — already in your dependencies
from pathlib import Path
from extraction.engine import extract_claims

async def main():
    pdf_path = Path("../docs/research_papers/2303.11366v4.pdf")
    doc = fitz.open(str(pdf_path))
    paper_text = ""
    for page in doc:
        paper_text += page.get_text()
    doc.close()
    
    print(f"Paper text length: {len(paper_text)} chars")
    
    result = await extract_claims(
        paper_text=paper_text,
        chat_id="smoke-test",
        correlation_id="manual-run-1"
    )
    
    print(f"\nClaims extracted: {len(result.claims)}")
    for i, claim in enumerate(result.claims, 1):
        print(f"\n--- Claim {i} ---")
        print(f"Label: {claim.label.value}")
        print(f"Summary: {claim.claim_summary}")
        print(f"Verbatim: {claim.claim_text_verbatim[:100]}...")
        print(f"Evidence spans: {len(claim.evidence_spans)}")

if __name__ == "__main__":
    asyncio.run(main())