# 04 · Hedonic Salary Modeling & Skill Valuation

**Question:** What is the marginal dollar value (salary premium) of individual skills, controlling for geography, employer type and major? Do skills interact? For example, is SQL worth more alongside Excel than alongside Tableau?

## What happens

Two complementary models predict **starting salary** from the same inputs:

1. **Hedonic wage regression** (OLS with fixed effects). Gives an interpretable, linear premium per skill with standard errors.
2. **XGBoost and Random Forest + SHAP**. Captures non-linear effects and skill-by-skill interactions, and splits every prediction into dollar contributions per feature.

## Data sources

- `data/alumni/synthetic_alumni.csv`:
  - `starting_salary_mid`, the midpoint of a $10K salary band
  - `skills_obtained`
  - `major`, `location_metro`, `industry_sector`, `employer_clean`, `grad_year`, `had_internship`, `gpa_final`
- `data/skills from courses/course_skills.csv`: skill names
- `common/company_tiers.csv`: employer → company tier 1/2/3 (editable judgment mapping; unlisted employers default to tier 3)
- `common/metro_cost_of_living.csv` (optional): regional price parity per metro. This file ships empty with source instructions. Once every row is filled, a second specification uses it.

## Feature construction (`features.py`)

- **Skill indicators:** one 0/1 column per skill.
  - Skills held by under 2% or over 98% of alumni are dropped, because they have no usable variation. Microsoft Excel and Tableau are dropped this way: every alumnus gets them from the core analytics courses BNAN 276/277.
  - **Skill bundles:** skills that are always taught together have identical columns (e.g. SQL and SAS both come only from ECON 454, along with 8 other skills). No model can value them separately, so each set of identical columns becomes one bundle, labelled "SQL (+9 co-taught)".
  - Result: 312 skills form 201 bundles. Membership is in `outputs/skill_bundles.csv`.
- **Controls:**
  - fixed effects for major, metro, industry, company tier and grad year
  - internship (0/1) and GPA

## Math

### Hedonic OLS (`hedonic_ols.py`)

$$\log(\text{salary}_i) = \alpha + \sum_s \beta_s\,\text{bundle}_{is} + \gamma\,\text{intern}_i + \delta\,\text{GPA}_i + \mu_{\text{major}} + \lambda_{\text{metro}} + \eta_{\text{industry}} + \tau_{\text{tier}} + \theta_{\text{year}} + \varepsilon_i$$

