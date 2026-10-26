"""Non-linear salary models with SHAP skill valuation.

XGBoost and Random Forest regressors predict starting salary (dollars) from the
same skill bundles and controls as the hedonic OLS. 5-fold cross-validation
compares them against a linear baseline. SHAP values from XGBoost's built-in
TreeSHAP (pred_contribs / pred_interactions) split each prediction into
per-feature dollar contributions, and SHAP interaction values measure whether a
skill is worth more alongside another (e.g. SQL with Excel vs. SQL with Tableau).
"""
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold, cross_validate

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import data  # noqa: E402
import features  # noqa: E402

OUT = data.outputs_dir(__file__)

SEED = 42
CV_FOLDS = 5
INTERACTION_SAMPLE = 1500
TOP_INTERACTIONS = 25
# Skill pairs to test explicitly. A pair is skipped with a reason when a skill
# has no variation in the data or both skills are always taught together.
SKILL_PAIRS = [
    ("SQL", "Microsoft Excel"),
    ("SQL", "Tableau"),
    ("SQL", "Database Management"),
    ("SQL", "Optimization Modeling"),
    ("Database Management", "Optimization Modeling"),
]
XGB_PARAMS = {"n_estimators": 400, "max_depth": 4, "learning_rate": 0.05, "subsample": 0.8,
              "colsample_bytree": 0.8, "min_child_weight": 5, "random_state": SEED, "n_jobs": -1}


def feature_frame():
    frame = features.load_salary_frame()
    skills, bundles = features.skill_bundles(frame)
    controls = frame.select(*features.CATEGORICAL_CONTROLS, *features.NUMERIC_CONTROLS).to_dummies(
        columns=features.CATEGORICAL_CONTROLS)
    X = np.column_stack([skills, controls.to_numpy()]).astype(np.float32)
    names = [*bundles["bundle_id"].to_list(), *controls.columns]
    y = frame["starting_salary_mid"].to_numpy()
    return X, y, names, bundles


def cross_validation(X, y) -> pl.DataFrame:
    models = {
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=20, max_features=0.3,
                                               random_state=SEED, n_jobs=-1),
        "xgboost": xgb.XGBRegressor(**XGB_PARAMS),
    }
    folds = KFold(CV_FOLDS, shuffle=True, random_state=SEED)
    rows = []
    for name, model in models.items():
        scores = cross_validate(model, X, y, cv=folds,
                                scoring=("r2", "neg_root_mean_squared_error", "neg_mean_absolute_error"))
        rows.append({
            "model": name,
            "cv_r2_mean": round(scores["test_r2"].mean(), 4),
            "cv_r2_std": round(scores["test_r2"].std(), 4),
            "cv_rmse_mean": round(-scores["test_neg_root_mean_squared_error"].mean(), 1),
            "cv_mae_mean": round(-scores["test_neg_mean_absolute_error"].mean(), 1),
        })
    return pl.DataFrame(rows)


def readable(names: list[str], bundles: pl.DataFrame) -> list[str]:
    labels = dict(zip(bundles["bundle_id"], bundles["bundle_label"]))
    return [labels.get(n, n) for n in names]


