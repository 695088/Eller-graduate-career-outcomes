"""Shared design matrix for the hedonic OLS and the tree-based salary models.

Skills come from alumni `skills_obtained`. Skills that are always taught
together (identical indicator columns across every alumnus) cannot be valued
separately, so each set of identical columns is merged into one "skill bundle".
Near-universal and very rare skills are dropped.
"""
import sys
from pathlib import Path

import numpy as np
import polars as pl
from sklearn.preprocessing import MultiLabelBinarizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import data  # noqa: E402

MIN_PREVALENCE = 0.02
MAX_PREVALENCE = 0.98
CATEGORICAL_CONTROLS = ["major", "location_metro", "industry_sector", "company_tier", "grad_year"]
NUMERIC_CONTROLS = ["had_internship", "gpa_final"]


def load_salary_frame() -> pl.DataFrame:
    alumni = data.load_alumni()
    tiers = data.load_company_tiers()
    frame = alumni.join(tiers, on="employer_clean", how="left").with_columns(
        company_tier=pl.col("company_tier").fill_null(3).cast(pl.Utf8),
        grad_year=pl.col("grad_year").cast(pl.Utf8),
        had_internship=pl.col("had_internship").cast(pl.Int8),
        log_salary=pl.col("starting_salary_mid").log(),
    )
    col = data.load_metro_cost_of_living()
    if col is not None:
        frame = frame.join(col, on="location_metro", how="left").with_columns(log_rpp=pl.col("rpp_index").log())
    return frame


def skill_bundles(frame: pl.DataFrame):
    """Return (bundle indicator matrix, bundle metadata) after merging identical skill columns."""
    skills = data.load_skills()
    names = dict(zip(skills["skill_id"], skills["skill_name"]))
    mlb = MultiLabelBinarizer()
    matrix = mlb.fit_transform(frame["skills_obtained"].to_list()).astype(np.int8)
    prevalence = matrix.mean(axis=0)
    keep = (prevalence >= MIN_PREVALENCE) & (prevalence <= MAX_PREVALENCE)
    ids = np.array(mlb.classes_)[keep]
    matrix = matrix[:, keep]

    groups: dict[bytes, list[int]] = {}
    for j in range(matrix.shape[1]):
        groups.setdefault(matrix[:, j].tobytes(), []).append(j)

    columns, rows = [], []
    for b, members in enumerate(sorted(groups.values(), key=lambda m: ids[m[0]]), start=1):
        member_ids = [ids[j] for j in members]
        lead = member_ids[0]
        label = names[lead] if len(members) == 1 else f"{names[lead]} (+{len(members) - 1} co-taught)"
        columns.append(matrix[:, members[0]])
        rows.append({
            "bundle_id": f"B{b:03d}",
            "bundle_label": label,
            "lead_skill_id": lead,
            "n_skills": len(members),
            "member_skill_ids": "; ".join(member_ids),
            "member_skill_names": "; ".join(names[i] for i in member_ids),
            "prevalence": round(float(matrix[:, members[0]].mean()), 4),
        })
    return np.column_stack(columns), pl.DataFrame(rows)


def find_bundle(bundles: pl.DataFrame, skill_name: str) -> str | None:
    """Bundle id containing a skill name, or None if the skill was dropped."""
    hit = bundles.filter(pl.col("member_skill_names").str.split("; ").list.contains(skill_name))
    return hit["bundle_id"][0] if len(hit) else None
