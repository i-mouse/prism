# Chat Refusal Bug Audit - 2026-09-10

## Overview
This document outlines the root causes and proposed minimal fixes for the three chat inconsistencies observed during testing with the `react.pdf` paper.

## 1. Wrong Refusal Answer ("There are no refused claims")
**Root Cause:**
When the user asks "Show me the strongest refusals", the router LLM interprets it as a topical FTS search (`claim_lookup="query"`) rather than a metadata filter (`claim_lookup="label_filter"`). This occurs because the prompt examples for `label_filter` ("which claims are refused?") don't strongly capture variations like "strongest refusals". 
Consequently, `execute_tools` runs `query_paper_claims` in full-text search mode for the string "strongest refusals". Since the word "refusal" exists only in the claim metadata (`label="not_supported"`) and not in the claim text itself, FTS returns 0 claims. 
The request avoids being outright rejected by `check_empty` because `query_paper_chunks` matches raw text in the paper containing the word "refusal". The request proceeds to `generate_response` with `claims=[]` and `chunks=[...]`. Seeing an empty claim list, the LLM hallucinates the response "There are no refused (unsupported) claims retrieved for this paper."

**File citations:**
- `Prism.PythonService/paper_chat/agent.py:114` (`RetrievalRoute` prompt)
- `Prism.PythonService/paper_chat/tools.py:194` (FTS query logic missing metadata hits)

**Proposed Minimal Fix:**
In `agent.py`, update the `claim_lookup` description in `RetrievalRoute` to better capture these variations. For example:
```python
"e.g. 'which claims are refused?', 'show me refusals', 'unsupported claims', 'any supported claims?' - set claim_label_filter to 'supported', 'partially_supported', or 'not_supported' to match."
```

## 2. Wrong Total Claim Count (25 instead of 28)
**Root Cause:**
When the user asks "total claims?", the router correctly assigns `claim_lookup="all"`, executing the `mode="all"` branch in `query_paper_claims`. However, this lookup mode enforces a hard limit of 25 claims via `_METADATA_LOOKUP_LIMIT`. Since the paper has 28 claims, the final 3 claims are silently truncated, causing the LLM to confidently report 25 total claims.

**File citations:**
- `Prism.PythonService/paper_chat/tools.py:107` (`_METADATA_LOOKUP_LIMIT = 25`)
- `Prism.PythonService/paper_chat/tools.py:217` (`LIMIT {_METADATA_LOOKUP_LIMIT}`)

**Proposed Minimal Fix:**
Increase `_METADATA_LOOKUP_LIMIT` to a slightly higher safe value (e.g., 50 or 100) to accommodate larger, realistic claim sets without blowing out the context window.
```python
_METADATA_LOOKUP_LIMIT = 50
```

## 3. Bad Formatting (Dense Paragraph)
**Root Cause:**
The `generate_response` prompt instructions tell the LLM to list claims "one per line in the form 'Claim N - summary. [claim:ID]'". Because the instruction omits Markdown list bullets (e.g., `- `) and explicitly discourages newlines without them, the LLM outputs consecutive lines of text. The frontend's Markdown renderer treats consecutive bullet-less text lines as a single continuous paragraph, resulting in an unreadable wall of text containing inline pills.

**File citations:**
- `Prism.PythonService/paper_chat/agent.py:443` (Formatting instruction for multiple claims)
- `Prism.PythonService/paper_chat/agent.py:455` (Formatting instruction for exact count lists)

**Proposed Minimal Fix:**
Modify the `generate_response` system instruction in `agent.py` to explicitly require Markdown bullet points when listing claims. Change the required format from `"Claim N - ..."` to `"- Claim N - ..."`.
```python
"When listing multiple claims, give one bullet per claim in the form \"- Claim N - <summary...>. [claim:<claim_id>]\""
# and
"then list them one per line in the \"- Claim N - summary. [claim:ID]\" form"
```

## Conclusion
The three symptoms do **not** share a single root cause; they are three distinct bugs across the router prompt, the database query limit, and the formatting instruction prompt. The provided minimal fixes address each issue individually and safely.
