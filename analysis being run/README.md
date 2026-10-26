# Analyses being run

Four analysis sections, each in its own folder with its scripts, a README, and an `outputs/` folder of CSV and JSON tables. Twenty research figures now visualize the saved tables. See [the chart guide](CHARTS.md) for all four chart folders, formats, interpretation, and regeneration instructions.

| Folder | Question | Main methods |
|---|---|---|
| [`01_curriculum_alignment`](01_curriculum_alignment/README.md) | Which skills are well aligned with the market, which are market gaps, and which are over-supplied? | TF-IDF cosine similarity, O\*NET job-posting shares, percentile-rank quadrants |
| [`02_career_archetypes`](02_career_archetypes/README.md) | Where do graduates actually end up, beyond their major label? | Weighted feature blocks, K-means with silhouette selection, location quotients, chi-square tests |
| [`03_transition_dynamics`](03_transition_dynamics/README.md) | How likely is each role transition, and which entry roles are springboards or dead ends? | First-order Markov chains, absorbing-chain fundamental matrix, PrefixSpan sequence mining |
| [`04_hedonic_salary`](04_hedonic_salary/README.md) | What is each skill worth in salary, controlling for geography, employer and major? | OLS with fixed effects (HC1 errors, FDR), XGBoost and Random Forest, TreeSHAP values and interactions |

## How to run

From the project root (`midterm-464/`), using the project venv:

```sh
.venv/bin/python "analysis being run/run_all.py"
```

Or run any single script, for example `.venv/bin/python "analysis being run/02_career_archetypes/archetype_clusters.py"`. Scripts can be launched from any working directory. In section 01, `build_market_demand.py` must run before `gap_matrix.py`. Every other script stands alone.

A full run takes about 30 seconds once the O\*NET responses are cached. Required packages: `polars`, `numpy`, `scipy`, `scikit-learn`, `statsmodels`, `xgboost`, `prefixspan`, `nltk`, `requests`. All are installed in the project venv and listed in the root `requirements.txt`.

## Data sources

| Data | Path | Used by |
|---|---|---|
| Alumni records (15,000, **synthetic**) | `data/alumni/synthetic_alumni.csv` | all sections |
| Eller course catalog and descriptions | `data/eller courses/processed data/eller_courses_combined.csv` | 01 |
| Course skills dictionary (354 skills) | `data/skills from courses/course_skills.csv` | 01, 04 |
| O\*NET occupations (job zone, cluster, median pay) | `onet and jobs/onet_occupations.csv` | 02 |
| O\*NET Web Services API (Hot Technologies, postings, tasks) | fetched live, cached in `onet and jobs/cache/` | 01 |
| Company tiers (editable judgment mapping) | `common/company_tiers.csv` | 04 |
| Metro cost-of-living index (template, empty) | `common/metro_cost_of_living.csv` | 04 (optional) |

## Shared code (`common/`)

- `data.py` holds all file paths and loaders. JSON array columns are parsed into lists.
  - `normalize_title()` strips level markers so inconsistent titles merge ("Systems Analyst I" and "Jr. Systems Analyst" both become "Systems Analyst").
  - `ROLE_STATE_RULES` maps noisy titles to latent role states: Individual Contributor, Client-Facing Operator, Functional Lead.
  - `import_onet_get()` reuses the cached O\*NET client from `onet and jobs/onet_skills.py`.
- `company_tiers.csv`: tier 1 is Big Four, mega-cap tech and bulge-bracket bank; tier 2 is other large national firms; tier 3 is regional firms. Edit freely.
- `metro_cost_of_living.csv`: fill it in with BEA Regional Price Parities to add a cost-of-living specification to section 04.

## Read this before using any result

**The alumni data is synthetic.** `data/alumni/generate_synthetic_alumni.py` invented every record from simple rules:
- Salary is set only by major, internship (+$2,000), grad year (+$1,200 per year) and three metros (+$10,000 in SF, NY and Seattle).
- Skills have no effect on salary.
- Promotion depends on internship, GPA and secondary major.
- Metro is assigned at random.

The pipelines run end to end, and section 04 recovers the planted effects almost exactly. That validates the code. The results describe the generator, not real Eller graduates. Re-run on real alumni data by replacing `synthetic_alumni.csv` with a file that has the same columns.

**Only two career points are observed**: the first job and 36 months later. The "1-to-5-year" progression in the original plan cannot be measured. Sections 02 and 03 measure years 0 to 3 and label any longer-run figure as a model projection.

**There is no scraped job-postings dataset.** Market demand comes from O\*NET, which reports national posting counts and per-occupation posting shares for "Hot Technologies", along with occupation task statements.
