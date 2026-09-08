# Eval Integrity Audit (2026-09-08)

## Q1 — Where technical failures become semantic Fail

1. **Where failures become `FAIL`:** Transient errors are caught and returned as `GroundingStatus.FAIL` in `Prism.PythonService/extraction/grounding.py:243-245` (inside `_audit_span_with_llm`'s `except Exception` block).
2. **`GroundingStatus.SKIPPED`:** Yes, it exists as an enum value in `Prism.PythonService/extraction/schemas.py:35`. However, it is completely unused in the codebase today.
3. **Minimum change for `SKIPPED`:** Change the exception handler in `grounding.py:245` to return `GroundingStatus.SKIPPED, None`. Additionally, update `_build_claim_reason` and the per-claim roll-up logic in `ground_extraction` (`grounding.py:516-528`) to set the final claim's status to `SKIPPED` when the spans hit errors, rather than defaulting to `FAIL`.
4. **`matrix_runner` handling:** `matrix_runner.py` and `scorer.py` currently do not handle `SKIPPED` rows. When encountered, `scorer.py` should exclude `SKIPPED` claims from the denominators (`total_negatives` and `positive_total`) so they don't incorrectly register as false rejections or depress the refusal rate.

## Q2 — Matcher / system coupling

1. **Matcher model variable:** After the PR #52 rename, the matcher uses an isolated variable, `LLM_EVAL_MATCHER_MODEL` (`Prism.PythonService/eval/matcher.py:124`).
2. **Fallback isolation:** If the matcher falls back, it uses `LLM_EVAL_MATCHER_FALLBACK_MODEL` (`matcher.py:149`). This maintains isolation and does not leak to a system-under-test model.
3. **Fixture header structure:** The fixture header does record the matcher model separately (`dump_fixture.py:121-123`). From `docs/evals/fixtures/cot.json`:
   ```json
   "header": {
     "prompt_hash": "31021b91b11a",
     "model_name": "gemini-3.6-flash",
     "matcher_model": "gemini-3.6-flash",
     "generated_at": "2026-09-05T11:13:01.692847+00:00",
     ...
   }
   ```
4. **Proving vs. Hiding differences:** The fixture header would **hide** a fallback difference. `match()` in `matcher.py` tracks `used_model`, but does not return it. Instead, `dump_fixture.py:199` statically writes the environment variable (`os.environ["LLM_EVAL_MATCHER_MODEL"]`) to the header. If the matcher fell back to model B internally, the fixture will falsely claim it was scored by matcher A.

## Q3 — Scorer tolerance

1. **Three-value tolerance location:** The tolerance lives in `Prism.PythonService/eval/scorer.py:9` (`_REFUSAL_LABELS = {"not_supported", "partially_supported"}`) and is applied at `scorer.py:62` (`elif actual_claim.label in _REFUSAL_LABELS:`).
2. **Tolerance documentation:** Yes, it is explicitly documented in `docs/evals/matrix_eval.json:9`: "...must either (a) not emit the claim as 'supported', OR (b) emit the claim with label 'not_supported' or 'partially_supported'."
3. **Reporting two numbers:** In `scorer.py`, calculate an additional `strict_correct_refusals` metric where `actual_claim.label == row.expected_label` in the `is_negative` block. Expand `EvalReport` and `MatrixReport` to carry this metric alongside the refusal-family one, and print the resulting `strict_refusal_rate` in `matrix_runner.py`'s `_print_report`.
4. **Other silent tolerances:** Yes. For negative expectations, missing claims (`actual_claim is None`, line 54) and grounding pipeline rejections (`_was_grounded_away(actual_claim)`, line 58) both silently count as valid correct refusals (`PASS`). However, positive expectations require a strict exact match with `expected_label`.

## Q4 — Matcher gold-set test wiring

1. **Location and purpose:** `docs/evals/matcher_gold.json`. It provides 15 hand-labeled (expected, actual) claim pairs to test the correctness of the LLM-as-judge semantic matcher, ensuring it accurately catches meaning-equivalence before trusting it on real extraction data.
2. **CI wiring:** It is **not** wired into CI today; it uses the `@pytest.mark.integration` decorator, and `pyproject.toml:50` configures `pytest` to skip integration tests (`addopts = "-m 'not integration'"`). The minimum change to run it is to either remove that flag from `pyproject.toml` or explicitly run `uv run pytest eval/tests/test_matcher.py -v -m integration` as a step in the CI workflow yaml, ensuring `AI_API_KEY` is provided.
3. **Drift detection:** It only detects matcher correctness on a fixed set of 15 static pairs. It does not detect semantic drift on dynamic data or real pipeline runs.

## Proposed PR B scope
- Replace `GroundingStatus.FAIL` with `GroundingStatus.SKIPPED` in `grounding.py` for transient errors and propagate it correctly.
- Update `scorer.py` and `matrix_runner.py` to omit `SKIPPED` claims from score denominators.
- Return the `used_model` from `matcher.py:match()` so `dump_fixture.py` can record whether fallback occurred.
- Add `strict_refusal_rate` to `scorer.py` and `matrix_runner.py` to publish alongside the current family refusal rate.
- Run `eval/tests/test_matcher.py` (the integration gold-set test) explicitly on every CI push.