def main():
    X, y, names, bundles = feature_frame()
    is_skill = np.array([n in set(bundles["bundle_id"]) for n in names])
    labels = readable(names, bundles)

    cv = cross_validation(X, y)
    cv.write_csv(OUT / "model_cv_performance.csv")
    print(cv)

    model = xgb.XGBRegressor(**XGB_PARAMS).fit(X, y)
    booster = model.get_booster()
    dmatrix = xgb.DMatrix(X, feature_names=names)

    # SHAP values: one dollar contribution per feature per alumnus (last column is the bias).
    contribs = booster.predict(dmatrix, pred_contribs=True)[:, :-1]
    rows = []
    for j, name in enumerate(names):
        present = X[:, j] == 1
        binary = set(np.unique(X[:, j])) <= {0.0, 1.0}
        rows.append({
            "feature": name,
            "label": labels[j],
            "feature_type": "skill_bundle" if is_skill[j] else "control",
            "prevalence": round(float(present.mean()), 4) if binary else None,
            "mean_abs_shap": round(float(np.abs(contribs[:, j]).mean()), 2),
            # Average dollar contribution for holders minus non-holders.
            "shap_gap_present_vs_absent": round(float(contribs[present, j].mean() - contribs[~present, j].mean()), 2)
            if binary and present.any() and (~present).any() else None,
        })
    importance = pl.DataFrame(rows).sort("mean_abs_shap", descending=True)
    importance.write_csv(OUT / "shap_feature_importance.csv")
    importance.filter(pl.col("feature_type") == "skill_bundle").join(
        bundles.select("bundle_id", "member_skill_names"), left_on="feature", right_on="bundle_id"
    ).write_csv(OUT / "shap_skill_values.csv")

    # SHAP interaction values on a sample: entry [i, a, b] is the part of the
    # prediction attributable to features a and b jointly (split evenly across [a,b] and [b,a]).
    rng = np.random.default_rng(SEED)
    sample = rng.choice(len(X), size=min(INTERACTION_SAMPLE, len(X)), replace=False)
    inter = booster.predict(xgb.DMatrix(X[sample], feature_names=names), pred_interactions=True)[:, :-1, :-1]
    mean_abs = np.abs(inter).mean(axis=0) * 2
    np.fill_diagonal(mean_abs, 0)
    upper = np.triu_indices(len(names), k=1)
    order = np.argsort(mean_abs[upper])[::-1][:TOP_INTERACTIONS]
    top = pl.DataFrame({
        "feature_a": [labels[upper[0][i]] for i in order],
        "feature_b": [labels[upper[1][i]] for i in order],
        "mean_abs_interaction": [round(float(mean_abs[upper][i]), 2) for i in order],
        "both_skills": [bool(is_skill[upper[0][i]] and is_skill[upper[1][i]]) for i in order],
    })
    top.write_csv(OUT / "shap_top_interactions.csv")

    # Explicit pairs: is skill A worth more when the alumnus also has skill B?
    pair_rows = []
    for a, b in SKILL_PAIRS:
        ba, bb = features.find_bundle(bundles, a), features.find_bundle(bundles, b)
        reason = None
        if ba is None or bb is None:
            missing = a if ba is None else b
            reason = f"'{missing}' dropped: prevalence outside {features.MIN_PREVALENCE:.0%}-{features.MAX_PREVALENCE:.0%} (no usable variation)"
        elif ba == bb:
            reason = f"'{a}' and '{b}' are always taught together (bundle {ba}); their values cannot be separated"
        if reason:
            pair_rows.append({"skill_a": a, "skill_b": b, "status": "not estimable", "reason": reason})
            continue
        ja, jb = names.index(ba), names.index(bb)
        has_a, has_b = X[:, ja] == 1, X[:, jb] == 1
        # Interaction values for every alumnus holding both skills (capped for memory).
        both_rows = np.where(has_a & has_b)[0][:INTERACTION_SAMPLE]
        pair_inter = (booster.predict(xgb.DMatrix(X[both_rows], feature_names=names), pred_interactions=True)[:, ja, jb] * 2
                      if len(both_rows) else np.array([]))
        pair_rows.append({
            "skill_a": a, "skill_b": b, "status": "estimated", "reason": None,
            "n_with_a": int(has_a.sum()), "n_with_both": int((has_a & has_b).sum()),
            "shap_a_when_b_present": round(float(contribs[has_a & has_b, ja].mean()), 2) if (has_a & has_b).any() else None,
            "shap_a_when_b_absent": round(float(contribs[has_a & ~has_b, ja].mean()), 2) if (has_a & ~has_b).any() else None,
            "mean_interaction_when_both": round(float(pair_inter.mean()), 2) if len(pair_inter) else None,
        })
    pl.DataFrame(pair_rows).write_csv(OUT / "skill_pair_interactions.csv")

    rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=20, max_features=0.3, random_state=SEED, n_jobs=-1).fit(X, y)
    pl.DataFrame({"feature": names, "label": labels, "impurity_importance": rf.feature_importances_.round(5)}).sort(
        "impurity_importance", descending=True).write_csv(OUT / "random_forest_importance.csv")

    skill_shap = importance.filter(pl.col("feature_type") == "skill_bundle")
    summary = {
        "n": int(len(y)),
        "n_features": len(names),
        "n_skill_bundles": int(is_skill.sum()),
        "share_of_total_mean_abs_shap_from_skills": round(float(skill_shap["mean_abs_shap"].sum() / importance["mean_abs_shap"].sum()), 4),
        "cv": cv.to_dicts(),
    }
    (OUT / "xgb_shap_summary.json").write_text(json.dumps(summary, indent=2))
    with pl.Config(tbl_rows=20, fmt_str_lengths=50, tbl_width_chars=200):
        print(importance.head(15).select("label", "feature_type", "mean_abs_shap", "shap_gap_present_vs_absent"))
        print(top.head(10))
        print(pl.DataFrame(pair_rows))
        print(json.dumps({k: v for k, v in summary.items() if k != "cv"}, indent=2))


if __name__ == "__main__":
    main()
