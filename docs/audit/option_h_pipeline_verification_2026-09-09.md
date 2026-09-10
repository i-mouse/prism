# Audit: Option H Pipeline Verification (2026-09-09)

## Q1 — Three-call Trace

The extraction pipeline indeed consists of three distinct sequential calls, wired in `Prism.PythonService/extraction/engine.py`.

1. **Extractor Call** (`engine.py` line 413, inside `extract_claims`):
   - **Prompt**: `build_gemini_messages_for_extractor` (which loads `extract_claims_system.md`).
   - **Schema**: **None**. It calls `_call_gemini_json` which uses `response_mime_type="application/json"` but does *not* provide a `response_schema`.

2. **Auditor Call** (`engine.py` line 370, inside `_audit_and_structure_claim`):
   - **Prompt**: `build_gemini_messages_for_audit` (which loads `audit_claim_system.md`).
   - **Schema**: **None**. It calls `_call_gemini_freetext` to generate plain prose.

3. **Structurer Call** (`engine.py` line 383, inside `_audit_and_structure_claim`):
   - **Prompt**: `build_gemini_messages_for_structure` (which loads `structure_verdict_system.md`).
   - **Schema**: `ClaimLLM`. It calls `_call_gemini_structured` and explicitly passes `response_schema=ClaimLLM`.

## Q2 — Who Sets `label`?

The **Auditor (Call 2)** decides the label. It emits a free-text string ending in `VERDICT: <label>` (e.g., `VERDICT: partially_supported`).

The **Structurer (Call 3)** is what actually populates the `label` field of the `ClaimLLM` JSON object by parsing the Auditor's free-text output. 

The Extractor never sees or emits the `label` field. It only emits `claim_text_verbatim` and `claim_summary`.

## Q3 — Extractor's `response_schema`

The Extractor call does **not** use `response_schema=ClaimLLM`. As seen in `engine.py` line 413, the extractor uses `_call_gemini_json`, which omits the Pydantic schema enforcement. It is completely free to output the 2-field JSON object requested in its prompt without being forced to hallucinate a `label`.

## Q4 — Verdict on the Contradiction

**NOT REAL.** 

The previous audit's claim of a contradiction is based on a misreading of the codebase. It assumed that because `ClaimLLM` (which requires a `label`) is the dataclass representing an extracted claim, it must be the schema passed to the extractor prompt.

In reality, the extractor call deliberately avoids `ClaimLLM` to prevent exactly this contradiction. The `ClaimLLM` schema is strictly reserved for the Structurer (Call 3), which runs *after* the auditor has already made its free-text verdict. There is no contradiction; the pipeline is working exactly as designed.

## Q5 — The Hedging Question

The hedging (`partially_supported` instead of `not_supported`) happens in the **Auditor (Call 2)**, and it is explicitly instructed to do so by its prompt (`prompts/audit_claim_system.md`).

The prompt is deliberately lenient toward generalization claims. In Step 4, it defines `partially_supported` as follows:

> "VERDICT: partially_supported — the paper supports part of the claim but not all of it, OR supports it but narrows/caveats it elsewhere, **OR uses broader language than the experimental scope justifies.**"

The final clause — *"OR uses broader language than the experimental scope justifies"* — directly instructs the auditor to categorize Pattern A and Pattern B trap claims (which are generalizations without sufficient test scope) as `partially_supported` rather than `not_supported`. This is why the strict golden eval fails (3/14) while the family eval passes (11/14).

## Q6 — Cross-Language Ripple for `claim_type`

If we proceed with the schema fix (adding `claim_type: Literal["empirical", "positioning"]`), we must update the following files across the Python, C#, and React stack to prevent serialization breakage (similar to the `GroundingStatus.Partial` rollout):

**Python:**
- `Prism.PythonService/extraction/schemas.py`: Add `claim_type` to `ClaimLLM` and `ClaimFinal`.

**C# / .NET:**
- `Prism.ApiService/Data/Schemas/PaperClaim.cs`: Add `public ClaimType Type { get; set; }`
- `Prism.ApiService/Data/Schemas/ClaimType.cs` (New File): Define the `ClaimType` enum.
- `Prism.ApiService/Data/Converters/ClaimTypeConverter.cs` (New File): Create a `ValueConverter` mapping the C# enum to Postgres snake_case strings.
- `Prism.ApiService/Data/PrismDBContext.cs`: Register the converter inside `OnModelCreating` (`entity.Property(x => x.Type).HasConversion(new ClaimTypeConverter());`).

**React / TypeScript:**
- `Prism.Web/src/types/api.ts`: Define `export type ClaimType = "empirical" | "positioning";` and add `type: ClaimType` to the `ClaimDto` interface.
- `Prism.Web/src/lib/claimMeta.tsx` (and potentially UI components like `ClaimCard.tsx`): Update to accommodate or display the new type.
