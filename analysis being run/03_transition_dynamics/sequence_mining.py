"""Sequential pattern mining (PrefixSpan) of alumni career sequences by major.

Each alumnus contributes an ordered sequence:
    [internship (industry), entry title, year-3 title]
(the internship item is omitted when there was none). PrefixSpan returns every
subsequence that appears in at least MIN_SUPPORT of a major's alumni; rule
confidence is support(pattern) / support(pattern without its last item).
The same mining runs on role-state sequences, which absorb title noise.
"""
import math
import sys
from pathlib import Path

import polars as pl
from prefixspan import PrefixSpan

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import data  # noqa: E402
from markov_transitions import add_states  # noqa: E402

OUT = data.outputs_dir(__file__)

MIN_SUPPORT = 0.05     # share of a major's alumni that must contain the pattern
MIN_LENGTH = 2


def sequences(df: pl.DataFrame, kind: str) -> list[list[str]]:
    seqs = []
    for row in df.iter_rows(named=True):
        intern = [f"[Intern] {row['intern_state'].removeprefix('Intern: ')}"] if row["had_internship"] else []
        if kind == "title":
            seqs.append(intern + [f"[Y0] {row['first_title']}", f"[Y3] {row['yr3_title']}"])
        else:
            seqs.append(intern + [f"[Y0] {row['entry_state']}", f"[Y3] {row['yr3_state']}"])
    return seqs


def mine(seqs: list[list[str]], group: str, kind: str) -> list[dict]:
    n = len(seqs)
    min_count = max(2, math.ceil(MIN_SUPPORT * n))
    patterns = PrefixSpan(seqs).frequent(min_count)
    support = {tuple(p): c for c, p in patterns}
    closed = PrefixSpan(seqs).frequent(min_count, closed=True)
    closed_set = {tuple(p) for _, p in closed}
    rows = []
    for count, pattern in patterns:
        if len(pattern) < MIN_LENGTH:
            continue
        prefix_support = support.get(tuple(pattern[:-1]))
        rows.append({
            "major": group,
            "sequence_type": kind,
            "pattern": " -> ".join(pattern),
            "length": len(pattern),
            "support_count": count,
            "support_pct": round(count / n, 4),
            "confidence": round(count / prefix_support, 4) if prefix_support else None,
            "is_closed": tuple(pattern) in closed_set,
        })
    return rows


def main():
    alumni = add_states(data.load_alumni())
    rows = []
    for group, sub in [("ALL", alumni), *[(m, alumni.filter(pl.col("major") == m)) for m in sorted(alumni["major"].unique())]]:
        for kind in ("title", "role_state"):
            rows.extend(mine(sequences(sub, kind), group, kind))

    result = pl.DataFrame(rows).sort("major", "sequence_type", "support_pct", descending=[False, False, True])
    result.write_csv(OUT / "frequent_sequences_by_major.csv")

    # Most frequent closed title sequences per major (closed = no longer pattern has the same support).
    top = (result.filter((pl.col("sequence_type") == "title") & pl.col("is_closed") & (pl.col("length") >= MIN_LENGTH))
           .sort("major", "support_pct", descending=[False, True]).group_by("major", maintain_order=True).head(5))
    top.write_csv(OUT / "top_title_sequences_by_major.csv")
    with pl.Config(tbl_rows=50, fmt_str_lengths=110, tbl_width_chars=200):
        print(top.select("major", "pattern", "support_pct", "confidence"))


if __name__ == "__main__":
    main()
