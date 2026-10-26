"""Hedonic wage regression: OLS with fixed effects.

    log(salary_i) = a + sum_s b_s * skill_bundle_is + g * internship_i + d * gpa_i
                    + FE(major) + FE(metro) + FE(industry) + FE(company tier) + FE(grad year) + e_i

exp(b_s) - 1 is the percentage salary premium of a skill bundle holding the
controls fixed; multiplied by mean salary it gives a dollar premium. Metro
fixed effects absorb regional cost of living; if common/metro_cost_of_living.csv
is filled in, a second specification replaces them with log(RPP).
Standard errors are heteroskedasticity-robust (HC1). Skill p-values are also
adjusted for multiple testing (Benjamini-Hochberg FDR).
"""
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import data  # noqa: E402
import features  # noqa: E402

OUT = data.outputs_dir(__file__)
COLLINEAR_TOL = 1e-8


def design(frame: pl.DataFrame, skills: np.ndarray, bundle_ids: list[str], use_rpp: bool):
    """Controls first, then skills, so collinearity checks drop skills rather than controls."""
    categorical = [c for c in features.CATEGORICAL_CONTROLS if not (use_rpp and c == "location_metro")]
    controls = frame.select(*categorical, *features.NUMERIC_CONTROLS, *(["log_rpp"] if use_rpp else [])).to_dummies(
        columns=categorical, drop_first=True)
    X = np.column_stack([np.ones(len(frame)), controls.to_numpy().astype(float), skills.astype(float)])
    names = ["const", *controls.columns, *bundle_ids]
    return X, names, len(names) - len(bundle_ids)


def drop_collinear(X: np.ndarray, names: list[str], n_controls: int):
    """Drop columns that are linear combinations of earlier columns (QR diagonal ~ 0).

    Columns are ordered const, controls, skills, so a redundant skill is dropped
    rather than a control. Controls can be redundant too: industry and company
    tier are both properties of the employer.
    """
    _, r = np.linalg.qr(X)
    diag = np.abs(np.diag(r))
    keep = diag > COLLINEAR_TOL * diag.max()
    keep[0] = True
    dropped = [n for n, k in zip(names, keep) if not k]
    n_controls_kept = int(keep[:n_controls].sum())
    return X[:, keep], [n for n, k in zip(names, keep) if k], dropped, n_controls_kept


def fit(frame, skills, bundles, use_rpp: bool, label: str):
    y = frame["log_salary"].to_numpy()
    X, names, n_controls = design(frame, skills, bundles["bundle_id"].to_list(), use_rpp)
    X, names, dropped, n_controls = drop_collinear(X, names, n_controls)
    model = sm.OLS(y, X).fit(cov_type="HC1")
    base = sm.OLS(y, X[:, :n_controls]).fit(cov_type="HC1")

    skill_idx = [i for i, n in enumerate(names) if n.startswith("B") and n[1:].isdigit()]
    restriction = np.zeros((len(skill_idx), len(names)))
    restriction[np.arange(len(skill_idx)), skill_idx] = 1
    joint = model.wald_test(restriction, use_f=True, scalar=True)

    mean_salary = float(frame["starting_salary_mid"].mean())
    coef = pl.DataFrame({
        "term": names, "coef": model.params, "se": model.bse, "t": model.tvalues, "p_value": model.pvalues,
        "ci_low": model.conf_int()[:, 0], "ci_high": model.conf_int()[:, 1],
    }).with_columns(
        pct_premium=(pl.col("coef").exp() - 1),
        dollar_premium=(pl.col("coef").exp() - 1) * mean_salary,
    )
    bundle_ids = bundles["bundle_id"].to_list()
    skill_coef = coef.filter(pl.col("term").is_in(bundle_ids))
    q = multipletests(skill_coef["p_value"].to_numpy(), method="fdr_bh")[1]
    skill_coef = (skill_coef.with_columns(q_value_fdr=q).rename({"term": "bundle_id"})
                  .join(bundles, on="bundle_id").sort("dollar_premium", descending=True))
    control_coef = coef.filter(~pl.col("term").is_in(bundle_ids) & (pl.col("term") != "const"))

    summary = {
        "specification": label,
        "n": int(model.nobs),
        "r_squared": round(model.rsquared, 4),
        "adj_r_squared": round(model.rsquared_adj, 4),
        "controls_only_r_squared": round(base.rsquared, 4),
        "mean_starting_salary": round(mean_salary, 2),
        "n_skill_bundles_estimated": len(skill_idx),
        "columns_dropped_collinear": dropped,
        "joint_test_all_skills_zero": {"F": round(float(joint.statistic), 4), "p_value": float(joint.pvalue),
                                       "df_num": int(joint.df_num), "df_denom": int(joint.df_denom)},
        "n_skill_bundles_q_below_0.05": int((skill_coef["q_value_fdr"] < 0.05).sum()),
    }
    return skill_coef, control_coef, summary


def main():
    frame = features.load_salary_frame()
    skills, bundles = features.skill_bundles(frame)
    bundles.write_csv(OUT / "skill_bundles.csv")

    specs = [(False, "metro_fixed_effects")]
    if "log_rpp" in frame.columns:
        specs.append((True, "log_rpp_cost_of_living"))

    summaries = []
    for use_rpp, label in specs:
        skill_coef, control_coef, summary = fit(frame, skills, bundles, use_rpp, label)
        round_cols = [pl.col(c).round(5) for c in ("coef", "se", "t", "ci_low", "ci_high", "pct_premium")] + [pl.col("dollar_premium").round(0)]
        skill_coef.with_columns(round_cols).write_csv(OUT / f"hedonic_skill_premiums_{label}.csv")
        control_coef.with_columns(round_cols).write_csv(OUT / f"hedonic_controls_{label}.csv")
        summaries.append(summary)
        with pl.Config(tbl_rows=25, fmt_str_lengths=45, tbl_width_chars=200):
            print(json.dumps(summary, indent=2))
            print(control_coef.select("term", "coef", "p_value", "dollar_premium"))
            print(skill_coef.select("bundle_label", "prevalence", "dollar_premium", "p_value", "q_value_fdr").head(10))

    (OUT / "hedonic_model_summary.json").write_text(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
