"""CLI: locks a clean-extraction attempt's hand-filled K1 or K6/K7 sheet(s)
(hash-pins them under lock.json) so eval/score_clean.py can verify they were
not edited after locking - same discipline eval/exp3_b4.py's own `lock`
subcommand uses (eval.blind_review.write_lock), reused here rather than
reimplemented.

Validates each row against its pydantic model before locking, so a
malformed hand-filled cell is caught now rather than at scoring time.

Usage:
  uv run python -m eval.lock_clean k1 --dir docs/evals/clean_k1/clean_r1
  uv run python -m eval.lock_clean k6k7 --dir docs/evals/clean_k6k7/clean_r1
"""
import argparse
import csv
from pathlib import Path

from pydantic import ValidationError

from eval.blind_review import C1Answer, K6Answer, K7Answer, write_lock


def _read_csv_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _validate(path: Path, model) -> list[str]:
    errors = []
    for row in _read_csv_rows(path):
        try:
            model.model_validate(row)
        except ValidationError as exc:
            errors.append(f"{row.get('id', row.get('row_id', '?'))}: {exc}")
    return errors


def cmd_k1(args: argparse.Namespace) -> None:
    csv_path = args.dir / "k1_adjudication.csv"
    errors = _validate(csv_path, C1Answer)
    if errors:
        print("lock FAILED:")
        for err in errors:
            print(f"  - {err}")
        raise SystemExit(1)
    write_lock({"k1_adjudication.csv": csv_path}, args.dir / "lock.json")
    print(f"lock OK - wrote {args.dir / 'lock.json'}")


def cmd_k6k7(args: argparse.Namespace) -> None:
    k6_path = args.dir / "k6_sheet.csv"
    k7_path = args.dir / "k7_sheet.csv"
    errors = _validate(k6_path, K6Answer) + _validate(k7_path, K7Answer)
    if errors:
        print("lock FAILED:")
        for err in errors:
            print(f"  - {err}")
        raise SystemExit(1)
    write_lock({"k6_sheet.csv": k6_path, "k7_sheet.csv": k7_path}, args.dir / "lock.json")
    print(f"lock OK - wrote {args.dir / 'lock.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    k1_parser = subparsers.add_parser("k1")
    k1_parser.add_argument("--dir", type=Path, required=True)
    k1_parser.set_defaults(func=cmd_k1)

    k6k7_parser = subparsers.add_parser("k6k7")
    k6k7_parser.add_argument("--dir", type=Path, required=True)
    k6k7_parser.set_defaults(func=cmd_k6k7)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
