"""First-order Markov transition analysis of alumni careers.

Each alumnus is observed at three points: internship (t0), first job (t1), and
36 months later (t2). Noisy raw titles are mapped to latent role states
(Individual Contributor, Client-Facing Operator, Functional Lead; see
common/data.py ROLE_STATE_RULES) and also kept as normalized titles.

Outputs transition matrices, the highest-probability paths out of each entry
role by major, springboard / dead-end classification of entry roles, an
absorbing-chain projection, and a test of the first-order Markov assumption.
"""
import sys
from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import chi2, chi2_contingency, norm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import data  # noqa: E402

OUT = data.outputs_dir(__file__)

STATES = [state for state, _ in data.ROLE_STATE_RULES]
ABSORBING_STATE = "Functional Lead"
TOP_PATHS_PER_ENTRY = 3
SIGNIFICANCE = 0.05
PERIOD_YEARS = 3          # one observed transition spans 36 months
PROJECTION_PERIODS = 3    # project 3, 6 and 9 years out


def wilson_interval(k: np.ndarray, n: np.ndarray, z: float = 1.96):
    p = np.where(n > 0, k / np.maximum(n, 1), 0)
    denom = 1 + z**2 / np.maximum(n, 1)
    centre = (p + z**2 / (2 * np.maximum(n, 1))) / denom
    half = z * np.sqrt(p * (1 - p) / np.maximum(n, 1) + z**2 / (4 * np.maximum(n, 1) ** 2)) / denom
    return np.clip(centre - half, 0, 1), np.clip(centre + half, 0, 1)


def add_states(alumni: pl.DataFrame) -> pl.DataFrame:
    employer_industry = dict(alumni.select("employer_clean", "industry_sector").unique("employer_clean").iter_rows())
    return alumni.with_columns(
        intern_state=pl.when(pl.col("had_internship"))
        .then(pl.lit("Intern: ") + pl.col("internship_employer").replace_strict(employer_industry, default="Other"))
        .otherwise(pl.lit("No internship")),
        entry_state=pl.col("first_title").map_elements(data.role_state, return_dtype=pl.Utf8),
        yr3_state=pl.col("yr3_title").map_elements(data.role_state, return_dtype=pl.Utf8),
    )


def transition_table(df: pl.DataFrame, src: str, dst: str, group_cols: list[str]) -> pl.DataFrame:
    """Long-format transition probabilities P(dst | src) with Wilson 95% intervals."""
    counts = df.group_by(*group_cols, src, dst).len("n")
    counts = counts.with_columns(n_from=pl.col("n").sum().over(*group_cols, src))
    lo, hi = wilson_interval(counts["n"].to_numpy(), counts["n_from"].to_numpy())
    return counts.with_columns(
        p=(pl.col("n") / pl.col("n_from")).round(4), p_ci_low=lo.round(4), p_ci_high=hi.round(4)
    ).rename({src: "from_state", dst: "to_state"}).sort(*group_cols, "from_state", "p", descending=[False] * (len(group_cols) + 1) + [True])


def classify_entry_roles(df: pl.DataFrame) -> pl.DataFrame:
    """Springboard vs dead-end: compare each entry title's promotion rate with its major's."""
    major_rate = df.group_by("major").agg(major_promo_rate=pl.col("promoted_within_3yr").mean(), major_n=pl.len())
    roles = (
        df.group_by("major", "first_title", "entry_state").agg(
            n=pl.len(),
            promo_rate=pl.col("promoted_within_3yr").mean(),
            stay_prob=(pl.col("first_title") == pl.col("yr3_title")).mean(),
            p_to_lead=(pl.col("yr3_state") == ABSORBING_STATE).mean(),
            median_months_to_promo=pl.col("months_to_promo").median(),
        ).join(major_rate, on="major")
    )
    # Two-proportion z-test of the entry role against the rest of its major.
    k = (roles["promo_rate"] * roles["n"]).to_numpy()
    n = roles["n"].to_numpy()
    k_rest = (roles["major_promo_rate"] * roles["major_n"]).to_numpy() - k
    n_rest = roles["major_n"].to_numpy() - n
    pooled = (k + k_rest) / (n + n_rest)
    se = np.sqrt(pooled * (1 - pooled) * (1 / n + 1 / np.maximum(n_rest, 1)))
    z = (k / n - k_rest / np.maximum(n_rest, 1)) / np.where(se > 0, se, np.inf)
    p = 2 * norm.sf(np.abs(z))
    label = np.where((p < SIGNIFICANCE) & (z > 0), "Springboard",
                     np.where((p < SIGNIFICANCE) & (z < 0), "Absorbing / dead-end", "Typical"))
    return roles.with_columns(
        z_vs_rest_of_major=z.round(3), p_value=p, classification=label,
        promo_rate=pl.col("promo_rate").round(4), stay_prob=pl.col("stay_prob").round(4),
        p_to_lead=pl.col("p_to_lead").round(4), major_promo_rate=pl.col("major_promo_rate").round(4),
    ).drop("major_n").sort("major", "z_vs_rest_of_major", descending=[False, True])


