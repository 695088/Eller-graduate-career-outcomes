# 04_hedonic_salary charts

Font: **Graphik**; code typography: **B612 Mono**.

All alumni-dependent results use synthetic testing data. Each figure includes a source caption. Original output tables are unchanged.

| Figure | PNG | PDF | SVG | Plotting data |
|---|---|---|---|---|
| Salary model cross-validation | [PNG](01_model_cross_validation.png) | [PDF](01_model_cross_validation.pdf) | [SVG](01_model_cross_validation.svg) | [CSV](01_model_cross_validation.data.csv) |
| Skill salary premiums with robust intervals | [PNG](02_skill_premiums_robust_intervals.png) | [PDF](02_skill_premiums_robust_intervals.pdf) | [SVG](02_skill_premiums_robust_intervals.svg) | [CSV](02_skill_premiums_robust_intervals.data.csv) |
| Salary control estimates | [PNG](03_salary_control_estimates.png) | [PDF](03_salary_control_estimates.pdf) | [SVG](03_salary_control_estimates.svg) | [CSV](03_salary_control_estimates.data.csv) |
| TreeSHAP feature importance | [PNG](04_shap_feature_importance.png) | [PDF](04_shap_feature_importance.pdf) | [SVG](04_shap_feature_importance.svg) | [CSV](04_shap_feature_importance.data.csv) |
| Largest TreeSHAP interactions | [PNG](05_shap_top_interactions.png) | [PDF](05_shap_top_interactions.pdf) | [SVG](05_shap_top_interactions.svg) | [CSV](05_shap_top_interactions.data.csv) |
| Requested skill-pair estimability | [PNG](06_requested_skill_pair_interactions.png) | [PDF](06_requested_skill_pair_interactions.pdf) | [SVG](06_requested_skill_pair_interactions.svg) | [CSV](06_requested_skill_pair_interactions.data.csv) |

## Reading the charts

- **Salary model cross-validation:** Symmetric bars are SD across folds for R² only. Both bar axes begin at zero.
- **Skill salary premiums with robust intervals:** Dollar CI endpoints = (exp(saved log-coefficient CI) − 1) × mean starting salary. Intervals are pointwise, not FDR-adjusted.
- **Salary control estimates:** References inferred from observed levels absent from model coefficient table; source alumni fingerprint recorded in run manifest.
- **TreeSHAP feature importance:** Magnitude is unsigned and does not imply a positive effect. Saved attribution values, not a reconstructed SHAP beeswarm.
- **Largest TreeSHAP interactions:** Uses the saved upper-triangle entry scale; not doubled into a joint contribution.
- **Requested skill-pair estimability:** All-zero estimates retain a symmetric ±$1 display window. Missing pair estimates are text only, never fabricated zeros.

Regenerate with the project virtual environment:

```sh
.venv/bin/python "analysis being run/create_charts.py" --section 4
```
