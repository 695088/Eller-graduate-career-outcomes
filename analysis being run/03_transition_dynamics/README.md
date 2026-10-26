# 03 · Career Transition Dynamics & Path Sequence Mining

**Question:** What is the conditional probability of moving between role states? Do certain entry positions act as career **springboards**, or as **absorbing states** (dead ends)?

## What happens

Each alumnus is observed at three points:

| Step | Source column | State |
|---|---|---|
| t0 internship | `had_internship`, `internship_employer` | "Intern: <industry of internship employer>" or "No internship" |
| t1 first job | `first_job_title_raw` | normalized title and role state |
| t2 year 3 (36 months) | `yr3_job_title_raw` | normalized title and role state |

Raw titles are noisy ("Systems Analyst I", "Jr. Systems Analyst"). They are normalized, then mapped to three **latent role states** using the keyword rules in `common/data.py` (`ROLE_STATE_RULES`). The first matching rule wins:

1. **Functional Lead:** senior, lead, manager, director, head, principal, supervisor
2. **Client-Facing Operator:** consulting, audit, tax, advisory, sales, account, client, recruiting, HR, marketing specialist or associate, growth marketing, market development
3. **Individual Contributor:** everything else

The analysis runs on both levels: role states, which absorb title noise, and normalized titles, which give concrete paths.

## Data sources

- `data/alumni/synthetic_alumni.csv`: titles, internship, promotion flag and months to promotion

## Math

