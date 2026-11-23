# Prism docs

Start with the [main README](../README.md), then the [engineering report](PRISM_REPORT.md). The current state is in [report section 12](PRISM_REPORT.md#12-where-prism-stands).

## Current

| File or folder | What it is |
|---|---|
| PRISM_REPORT.md | Engineering report: pipeline, every test, results, limits, switched-off features; section 12 is the current state |
| decisions.md | Dated decision log; every paid test was pre-registered here before it ran (append-only); wins on any conflict |
| RUNBOOK.md | Local setup notes and gotchas |
| extraction-audit-grounding-architecture.md | How extraction, audit and grounding work |
| deployment-and-environment-architecture.md | Azure deployment design (decommissioned 2026-09-28; `AppHost.cs` comments cite it) |
| observability-and-cost-plan.md | Known gaps in cost, limits and monitoring (steps 3-8 not built) |
| LABEL_RUBRIC.md | Labelling rules for the eval sets (kept out of all model prompts) |
| report/ | Sourced fact sheet and field comparison |
| diagrams/ | Hero diagram and architecture diagram |
| design/ | UI design specs (`tailwind.config.ts` cites them) |

## Evidence

| Folder | What it is |
|---|---|
| evals/ | Eval sets, frozen run outputs, scores and manifests; map in [evals/README.md](evals/README.md) |
| dev_labels/ | Hand-written label drafts for the 12 dev papers |
| research_papers/ | PDFs used in the evals (third-party; see decisions.md 2026-11-21) |

Raw model outputs that contain paper text are kept outside the repo; their sha256 hashes are committed (for example evals/testb_2026-11-19/manifest.json).

## History

| Folder | What it is |
|---|---|
| archive/ | Superseded docs, kept for the record: PRISM_STATUS.md, PRODUCT_BRIEF.md, discovery/ (read-only discovery report, 2026-10-10), research/ (fact inventory, 2026-10-14), experiments/ (experiment pre-registration notes) and older files |

On 2026-11-23, PRISM_STATUS.md, PRODUCT_BRIEF.md, discovery/, research/ and experiments/ moved to archive/ with the same names. Paths to them in decisions.md and other dated records refer to the same name under docs/archive/.