- **Interpretation:** $e^{\beta_s} - 1$ is the % premium of holding bundle $s$, all else equal. Multiplied by mean salary it gives the **dollar premium**.
- **Cost of living:** metro fixed effects $\lambda$ absorb regional cost of living. The optional second specification replaces them with $\phi \log(\text{RPP}_{\text{metro}})$.
- **Collinearity:** columns are ordered constant → controls → skills. A QR decomposition drops any column that is a linear combination of earlier columns ($|R_{jj}| \approx 0$), so a redundant skill is dropped before a control. Controls can be redundant too: industry and tier are both properties of the employer, and here the tier-3 dummy is dropped.
- **Standard errors:** heteroskedasticity-robust (HC1), $\widehat{V} = \frac{n}{n-k}(X'X)^{-1}X'\operatorname{diag}(\hat e^2)X(X'X)^{-1}$.
- **Joint test:** a Wald F-test of $H_0: \beta_s = 0$ for all $s$.
- **Multiple testing:** with 201 skill tests, about 10 would be "significant" at 5% by chance. Benjamini–Hochberg q-values control the false discovery rate: $q_{(i)} = \min_{j \ge i} \frac{m}{j} p_{(j)}$.

### Tree models and SHAP (`xgb_shap.py`)

- **Models:**
  - XGBoost (400 trees, depth 4, learning rate 0.05, row and column subsampling 0.8)
  - Random Forest (300 trees, minimum leaf 20)
  - linear regression as a baseline

  All three predict salary in dollars from the same features (skill bundles + one-hot controls).
- **5-fold cross-validation** reports out-of-sample R², RMSE and MAE. If the tree models do not beat the linear model, there is little non-linearity to find.
- **SHAP values** use XGBoost's exact TreeSHAP. Each prediction is decomposed as $f(x) = \phi_0 + \sum_j \phi_j(x)$, where $\phi_j$ is feature $j$'s Shapley value:
$$\phi_j = \sum_{S \subseteq F \setminus \{j\}} \frac{|S|!\,(|F|-|S|-1)!}{|F|!}\left[f_{S \cup \{j\}}(x) - f_S(x)\right]$$
  - Reported: mean $|\phi_j|$ (importance), and the mean $\phi_j$ for holders minus non-holders (average marginal dollar value).
- **SHAP interaction values** $\Phi_{jk}$ split the joint effect of two features off from their main effects. Here $\Phi_{jk} + \Phi_{kj}$ is the extra salary from holding both, beyond what each adds alone.
  - For each pair in `SKILL_PAIRS`, the script compares skill A's SHAP when B is present against when B is absent, plus the mean interaction across every alumnus holding both.
  - A pair is reported **not estimable** (with the reason) if either skill was dropped or both are in the same bundle.
- **Random Forest impurity importance** is reported for comparison.

## Outputs (`outputs/`)

| File | Contents |
|---|---|
| `skill_bundles.csv` | bundle id, label, member skills, prevalence |
| `hedonic_skill_premiums_metro_fixed_effects.csv` | per bundle: coefficient, robust SE, t, p, FDR q, 95% CI, % premium, $ premium, members |
| `hedonic_controls_metro_fixed_effects.csv` | the same for every control (major, metro, industry, tier, year, internship, GPA) |
| `hedonic_model_summary.json` | n, R², adjusted R², controls-only R², joint skill F-test, columns dropped, number of significant bundles |
| `hedonic_*_log_rpp_cost_of_living.csv` | written only once the cost-of-living template is filled |
| `model_cv_performance.csv` | 5-fold CV R², RMSE and MAE for linear regression, Random Forest and XGBoost |
| `shap_feature_importance.csv` | every feature: mean \|SHAP\|, holder-minus-non-holder SHAP gap, prevalence |
| `shap_skill_values.csv` | the same, skill bundles only, with members |
| `shap_top_interactions.csv` | 25 strongest pairwise SHAP interactions (1,500-row sample) |
| `skill_pair_interactions.csv` | the configured skill pairs: estimated values, or why a pair is not estimable |
| `random_forest_importance.csv` | Random Forest impurity importances |
| `xgb_shap_summary.json` | feature counts, share of total SHAP from skills, CV results |

## How to run

```sh
.venv/bin/python "analysis being run/04_hedonic_salary/hedonic_ols.py"
.venv/bin/python "analysis being run/04_hedonic_salary/xgb_shap.py"
```

Settings:
- `features.py`: `MIN_PREVALENCE`, `MAX_PREVALENCE`, control lists
- `xgb_shap.py`: `SKILL_PAIRS`, `XGB_PARAMS`, `CV_FOLDS`, `INTERACTION_SAMPLE`

To add the cost-of-living index, fill `rpp_index` in `common/metro_cost_of_living.csv` from BEA's MARPP table and re-run.

## Results on the current data, checked against the generator

The synthetic generator sets salary as major mean + $2,000 × internship + $1,200 × (grad year − 2020) + $10,000 in SF/NY/Seattle + noise, then bins it into $10K bands. Skills have no effect. The models recover this:

| Effect | Planted | OLS estimate | XGBoost SHAP gap |
|---|---|---|---|
| Internship | +$2,000 | +$2,211 (p ≈ 10⁻³⁵) | +$2,036 |
| New York | +$10,000 | +$10,322 | +$8,909 |
| San Francisco | +$10,000 | +$10,442 | +$9,140 |
| Seattle | +$10,000 | +$10,762 | +$9,498 |
| Grad year 2018 vs 2021 | −$3,600 | −$3,684 | — |
| Skills (all 201 bundles) | $0 | joint F = 0.93, p = 0.75; **0 bundles with q < 0.05** | each bundle small; the "SQL (+9 co-taught)" bundle is +$110 |

- **R²:** 0.377 with skills vs 0.369 for controls only. Skills add essentially nothing.
- **Company tier and industry:** no detectable effect, as in the generator.
- **Cross-validated R²:** linear 0.373, XGBoost 0.367, Random Forest 0.361. The tree models do not beat the linear model, so there is no non-linear structure to exploit.
- **Interactions:** the strongest SHAP interactions are among controls (major × major, metro × year), under $200 on average. No skill pair has a non-zero interaction.
- **Skills' 27% share of total mean |SHAP|** is noise spread across 201 features (the trees overfit slightly). It is not real value: the holder-vs-non-holder gaps are small and mixed in sign.
- **The SQL × Excel vs SQL × Tableau question is not estimable in this data.** Every alumnus has Excel and Tableau, and SQL cannot be separated from SAS and the other ECON 454 skills. The pairs that can be estimated (SQL with Database Management, SQL with Optimization Modeling) show zero interaction. The course skills list has no Python, so SQL × Python cannot be tested.

## Limitations

- Salary is a band midpoint, so OLS on midpoints understates variation. Interval regression is the exact alternative.
- Only starting salary exists. Year-3 salary would allow skill premiums to be measured over time.
- Skills are course tags, not verified proficiency, and are largely determined by major. The skill coefficients are identified only from electives and secondary majors within a major.
- These are associations, not causal effects: unobserved ability can drive both course choice and salary.
- Company tiers are a hand-made mapping, and metro fixed effects stand in for cost of living until real RPP values are added.

## Charts

Publication-style figures are in [`outputs/charts/`](outputs/charts/README.md), with PNG, PDF, SVG, plotting CSVs, and source manifests. See the [shared chart guide](../CHARTS.md) for format and uncertainty conventions.
