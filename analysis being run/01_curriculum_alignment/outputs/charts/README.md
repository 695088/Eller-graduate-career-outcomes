# 01_curriculum_alignment charts

Font: **Graphik**; code typography: **B612 Mono**.

All alumni-dependent results use synthetic testing data. Each figure includes a source caption. Original output tables are unchanged.

| Figure | PNG | PDF | SVG | Plotting data |
|---|---|---|---|---|
| Supply and demand quadrants | [PNG](01_supply_demand_quadrants.png) | [PDF](01_supply_demand_quadrants.pdf) | [SVG](01_supply_demand_quadrants.svg) | [CSV](01_supply_demand_quadrants.data.csv) |
| Alignment mix across majors | [PNG](02_alignment_mix_by_major.png) | [PDF](02_alignment_mix_by_major.pdf) | [SVG](02_alignment_mix_by_major.svg) | [CSV](02_alignment_mix_by_major.data.csv) |
| Largest market gaps | [PNG](03_largest_market_gaps.png) | [PDF](03_largest_market_gaps.pdf) | [SVG](03_largest_market_gaps.svg) | [CSV](03_largest_market_gaps.data.csv) |
| Market gaps by major | [PNG](04_market_gaps_by_major.png) | [PDF](04_market_gaps_by_major.pdf) | [SVG](04_market_gaps_by_major.svg) | [CSV](04_market_gaps_by_major.data.csv) |

## Reading the charts

- **Supply and demand quadrants:** Both axes are ranks, not percentages of postings. Duplicate display names retain separate source records. No jitter.
- **Alignment mix across majors:** 100% stacked shares, not counts of students.
- **Largest market gaps:** Top 12 rows, retaining source identity; zero-based bar axis.
- **Market gaps by major:** Diverging colors share the fixed −1 to +1 rank-gap scale.

Regenerate with the project virtual environment:

```sh
.venv/bin/python "analysis being run/create_charts.py" --section 1
```
