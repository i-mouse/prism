# Audit: Chat Contradicts Label (2026-09-10)

## 1. Data Flow & The Disconnect
The database correctly stores the ground truth: the claim's `label` is `not_supported`, the claim's `grounding_status` is `Fail`, and the individual citation attempts in `evidence_spans` failed validation.

However, the context block passed to the LLM drops critical validation context. 
In `Prism.PythonService/paper_chat/tools.py` (`query_paper_claims`), the tool returns the raw `evidence_spans` array from the database. 
Then, in `Prism.PythonService/paper_chat/agent.py` (`_build_context_block`, lines 382-386), the context is formatted for the LLM:
```python
            evidence_text = "; ".join(
                f'"{e.get("source_text", "")}" ({e.get("source_section") or "unknown section"})'
                for e in (c.get("evidence_spans") or [])[:2]
            ) or "none"
```
This loop only extracts `source_text` and `source_section` from the spans. It **omits the span-level `grounding_status`**. 
The LLM is handed the raw, unverified quote strings (which we know failed RapidFuzz validation) under the heading `evidence: "..."`. It receives no signal that these specific text snippets were rejected as hallucinations by the grounding pipeline.

## 2. Root Cause: System Prompt Contradiction
While the context block omits the span-level failure flag, it *does* include the claim-level `label="not_supported"`, `grounding_status="Fail"`, and the `reason`. So why does the LLM ignore the `not_supported` label and answer "supported"?

The root cause lies in the system prompt instructions in `agent.py` (`generate_response`, lines 442-444):
> *"The one exception is evidence text itself: when the user asks for evidence, quote the listed evidence spans verbatim, since that's the paper's own words, not internal metadata."*

This instruction actively forces the LLM to trust the `evidence_text` blindly. When the LLM evaluates Claim 25, it sees `label="not_supported"` and `reason="auditor's cited passages do not appear..."`, but it also sees concrete Table 3 numbers in the `evidence_text`. Because the prompt explicitly commands the LLM that the evidence text is "the paper's own words", the LLM resolves the contradiction by trusting the concrete "paper words" over the metadata label, overriding the system's verdict.

## 3. Claim 25 Trace
For claim 25, the context block built by `_build_context_block` looked exactly like this:
```text
- Claim 25 (claim_id=...) label=not_supported grounding_status=Fail missing=False reason=auditor's cited passages do not appear in the paper as quoted
  summary: [Summary]
  verbatim: "[Verbatim Claim]"
  evidence: "[Hallucinated Table 3 quote]" (Table 3)
```
The `label="not_supported"` was literally present. The LLM ignored it because the prompt instructed it that the evidence line is incontrovertibly "the paper's own words", causing it to re-derive its own verdict based on the hallucinated quotes.

## 4. Scope: Systemic
This is not specific to claim 25. This is a **systemic flaw** that will occur for *any* `not_supported` claim where the auditor generated plausible-looking but hallucinated quotes. Because the grounder's rejection (the span-level `Fail` status) is stripped from the LLM context, and the prompt insists the quotes are real, the chat agent will reliably contradict the UI and defend the hallucinated evidence.

## 5. Proposed Fix
This requires fixing both the data payload and the prompt instruction:
1. **Expose per-span grounding status:** Update `_build_context_block` in `agent.py` to include the span's verification state, e.g., `"{source_text}" (Status: {span_grounding_status}, {source_section})`. If a span failed, the LLM must see that it failed.
2. **Strengthen the prompt:** Remove the dangerous "that's the paper's own words" assumption. Add an explicit instruction: *"If a claim's label is not_supported, or its evidence spans failed grounding, you MUST state that the claim is unsupported. Do not re-evaluate or trust evidence text that the system has marked as Fail."*
