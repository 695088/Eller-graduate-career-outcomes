# 02 · Distinct Career Archetype Clusters

**Question:** Where do graduates actually concentrate, beyond generic major titles? What does each group's title progression, industry mix and geography look like?

## What happens

Alumni are clustered on **what they do**, not what they studied:
- normalized job titles
- O\*NET occupations
- industry
- course-derived skills

Clustering runs once **within each major**, which splits a major into sub-archetypes, and once **pooled across all majors**, which finds archetypes that cross major lines. The number of clusters is chosen automatically. Each archetype is then profiled.

## Data sources

- `data/alumni/synthetic_alumni.csv`: titles, O\*NET codes, industry, metro, salary, promotion and skills
- `onet and jobs/onet_occupations.csv`: job zone and occupation title for each O\*NET code

## Math

**Features.** Four blocks are built per alumnus:
- **titles:** TF-IDF unigrams and bigrams of "entry title + year-3 title" (normalized, see `common/data.py`)
- **occupations:** one-hot first and year-3 O\*NET codes
- **industry:** one-hot industry sector
- **skills:** multi-hot skill tags, compressed to 15 dimensions with truncated SVD (latent semantic analysis)

Each block is L2-normalized row by row, then multiplied by a weight (titles 1.0, occupations 0.75, industry 0.75, skills 0.5) so that no block dominates through sheer size. The blocks are then stacked.

**K-means** minimizes within-cluster squared distance, $\sum_k \sum_{i \in C_k} \lVert x_i - \mu_k \rVert^2$, with 10 random restarts and seed 42.

**Choosing k.** The **silhouette score** is $s_i = \frac{b_i - a_i}{\max(a_i, b_i)}$, where $a_i$ is the mean distance to points in the alumnus's own cluster and $b_i$ is the mean distance to the nearest other cluster. Values run from −1 to 1, and higher means better separated. The script picks the k with the highest mean silhouette: k = 2–6 within a major, 4–14 pooled. Silhouette is estimated on a 3,000-row sample.

**Geographic hubs.** The location quotient is
$$LQ_{a,m} = \frac{\text{share of archetype } a \text{ in metro } m}{\text{share of all alumni in metro } m}$$
A metro counts as a hub when LQ ≥ 1.2 and at least 30 alumni are there.

**Independence tests.** A chi-square test is run on archetype × metro and on archetype × industry:

$$\chi^2 = \sum \frac{(O - E)^2}{E}$$

Effect size is Cramér's $V = \sqrt{\chi^2 / (n(\min(r,c)-1))}$. A non-significant metro test means the "hubs" are noise.

**Job zone jump** = year-3 job zone minus entry job zone, using the O\*NET job zone of each code.

## What the code does

`archetype_clusters.py`:
1. For each major and for the pooled set:
   - build the weighted feature matrix
   - run K-means for each k, keep the best silhouette
   - number the archetypes by size (A1 is the largest) and auto-label each one as `<most common entry title> -> <most common year-3 title> | <top industry>`
2. Profile every archetype.
3. Compute within-archetype title transitions, industry shares, metro location quotients and the independence tests.

## Outputs (`outputs/`)

| File | Contents |
|---|---|
| `cluster_selection.csv` | silhouette and inertia for every k tried, per group |
| `archetype_assignments.csv` | `alumni_id` → `archetype_id` and label, per group (each alumnus appears once in their major and once in `ALL`) |
| `archetype_profiles.csv` | per archetype: size, share of group, major mix, top entry and year-3 titles, top occupation, industries, metros, internship rate, median and mean salary, 3-year promotion rate, months to promotion, entry and year-3 job zone and jump |
| `archetype_title_transitions.csv` | entry title → year-3 title counts and P(year-3 title \| entry title) within each archetype (the transition map) |
| `archetype_industry_distribution.csv` | industry shares per archetype |
| `archetype_geo_hubs.csv` | metro share, location quotient and `is_hub` per archetype |
| `archetype_independence_tests.csv` | chi-square, p-value and Cramér's V for metro and for industry, per group |

## How to run

```sh
.venv/bin/python "analysis being run/02_career_archetypes/archetype_clusters.py"
```

Settings are at the top of the script:
- `K_RANGE_MAJOR`, `K_RANGE_POOLED`
- `BLOCK_WEIGHTS`
- `SKILL_SVD_COMPONENTS`
- `HUB_MIN_LQ`, `HUB_MIN_ALUMNI`

To give archetypes human names (e.g. "Cyber Risk & IT Audit"), map `archetype_id` to a name after reviewing `archetype_profiles.csv`.

## Results on the current data

- **Chosen k by major:** ACCT 6, FIN 6, MIS 6, ECON 6, OSCM 6, MKTG 4, BMGT 2, BNAD 2, ENTR 2 (silhouettes 0.31–0.51). Pooled: 10.
- **Pooled archetypes that cross majors:**
  - "Business Analyst → Senior Management Analyst" draws evenly from BMGT, ECON and BNAD (about a third each).
  - "Market Development → Senior Marketing Specialist" is 67% MKTG and 33% ENTR.
  - "Startup / Business Operations" is roughly half BNAD and half ENTR.
- **MIS splits into six archetypes:**
  - Systems Analyst → Senior Systems Analyst in Technology
  - Systems Analyst → Senior Consultant, in Technology and in Consulting (two archetypes)
  - IT Business Analyst in Consulting
  - Systems Analyst with no promotion, in Consulting
  - Tech Consultant with no promotion
- **Industry** differs strongly between archetypes in ACCT, FIN, MIS, ECON and OSCM (Cramér's V 0.72–1.0). It does not differ in BMGT, BNAD, ENTR or MKTG.
- **Metro does not differ between archetypes in any group** (all p > 0.13). The flagged hubs are noise. That is expected, because the generator assigns metros at random.

## Limitations

- Year-3 title is a feature, so archetypes partly encode whether someone was promoted. This is deliberate, because an archetype here is a trajectory. Drop `yr3_title` from the title block for entry-only archetypes.
- The synthetic data has only 35 entry titles and 9 O\*NET codes, so within-major clusters closely follow the generator's role templates. Real titles would give richer clusters.
- Only years 0 and 3 are observed. Progression beyond year 3 cannot be mapped.
- K-means assumes roughly spherical clusters. A different algorithm (e.g. agglomerative or HDBSCAN) can be swapped into `choose_k`.

## Charts

Publication-style figures are in [`outputs/charts/`](outputs/charts/README.md), with PNG, PDF, SVG, plotting CSVs, and source manifests. See the [shared chart guide](../CHARTS.md) for format and uncertainty conventions.