**First-order Markov chain.** The transition probability from state $i$ to state $j$ is estimated as
$$\hat P_{ij} = \frac{n_{ij}}{\sum_k n_{ik}}$$
with a 95% **Wilson score interval**:
$$\frac{\hat p + \frac{z^2}{2n} \pm z\sqrt{\frac{\hat p(1-\hat p)}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}, \quad z = 1.96$$

**Springboard vs. dead end.** For each entry title, a two-proportion z-test compares its 3-year promotion rate $p_1$ with the rest of its major, $p_2$:
$$z = \frac{p_1 - p_2}{\sqrt{\bar p(1-\bar p)(1/n_1 + 1/n_2)}}$$
- **Springboard:** significantly higher (p < 0.05)
- **Absorbing / dead-end:** significantly lower
- **Typical:** otherwise

The table also reports the stay probability (year-3 title equals entry title) and P(reaching Functional Lead).

**Absorbing-chain projection.** This treats the 36-month role-state matrix as time-homogeneous, with Functional Lead absorbing (no demotions). Write the matrix in canonical form, with $Q$ for transient-to-transient moves and $R$ for transient-to-absorbing moves. The **fundamental matrix** is
$$N = (I - Q)^{-1}$$
$N\mathbf{1}$ is the expected number of 3-year periods before reaching Functional Lead; ×3 gives years. The state distribution after $k$ periods is $\pi_k = \pi_0 P^k$ (projected to years 3, 6 and 9). **This is a model extrapolation, not observed data.**

**Testing the first-order assumption.** A first-order chain assumes the year-3 state depends only on the entry state, not on earlier history. The test runs within each entry state (stratum $s$), computing $\chi^2_s$ of internship × year-3 state, then sums them:
$$\chi^2 = \sum_s \chi^2_s, \quad df = \sum_s df_s$$
Under the null this sum is chi-square distributed. Rejection means internship history still matters after conditioning on the entry state, so first-order probabilities hide that effect.

**Sequential pattern mining (PrefixSpan).** Each alumnus contributes a sequence: `[Intern] <industry> → [Y0] <entry title> → [Y3] <year-3 title>`. The internship item is omitted if there was none. PrefixSpan grows frequent prefixes depth-first over projected databases and returns every subsequence with
$$\text{support}(p) = \frac{\#\{\text{sequences containing } p\}}{n} \ge 5\%$$
- Rule confidence is $\text{support}(p) / \text{support}(p \text{ minus its last item})$, an estimate of P(last step | earlier steps).
- A pattern is **closed** when no longer pattern has the same support.

SPADE would return the same frequent set; PrefixSpan is used because it is faster on short sequences.

## What the code does

1. `markov_transitions.py`
   - adds internship, entry and year-3 states
   - writes the t0→t1 and t1→t2 role-state matrices, by major and pooled
   - writes title-level transition edges, ranked within each entry title
   - classifies entry roles, runs the absorbing projection and the Markov-property test per major
2. `sequence_mining.py`
   - builds title sequences and role-state sequences per major
   - runs PrefixSpan (all patterns and closed patterns), adds confidence, writes the tables

## Outputs (`outputs/`)

| File | Contents |
|---|---|
| `role_state_transition_matrices.csv` | long-format P(to \| from) with counts and Wilson CIs, for t0→t1 and t1→t2, by major and `ALL` |
| `title_transition_edges.csv` | every entry title → year-3 title edge by major, with probability, CI, role states and `path_rank`. This is the **data for the Markov state diagram**. |
| `top_paths_out_of_entry_roles.csv` | the three highest-probability paths out of each entry role, per major |
| `entry_role_springboard_classification.csv` | per (major, entry title): n, promotion rate, stay probability, P(to lead), median months to promotion, z, p, classification |
| `absorbing_chain_projection.csv` | expected years to Functional Lead per starting state, and projected state shares at years 3, 6 and 9 |
| `markov_property_tests.csv` | summed stratified chi-square, df, p-value and verdict per major |
| `frequent_sequences_by_major.csv` | all frequent patterns (length ≥ 2): support, confidence, `is_closed`, for title and role-state sequences |
| `top_title_sequences_by_major.csv` | top 5 closed title sequences per major |

## How to run

```sh
.venv/bin/python "analysis being run/03_transition_dynamics/markov_transitions.py"
.venv/bin/python "analysis being run/03_transition_dynamics/sequence_mining.py"
```

Settings:
- `markov_transitions.py`: `TOP_PATHS_PER_ENTRY`, `SIGNIFICANCE`, `PROJECTION_PERIODS`
- `sequence_mining.py`: `MIN_SUPPORT`, `MIN_LENGTH`
- `common/data.py`: role-state definitions (`ROLE_STATE_RULES`)

## Results on the current data

- **Pooled role-state transitions over 36 months:**

  | From | To Functional Lead | Stay in same state |
  |---|---|---|
  | Individual Contributor | 56.2% (95% CI 55.3–57.2%) | 43.8% |
  | Client-Facing Operator | 54.5% (53.0–55.9%) | 45.6% |

  Nobody moves directly between IC and Client-Facing.
- **Springboards:** BNAD Management Analyst (60% promoted vs 56% in the major, p = 0.04) and MKTG Market Research Associate (62% vs 57%, p = 0.05).
- **Dead end:** MIS Tech Consultant (50% vs 55%, p = 0.03). Every other entry role is typical.
- **Projection:** expected time to Functional Lead is about 5.2–6.0 years by major and state (MIS Client-Facing is slowest at 6.0). Projected Functional Lead share is 56% at year 3, 80% at year 6 and 91% at year 9.
- **The first-order Markov assumption is rejected in every major** (pooled χ² = 135, p ≈ 5×10⁻³⁰). Internship history still predicts year-3 outcomes after conditioning on the entry role. This matches the generator, where internships raise promotion odds. A second-order model, or including internship in the state, is warranted.
- **Top sequences:**
  - Most are "entry → Senior <same track>" with confidence 0.50–0.60.
  - For ACCT, three-step patterns with an internship clear 5% support, for example `[Intern] Consulting & Advisory → Audit Associate → Senior Audit/Tax Associate` (6.6% support, 0.60 confidence).

## Limitations

- **There is only one observed transition** (year 0 to year 3). Year-by-year dynamics, multi-hop paths and promotion timing within the window cannot be modelled as a chain. Use `months_to_promo` for timing.
- The projection assumes the year 0–3 matrix repeats unchanged and that nobody leaves Functional Lead. Neither is observed.
- Role states are rule-based. Titles that match no keyword fall into Individual Contributor, so review `ROLE_STATE_RULES` for real titles.
- Synthetic titles come from a few templates, so the mined sequences mostly reflect those templates.

## Charts

Publication-style figures are in [`outputs/charts/`](outputs/charts/README.md), with PNG, PDF, SVG, plotting CSVs, and source manifests. See the [shared chart guide](../CHARTS.md) for format and uncertainty conventions.
