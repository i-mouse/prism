# Clean-extraction attempt - bounded score (2026-10-20)

## K1 (13 target rows, 7 stable rows; no key, no human judgement)
- clean_r1: found 5/13 (low), 5/13 (high)
- clean_r2: found 6/13 (low), 6/13 (high)
- 7 stable rows found in BOTH runs: 4/7 (low), 4/7 (high)
- verdict: FAIL

## K2 (filter never touches pass 1)
- clean_r1: retained 18/18, pass=True
- clean_r2: retained 18/18, pass=True
- verdict: PASS

## K3 (report only, docs/decisions.md 2026-10-18 - threshold r <= 1.4)
- mean reading: r=2.5037
- pooled reading: r=2.4696
- no verdict (report only)

## K4 (projected cost per paper <= INR 130)
- mean reading: projected=INR 230.52, pass=False
- pooled reading: projected=INR 227.55, pass=False
- verdict: FAIL

## K5 (pass-2 Stage-1 grounding rate >= 0.95)
- clean_r1: rate=0.9907, pass=True
- clean_r2: rate=0.9905, pass=True
- verdict: PASS

## K6 (precision, unsure as not-claim, >= 0.7)
- low: n=59, precision=0.8136, pass=True
- high: n=59, precision=0.9492, pass=True
- verdict: PASS

## K7 (not-same count, unsure as not-same, <= 1)
- low: n=60, not_same=43, pass=False
- high: n=60, not_same=18, pass=False
- verdict: FAIL

## K8 (filter spend; per-run <= INR 40, attempt total <= INR 350)
- clean_r1: filter_cost_inr=64.25, pass=False
- clean_r2: filter_cost_inr=58.31, pass=False
- attempt total: pilot INR 6.40 (docs/decisions.md 2026-10-19) + this attempt's two full runs INR 304.64 = INR 311.04, pass=True
- verdict: FAIL

## Overall: FAIL

## Labels files used (sha256)
- k6_low: 4bc4b02df0f61c390afa43379e3b14c41986a7b976ad3bc2f4b39ec4aa41d034
- k6_high: 1885f546a79f91a80c1a679d2b7f654e0c68baa0c3783f771cad09f070b84f88
- k7_low: 35c3f1532f7747e232b10f2146e167ecf7861bd8e8f03ddaa3f48e0836f1cecc
- k7_high: ae4024ed3a61180f913d2e383cc0c9bb678117978bac22c17af62cbcea640dc4
- k1: none (new method reads no labels/key file)