def absorbing_projection(df: pl.DataFrame, group: str) -> list[dict]:
    """Treat the 36-month role-state matrix as time-homogeneous with Functional Lead absorbing.

    Q = transitions among transient states, N = (I - Q)^-1 is the fundamental
    matrix; N @ 1 is the expected number of periods before reaching the lead state.
    """
    P = np.zeros((len(STATES), len(STATES)))
    counts = df.group_by("entry_state", "yr3_state").len("n")
    for a, b, n in counts.iter_rows():
        P[STATES.index(a), STATES.index(b)] += n
    P[STATES.index(ABSORBING_STATE)] = 0
    P[STATES.index(ABSORBING_STATE), STATES.index(ABSORBING_STATE)] = 1
    row_sums = P.sum(axis=1, keepdims=True)
    P = np.divide(P, row_sums, out=np.eye(len(STATES)), where=row_sums > 0)

    transient = [i for i, s in enumerate(STATES) if s != ABSORBING_STATE]
    Q = P[np.ix_(transient, transient)]
    N = np.linalg.pinv(np.eye(len(transient)) - Q)
    expected_periods = N.sum(axis=1)

    start = np.zeros(len(STATES))
    for s, n in df.group_by("entry_state").len().iter_rows():
        start[STATES.index(s)] = n
    start /= start.sum()

    rows = []
    for i, t in enumerate(transient):
        observed = df.filter(pl.col("entry_state") == STATES[t])
        value = round(float(expected_periods[i] * PERIOD_YEARS), 2) if len(observed) else None
        rows.append({"group": group, "metric": "expected_years_to_lead", "state": STATES[t],
                     "value": value, "n_observed": len(observed)})
    dist = start
    for k in range(1, PROJECTION_PERIODS + 1):
        dist = dist @ P
        for s, share in zip(STATES, dist):
            rows.append({"group": group, "metric": f"projected_share_year_{k * PERIOD_YEARS}", "state": s,
                         "value": round(float(share), 4), "n_observed": len(df)})
    return rows


def markov_property_test(df: pl.DataFrame, group: str) -> dict:
    """Does the internship (t0) still predict the year-3 state once the entry state (t1) is known?

    Sums per-stratum chi-square statistics of intern_state x yr3_state within each
    entry state; under the first-order Markov null the total is chi-square with
    the summed degrees of freedom.
    """
    total_chi2, total_dof = 0.0, 0
    for _, stratum in df.group_by("entry_state"):
        table = stratum.with_columns(interned=pl.col("had_internship").cast(pl.Utf8)).pivot(
            on="yr3_state", index="interned", values="alumni_id", aggregate_function="len").fill_null(0)
        matrix = table.drop("interned").to_numpy()
        if matrix.shape[0] > 1 and matrix.shape[1] > 1:
            stat, _, dof, _ = chi2_contingency(matrix, correction=False)
            total_chi2 += stat
            total_dof += dof
    p = chi2.sf(total_chi2, total_dof) if total_dof else None
    return {"group": group, "chi2": round(total_chi2, 3), "dof": total_dof, "p_value": p,
            "first_order_assumption": None if p is None else ("rejected" if p < SIGNIFICANCE else "not rejected")}


def main():
    alumni = add_states(data.load_alumni())
    pooled = alumni.with_columns(major=pl.lit("ALL"))
    both = pl.concat([alumni, pooled])

    # Role-state matrices for each step, by major and pooled.
    pl.concat([
        transition_table(both, "intern_state", "entry_state", ["major"]).with_columns(step=pl.lit("t0 internship -> t1 entry")),
        transition_table(both, "entry_state", "yr3_state", ["major"]).with_columns(step=pl.lit("t1 entry -> t2 year 3")),
    ]).write_csv(OUT / "role_state_transition_matrices.csv")

    # Title-level paths out of each entry role: the data behind a state diagram.
    titles = transition_table(both.with_columns(
        from_title_state=pl.col("entry_state"), to_title_state=pl.col("yr3_state")),
        "first_title", "yr3_title", ["major"])
    states = alumni.select(pl.col("first_title").alias("from_state"), pl.col("entry_state").alias("from_role_state")).unique()
    to_states = alumni.select(pl.col("yr3_title").alias("to_state"), pl.col("yr3_state").alias("to_role_state")).unique()
    edges = (titles.join(states, on="from_state", how="left").join(to_states, on="to_state", how="left")
             .with_columns(path_rank=pl.col("p").rank("ordinal", descending=True).over("major", "from_state"))
             .sort("major", "from_state", "path_rank"))
    edges.write_csv(OUT / "title_transition_edges.csv")
    edges.filter(pl.col("path_rank") <= TOP_PATHS_PER_ENTRY).write_csv(OUT / "top_paths_out_of_entry_roles.csv")

    classify_entry_roles(alumni).write_csv(OUT / "entry_role_springboard_classification.csv")

    projection, tests = [], []
    for group, sub in [("ALL", alumni), *[(m, alumni.filter(pl.col("major") == m)) for m in sorted(alumni["major"].unique())]]:
        projection.extend(absorbing_projection(sub, group))
        tests.append(markov_property_test(sub, group))
    pl.DataFrame(projection).write_csv(OUT / "absorbing_chain_projection.csv")
    pl.DataFrame(tests).write_csv(OUT / "markov_property_tests.csv")

    with pl.Config(tbl_rows=30, fmt_str_lengths=40, tbl_width_chars=200):
        print(transition_table(pooled, "entry_state", "yr3_state", ["major"]).drop("major"))
        print(pl.DataFrame(tests))


if __name__ == "__main__":
    main()
