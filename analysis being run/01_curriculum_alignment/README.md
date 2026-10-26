# 01 · Curriculum Alignment & Gap Matrix

**Question:** Which skills does Eller teach that the market wants (high alignment)? Which skills does the market want that the curriculum barely covers (market gaps)? Which taught topics show little market demand (over-supply)?

## What happens

Every **term** gets two scores, supply and demand, each a percentile rank between 0 and 1. A term is either one of the 354 course skills or one of O\*NET's 176 "Hot Technologies". The two scores place the term in a quadrant:

| | supply ≥ 0.5 | supply < 0.5 |
|---|---|---|
| **demand ≥ 0.5** | High Alignment | Market Gap |
| **demand < 0.5** | Over-Supply | Low Priority |

This runs once for all alumni and again for each major. Per-major runs weight demand by the occupations that major's alumni hold, and measure exposure using that major's transcripts.

## Data sources

- **Supply:** course descriptions in `data/eller courses/processed data/eller_courses_combined.csv` (243 courses) and alumni transcripts (`courses_taken` in `data/alumni/synthetic_alumni.csv`).
- **Terms:** `data/skills from courses/course_skills.csv` (name plus synonyms) and the O\*NET Hot Technologies list.
- **Demand** comes from the O\*NET Web Services v2 API for the **target occupations**, meaning the 9 O\*NET codes alumni hold at their first job or year 3. Each code is weighted by how many alumni hold it:
  - `online/hot_technology/` gives national job-posting counts per technology.
  - `online/occupations/{code}/hot_technology` gives the % of that occupation's postings mentioning each technology.
  - `online/occupations/{code}/details/tasks` and `.../details/technology_skills` give task statements and technology examples.

## Math

**Text similarity.** All text is lowercased, stop words are dropped and words are Porter-stemmed, so "negotiation" and "negotiate" both become "negoti". Unigrams and bigrams are then weighted by TF-IDF with sublinear term frequency:

$$w_{t,d} = (1+\log tf_{t,d})\cdot \log\frac{1+N}{1+df_t} + 1$$

Cosine similarity between term vector $a$ and document vector $b$ is $\cos(a,b)=\frac{a\cdot b}{\lVert a\rVert\lVert b\rVert}$. Each term is compared using every phrase it owns (name and each synonym), and the best-matching phrase counts. Course descriptions are split into sentences, and a course's similarity is its best sentence. Without this, one clear mention such as "SQL programming may be used" would be diluted by the rest of the description.

**Supply** for term $s$:
- catalog similarity: $\max_c \cos(s, c)$ over all courses
- core similarity: the same maximum, restricted to courses taken by ≥ 50% of alumni
- alumni exposure: the share of alumni who took at least one course with $\cos \ge 0.20$
- **supply score** = mean of the percentile ranks of catalog similarity and alumni exposure

**Demand** for term $s$, with alumni weights $w_o$ over target occupations $o$ (summing to 1):
- posting share: $\sum_o w_o \cdot \text{pct}_{o,s}/100$, the alumni-weighted share of target-occupation postings naming the technology. A course skill inherits this from a Hot Technology whose name matches it with cosine ≥ 0.5. If several match, the most-posted one wins, so "SQL" maps to "Structured query language SQL", not "PostgreSQL".
- task relevance: $\sum_o w_o \max_{x \in \text{profile}(o)} \cos(s, x)$, where the profile is the occupation's task statements plus its technology examples
- **demand score** = percentile rank of (task relevance + posting share)

Percentile rank uses average ranks for ties: $r_i/n$. The alignment gap is demand score minus supply score.

## What the code does

1. `build_market_demand.py`
   - computes alumni weights per (major, occupation) from first-job and year-3 codes
   - pages through the O\*NET endpoints above (responses are cached in `onet and jobs/cache/`)
   - writes the market tables
2. `gap_matrix.py`
   - builds the 530 terms with their phrases and fits one TF-IDF vocabulary over course sentences, O\*NET texts and term phrases
   - computes the similarity matrices
   - scores supply and demand for all alumni and for each major, assigns quadrants and writes the tables

## Outputs (`outputs/`)

| File | Contents |
|---|---|
| `target_occupation_weights.csv` | alumni-observation count and weight per (major, O\*NET code); `ALL` is pooled |
| `market_hot_technologies.csv` | 176 Hot Technologies with national job-posting counts |
| `occupation_technology_postings.csv` | % of each target occupation's postings naming each technology, plus O\*NET's in-demand flag |
| `occupation_profile_texts.csv` | task statements and technology examples per target occupation |
| `gap_matrix.csv` | all terms, all alumni: every supply and demand metric, `best_matching_course`, `matched_hot_technology`, scores, `alignment_gap`, `quadrant` |
| `gap_matrix_by_major.csv` | the same, recomputed for each major |
| `quadrant_summary.csv` | top 15 terms per quadrant |

## How to run

From the project root:

```sh
.venv/bin/python "analysis being run/01_curriculum_alignment/build_market_demand.py"   # needs internet on first run
.venv/bin/python "analysis being run/01_curriculum_alignment/gap_matrix.py"
```

Settings are at the top of `gap_matrix.py`:
- `QUADRANT_CUTOFF` (0.5)
- `CORE_COURSE_SHARE` (0.5)
- `COURSE_MATCH_SIM` (0.20)
- `TECH_MATCH_SIM` (0.50)

## Results on the current data

Of 530 terms: 114 High Alignment, 152 Market Gap, 185 Over-Supply, 79 Low Priority.

- **High Alignment:** Microsoft Excel, Tableau and SAS (also high on posting share), plus Portfolio Management, Fund Accounting, HR Management, Tax Compliance, Financial Modeling, Financial Statement Analysis and Project Management.
- **Market Gaps:**
  - Office and collaboration tools: PowerPoint, Outlook, SharePoint, Visio, JIRA
  - Microsoft Power BI (3.6% of target postings, no course coverage)
  - SAP, Git, Amazon Web Services and QuickBooks
  - **SQL** as a course skill. It is in the catalog (MIS 331, ECON 454), but only about 8% of alumni take a covering course.
  - For MIS alone, the top gaps are Office, SAP, PowerPoint, JIRA and Power BI.
- **Over-Supply:** taught topics that rarely appear in these occupations' O\*NET profiles. Examples are Ethical Reasoning, Social Entrepreneurship, Venture Capital, Real Estate Investment Analysis, Behavioral Game Theory and Property Rights Law.
- **Python and Snowflake rank Low Priority, not Market Gap.** O\*NET does not list them for the 9 business occupations these alumni hold. Python appears in only 2% of their postings. That is a finding about these occupations, and it would change if alumni held data or analytics roles.

## Limitations

- Supply measures catalog coverage and enrollment, not depth of instruction or student proficiency.
- TF-IDF matches words, not meaning. Paraphrases with no shared stems are missed.
- Demand covers only the occupations the (synthetic) alumni hold. Real alumni with more varied roles would broaden it.
- O\*NET posting shares are national, not specific to Arizona.
- Terms appear twice when a course skill and a Hot Technology share a name (e.g. Tableau). Both rows are kept on purpose, because one is measured as taught and one as posted.

## Charts

Publication-style figures are in [`outputs/charts/`](outputs/charts/README.md), with PNG, PDF, SVG, plotting CSVs, and source manifests. See the [shared chart guide](../CHARTS.md) for format and uncertainty conventions.
