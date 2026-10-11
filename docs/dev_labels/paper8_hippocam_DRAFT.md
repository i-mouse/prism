# Paper 8 - Hippocam, "Use and Disuse" (arXiv 2610.12124v1) - DRAFT dev labels
Status: DRAFT. Labelled under docs/LABEL_RUBRIC.md before any Prism output. Verified against the PDF.
Row format: id | claim | section/page | deciding evidence | label | rule | confidence

## Refusal-family rows (3, all partial; 0 not_supported)

P8-R1 | Abstract: "a recursive prefix consolidation mechanism repeatedly consolidates earlier history, causing long-unused experiences to become increasingly abstract." Sec 1: "Experience that remains unused continues to recede in detail through recursive consolidation, without separately assigned importance scores or time-based forgetting rules." Sec 2.6: "incidental details and knowledge not currently used are retained in progressively less detail through recursive Prefix Consolidation" | Abstract p1; Sec 1 p2; Sec 2.6 p5; App A.6 Table 10 p19; App B.2.3 prompt p30 | Table 10 (ToolBench knowledge-item transitions): "No detected use" = 95.8% unchanged, 0.9% supplemented, 0.1% updated, 3.1% rewritten, 0.1% dropped. App A.6: "Most items without detected use remain unchanged (95.8%), so these adjacent-consolidation statistics do not establish general fading of unused knowledge." PALIM Step 3 prompt: consolidated knowledge "survives every later fold ... nothing is shortened out of it." Narrative does get coarser by design (Step 2 prompt "retold one grain coarser"; Fig. 7), but that follows fold age and was not measured against "unused". | partially_supported | R3 (hidden loss) | 0.70 (Reading 2 = not_supported if "experience" includes knowledge items)

P8-R2 | Sec 1: "These results demonstrate how our use-and-disuse cycle supports memory and learning through interaction history." Sec 6: "Experiments and analyses demonstrate its broad applicability and illuminate how retained knowledge evolves through use and disuse." | Sec 1 p2; Sec 6 p9; App A.6 Table 10 p19 | "Use" half is backed: used items supplemented 28.4% (call matches) and 11.7% (call differs) vs 0.9% with no detected use; updates 3.4% / 0.3% / 0.1%. "Disuse" half is not demonstrated (same A.6 concession as P8-R1). A.6 also says these associations do not establish that use alone causes the changes, and the use proxy is API-linked, not direct influence on reasoning. | partially_supported | R3 | 0.60 (shares evidence with P8-R1)

P8-R3 | Sec 4.1: "These gains demonstrate more effective learning from accumulated experience than the compared methods." | Sec 4.1 p6; Table 1 p6; Fig. 4 and Table 6 | The sentence follows Fig. 4, which tracks only the three leading methods per StreamBench stream to task 300. In Table 1, same RQ1 section, ACE (91.9) and A-Mem (87.2) beat Hippocam (81.9) on ScienceWorld. ToolBench lead over Letta at 300 tasks is 78.7 vs 77.3. | partially_supported | R3 | 0.55 (judgment call: Reading 2 = supported if "the compared methods" is read as the Fig. 4 methods only)

## Supported rows (8)

P8-S1 | "Across the three benchmarks, most methods outperform Plain, although some match or fall below it." | Table 1 p6 | Plain 78.4 / 66.9 / 69.0. 16 of 21 baseline cells above Plain, 2 equal (ReasoningBank SciWorld 66.9; HiAgent StreamBench 69.0), 3 below (HiAgent 56.7, mem0 58.6 SciWorld; ReasoningBank 68.3 StreamBench). | supported | R3 | 1.0
P8-S2 | "Its 81.9% mean ScienceWorld progress exceeds four of the six compared methods." | Table 1 | Exceeds HiAgent 56.7, mem0 58.6, Letta 71.2, ReasoningBank 66.9; trails A-Mem 87.2 and ACE 91.9. | supported | plain read | 1.0
P8-S3 | "On StreamBench, it achieves the highest mean accuracy of 81.7%, narrowly ahead of Letta's 81.3%." | Table 1 | Hippocam 81.7; Letta 81.3; next A-Mem 79.0. | supported | plain read | 1.0
P8-S4 | Hippocam 78.9% mean progress, +30.1 pp over Plain and +16.2 pp over ACE | Table 2 p7 | 78.9 - 48.8 = 30.1; 78.9 - 62.7 = 16.2. | supported | plain read | 1.0
P8-S5 | "On FEVER, Frozen scores cluster around Plain's 59.3%, with Hippocam and HiAgent reaching 61.8%." | Table 2 | HiAgent 61.8, mem0 59.9, Letta 59.9, ACE 57.9, A-Mem 55.8, ReasoningBank 55.8, Hippocam 61.8. | supported | plain read | 1.0
P8-S6 | "Only Hippocam and ACE achieve positive gains on both domain transitions" | Table 2 | Delta-stream (Sci, FEVER): Hippocam +19.2/+6.0; ACE +14.0/+2.0; HiAgent +0.1/-5.8; mem0 -28.1/0.0; A-Mem -8.0/0.0; Letta -4.8/-9.9; ReasoningBank -11.2/-2.1. | supported | R3 | 1.0
P8-S7 | "Prefix consolidation thus supports more effective subsequent work with a smaller active context." | Sec 5.1 p9; Table 4 | ToolBench 78.7 vs 65.7; ALFWorld steps 9.62 vs 11.74; context 19.7k vs 50.7k. The text carves out the one loss: "ALFWorld success remains near perfect" (97.8 vs 100.0). | supported | R3 | 0.85
P8-S8 | Disabling recall on MemoryAgentBench 64k drops accuracy 41.0% -> 27.0%; "Access to underlying evidence therefore improves reasoning beyond what the consolidated context alone supports." | Sec 5.1 p9; Table 4 | 41.0 vs 27.0 on the same post-ingestion snapshot. | supported | plain read | 0.95

## Rejected from AG (do not add as rows)
- C07 as not_supported: narrative recession is real (Step 2 prompt, Fig. 7), so partial, not not_supported.
- C33 as partial: the paper's own text carves out the ALFWorld 97.8 vs 100.0 gap ("remains near perfect").
- C04 ("without parameter updates"): true by design and demonstrated in-context; single DeepSeek-V4.1-Flash backbone is a scope note, not a clean gap.
- "broad applicability" (Sec 4.4 and Sec 6): demonstrated across 8 task sets; single-backbone point kept as an open item only.

## Open items
- P8-R1 and P8-R2 share evidence (Table 10, A.6); treat as about 1.5 independent rows when counting toward the 40.
- Sec 4.2 "Hippocam achieves larger gains of 19.2 and 6.0 pp ... with a narrower FEVER gap under the scoring sensitivity analysis (A.2)": A.2 says the sequential improvement falls from six to two points under alternative answer extraction; disclosed in the paper, so no row.
- All experiments use one backbone (DeepSeek-V4.1-Flash); no parameter-update baselines (ETO, EMPO2) were run.
- Figure-read values (GoodAI isolated/interleaved bars, Fig. 5) and the Fig. 1 "seven of eight" count were not re-verified from the PDF for this draft.
