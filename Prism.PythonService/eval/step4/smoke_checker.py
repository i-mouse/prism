"""CLI: one real table-checker call on a made-up table and a made-up claim (about INR 0.1). Nitin runs it once
before the paid step 4 run to see that the request shape, the response schema and the code guard work end to end.
Agents never run it.

Everything here is invented: no paper, no eval row, no real table. The pieces are written by hand, so the lister
is not called and the script makes exactly one request (plus at most one retry). Backend: AI Studio, with the key
the service already reads from its settings (.env is loaded by python-dotenv; this script never prints it).

Prints the parsed answers and the guard outcome only.

Usage (from Prism.PythonService):
  uv run python -m eval.step4.smoke_checker [--level medium]
"""
import argparse
import asyncio
import sys

MADE_UP_PAPER = (
    "Results. We compare three made-up sorting gadgets.\n"
    "Table 1: Sorting speed of the gadgets (items per minute)\n"
    "Gadget Small load Large load\n"
    "Alpha sorter 41.5 38.2\n"
    "Bravo sorter 44.0 36.9\n"
    "Charlie sorter 39.8 40.1\n"
    "Figure 1: A drawing of the gadgets.\n"
)
MADE_UP_CLAIM = "As Table 1 shows, the Bravo sorter is the fastest gadget on both the small load and the large load."
MADE_UP_PIECES = (
    ("the Bravo sorter is the fastest gadget on the small load", "pair"),
    ("the Bravo sorter is the fastest gadget on the large load", "pair"),
)


async def _run(level: str) -> int:
    from eval.step4 import table_check, table_check_calls

    blocks = table_check.build_table_blocks(MADE_UP_PAPER)
    decision = table_check.route(MADE_UP_CLAIM, (), blocks)
    print(f"tables found: {list(blocks.included)}; routed: {decision.routed} ({decision.reason})")
    print(f"checker hash: {table_check.checker_hash()}; lister hash: {table_check.lister_hash()}")
    pieces = [table_check.Piece(i, text, kind) for i, (text, kind) in enumerate(MADE_UP_PIECES, start=1)]
    try:
        answers, served = await table_check_calls.check_pieces(MADE_UP_CLAIM, pieces, blocks, level, "smoke-table-check")
    except Exception as exc:
        print(f"CHECKER CALL FAILED after retry: {exc!r}")
        return 1
    print(f"served model: {served}")
    outcomes = table_check.piece_outcomes(pieces, answers, blocks)
    for outcome in outcomes:
        print(f"piece {outcome.piece_id}: answer {outcome.answer}, state {outcome.state}, "
              f"guard {'pass' if not outcome.guard_reasons else outcome.guard_reasons}, cells {outcome.cells}")
    result = table_check.claim_result(outcomes)
    print(f"claim result: {result.label or 'fallback to the auditor'} "
          f"(failed {result.n_failed}, could-not-check {result.n_could_not_check} of {result.n_pieces})")
    print("expected for this made-up table: piece 1 backed, piece 2 not_backed, claim partially_supported")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--level", default="medium", choices=["low", "medium", "high"])
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(asyncio.run(_run(args.level)))


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    main()
