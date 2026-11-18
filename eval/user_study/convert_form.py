"""Turn the two Google Form CSV downloads into one ratings.csv.        OWNER: Mani

In each form: Responses -> Link to Sheets -> File -> Download -> CSV. Then

  python -m eval.user_study.convert_form A=responses_A.csv B=responses_B.csv
  python -m eval.user_study.analyse_ratings results/user_study/ratings.csv

Each response row is one rater (named A1, A2, ... / B1, B2, ...). Columns are found by their
titles "Item N: Correctness|Clarity|Usefulness". Rows with a missing rating are skipped
and reported.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

COLUMN = re.compile(r"Item\s+(\d+)\s*:\s*(Correctness|Clarity|Usefulness)", re.I)


def convert(files: dict[str, str]) -> tuple[list[dict], list[str]]:
    out, notes = [], []
    for sheet, path in files.items():
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            cols = {}
            for name in reader.fieldnames or []:
                m = COLUMN.search(name or "")
                if m:
                    cols[name] = (int(m.group(1)), m.group(2).lower())
            if not cols:
                raise ValueError(f"{path}: no columns named 'Item N: Correctness/Clarity/Usefulness'")
            for n, row in enumerate(reader, start=1):
                rater = f"{sheet.upper()}{n}"
                per: dict[int, dict] = {}
                for name, (item, dim) in cols.items():
                    val = (row.get(name) or "").strip()
                    if val:
                        per.setdefault(item, {})[dim] = float(val)
                for item, d in sorted(per.items()):
                    if len(d) < 3:
                        notes.append(f"{rater} item {item}: incomplete, skipped")
                        continue
                    out.append(dict(rater=rater, sheet=sheet.upper(), item=item, **d))
    return out, notes


def main(argv=None):
    args = (argv if argv is not None else sys.argv[1:])
    files = dict(a.split("=", 1) for a in args if "=" in a)
    if not files:
        raise SystemExit(__doc__)
    rows, notes = convert(files)
    out = Path("results/user_study/ratings.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["rater", "sheet", "item", "correctness", "clarity", "usefulness"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out}: {len(rows)} ratings from {len({r['rater'] for r in rows})} raters")
    for n in notes:
        print("note:", n)


if __name__ == "__main__":
    main()
