# 03_transition_dynamics charts

Font: **Graphik**; code typography: **B612 Mono**.

All alumni-dependent results use synthetic testing data. Each figure includes a source caption. Original output tables are unchanged.

| Figure | PNG | PDF | SVG | Plotting data |
|---|---|---|---|---|
| Observed role transition probabilities | [PNG](01_observed_role_transitions.png) | [PDF](01_observed_role_transitions.pdf) | [SVG](01_observed_role_transitions.svg) | [CSV](01_observed_role_transitions.data.csv) |
| Most common title paths | [PNG](02_common_title_paths.png) | [PDF](02_common_title_paths.pdf) | [SVG](02_common_title_paths.svg) | [CSV](02_common_title_paths.data.csv) |
| Entry-role promotion comparison | [PNG](03_entry_role_promotion_comparison.png) | [PDF](03_entry_role_promotion_comparison.pdf) | [SVG](03_entry_role_promotion_comparison.svg) | [CSV](03_entry_role_promotion_comparison.data.csv) |
| Frequent title sequences | [PNG](04_frequent_title_sequences.png) | [PDF](04_frequent_title_sequences.pdf) | [SVG](04_frequent_title_sequences.svg) | [CSV](04_frequent_title_sequences.data.csv) |
| Absorbing-chain extrapolation | [PNG](05_absorbing_chain_projection.png) | [PDF](05_absorbing_chain_projection.pdf) | [SVG](05_absorbing_chain_projection.svg) | [CSV](05_absorbing_chain_projection.data.csv) |

## Reading the charts

- **Observed role transition probabilities:** Zero destinations are inferred only for observed origin rows. No unobserved Functional Lead origin row is manufactured.
- **Most common title paths:** Two highest-count edges per major, not two highest conditional probabilities. Full denominators are in source/plotting data.
- **Entry-role promotion comparison:** Classification flags use existing unadjusted tests. No invented uncertainty on promotion-rate points.
- **Frequent title sequences:** One most-supported closed pattern per major; support_pct source values are fractions, formatted as percentages.
- **Absorbing-chain extrapolation:** Dashed paths are scenario projections, not forecasts validated by additional observations. No uncertainty is supplied.

Regenerate with the project virtual environment:

```sh
.venv/bin/python "analysis being run/create_charts.py" --section 3
```
