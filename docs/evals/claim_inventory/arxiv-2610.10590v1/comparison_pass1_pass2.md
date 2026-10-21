# pass-1 vs pass-2 comparison - arxiv-2610.10590v1

Amends, per docs/decisions.md:
- "Pass-2 keep/drop rule for the 2610.10590v1 comparison - 2026-10-18"
  (thresholds unchanged: gain >= 10pp, strict precision >= 0.70)
- "Answer-key labelling and Phase B method for 2610.10590v1 - 2026-10-18"
  (matching/banding override; scored under two answer keys A and B;
  different A/B verdicts -> DROP)

Process deviation: per-arm band counts and auto-match lists were shown to
the human reviewer before borderline review (B1 report and
match_proposals.md). Impact: the borderline set was 2 rows of one
identical key/pipeline pair (K038), appearing in both pass-2 arms;
judged once, applied to both.

## Score under Key A (reconciled + disputed "claim" only)

- Recall pass 1: 0.438
- Recall raw pass 2: 0.219
- Recall filtered pass 2: 0.192
- Recall combined (pass 1 ∪ filtered pass 2): 0.630
- Recall gain (pp): 19.18
- Strict precision (filtered pass 2): 0.778
- Verdict under Key A: KEEP

## Score under Key B (reconciled + disputed "claim" + "unsure")

- Recall pass 1: 0.423
- Recall raw pass 2: 0.218
- Recall filtered pass 2: 0.192
- Recall combined (pass 1 ∪ filtered pass 2): 0.615
- Recall gain (pp): 19.23
- Strict precision (filtered pass 2): 0.833
- Verdict under Key B: KEEP

## Final verdict

**KEEP** (Key A: KEEP, Key B: KEEP -> agree)


