# State of the Repo Audit: Prism
Date: 2026-09-11

## Phase 1: Discovery
- Executed `git log --oneline -20` and `git log --stat` to extract today's merged PRs.
- Reviewed `docs/decisions.md`, `docs/PRODUCT_BRIEF.md`, and `README.md`.
- Read `docs/evals/matrix_eval.json` and `docs/evals/golden_eval.json`.
  - `matrix_eval.json` has 37 claims evaluated, with 14 designated as grounding-negative.
  - `golden_eval.json` has 21 total questions, with 3 designated as grounding-negative.
- Confirmed definitions in `eval/scorer.py`:
  - `refused_by_label`: Model explicitly labeled claim as `not_supported` or `partially_supported` (even if it doesn't strictly match the expected refusal tier).
  - `refused_by_omission`: Extractor completely omitted the claim (which functions as a safety refusal).
  - `positive_hits`: Claim correctly matched expected `supported` label without being grounded away.
- Checked `logs/eval/` and extracted exact numbers from the most recent fixture-sourced matrix runner log (`matrix_20260910T090839.json`).
- Verified live deploy state at the Azure URL. It successfully serves the `prism-web` React frontend, though login/Google Auth claims in the README appear out-of-sync with recent auth-related PR merges.

## Phase 2: Numbers Reconciliation

| Source | Date/Commit | Refusal Fraction | refused_by_label | refused_by_omission | positive_hits | Denominator | Source Type | Current |
|--------|-------------|------------------|------------------|---------------------|---------------|-------------|-------------|---------|
| `README.md` | `961d727` (2026-09-10) | 11/14 (79%) | 4 | 7 | 10 | 14 | Unknown | No |
| `matrix_20260910T090839.json` | 2026-09-10T09:08:39 | 11/14 (78.57%) | 5 | 6 | 11 | 14 | fixture-sourced | Yes |
| `docs/decisions.md` (Slice 2.8) | 2026-08-27 | 10/14 (71%) | N/A | N/A | 16 | 14 | db-sourced (assumed) | No |
| `docs/decisions.md` (v4.1) | 2026-08-20 | 13/14 (93%) | 2 | 11 (implied) | 15 | 14 | db-sourced (assumed) | No |

**Exact current fractions (from `logs/eval/matrix_20260910T090839.json`):**
- **Refusal-family fraction:** 11/14 (78.57%)
- **Strict (by_label only) fraction:** 3/14 (21.4%) 
*(Note: 5 rows were refused by having a refusal-family label, but only 3 strictly matched their exact expected refusal tier).*

## Phase 3: Contradiction Audit

- **PRODUCT_BRIEF vs. decisions.md:** `PRODUCT_BRIEF.md` defines Tier 2 as "Multi-paper Chat" and Tier 3 as "Web-grounded Chat". However, `decisions.md` (2026-08-22 entry) reveals that Tier 2 was originally "Verdict view" and Tier 3 was "Overstated Claims + Questions", and both were collapsed into paper-scoped chat. The Product Brief has redefined these tiers without leaving historical traceability of the collapse.
- **Missing Sections:** `PRODUCT_BRIEF.md` entirely lacks a "Build Order" section. `README.md` entirely lacks a "Roadmap" section.
- **"Not Built" vs. Merged:** `README.md` claims "Google Sign-In: Coming soon. Google authentication is currently under development." However, `git log` shows that `Feature/login page (#48)` and `fix(python): Entra token refresh... (#51)` have already been merged.

## Phase 4: Artifact Inventory

- **Live URL:** `https://prism-ai-reactui.nicesky-c6f0b846.centralindia.azurecontainerapps.io/` (Currently rendering the React App `prism-web`).
- **Screenshots:**
  - `docs/diagrams/matrix-view.png`
  - `docs/diagrams/matrix-view-edited.png`
  - `docs/diagrams/architecture.png`
  - `docs/diagrams/current.png`
  - `docs/diagrams/target.png`
  - `docs/design/PRISM_UI_DESIGN_SAMPLE_V2.png`
- **Verbatim PR Titles (Today's PRs):**
  - `fix(chat): add total claim count to context on every turn (#60)`
  - `fix(chat):  chat rendering, retrieval, and two UI gaps found in live testing. (#59)`
  - `fix(eval): raise claim-count ceiling, add table-claim examples (#58)`
  - `fix(extraction): catch positioning claims previously omitted (#57)`
  - `Eval harness: matcher gold-set verification frozen into fixtures (secretless CI) (#56)`
  - `Eval integrity: SKIPPED status, matcher provenance (#55)`
- **Versioned Prompt Hash:** `0bcf9d44e619`
- **Models Currently in Use:**
  - Extraction: `gemini-3.6-flash` (fallback: `gemini-3.1-flash-lite`)
  - Claim Audit: `gemini-3.6-flash` (fallback: `gemini-3.1-flash-lite`)
  - Grounding: `groq/openai/gpt-oss-20b` (fallback: `gemini/gemini-3.1-flash-lite`)
  - Chat: `gemini-3.6-flash`
  - Router/Summary: `gemini-3.5-flash-lite`

## Flags for Claude

- **Metric Drift:** The `README.md` correctly quotes the 11/14 refusal count but uses slightly stale numbers for its components (4 by_label, 7 by_omission, 10 positive hits). The latest run actually achieved 5 by_label, 6 by_omission, and 11 positive hits.
- **Tier Redefinition:** The Product Brief silently rewrote history. Tier 2/3 used to mean discrete UI cards, but were scrapped. The brief now uses Tier 2/3 to refer to future "North-Star" features (Multi-paper / Web chat) — ensure the blog post aligns with this new framing rather than the old one.
- **Missing Roadmap/Build Order:** The requested Roadmap and Build Order sections do not exist in their respective documents, so any references to them in the walkthrough script need to be omitted or adapted.
- **Auth Reality:** The README still says Google auth is "coming soon", but a login page and Entra token refresh were recently merged. The blog shouldn't parrot the README's "not built" disclaimer if auth is actually live.
- **Strict vs Family Refusal:** The exact strict `by_label` correctness is only 3/14 (21.4%). The 11/14 (78.57%) number is the "refusal-family rate" (omissions + partials + strict match). The blog should be careful to frame the 78% as the overall safety/refusal rate, not the "perfect auditor reasoning" rate.
