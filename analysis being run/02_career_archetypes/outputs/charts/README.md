# 02_career_archetypes charts

Font: **Graphik**; code typography: **B612 Mono**.

All alumni-dependent results use synthetic testing data. Each figure includes a source caption. Original output tables are unchanged.

| Figure | PNG | PDF | SVG | Plotting data |
|---|---|---|---|---|
| Archetype cluster selection | [PNG](01_cluster_selection.png) | [PDF](01_cluster_selection.pdf) | [SVG](01_cluster_selection.svg) | [CSV](01_cluster_selection.data.csv) |
| Pooled archetype sizes and promotion rates | [PNG](02_pooled_archetype_profiles.png) | [PDF](02_pooled_archetype_profiles.pdf) | [SVG](02_pooled_archetype_profiles.svg) | [CSV](02_pooled_archetype_profiles.data.csv) |
| Archetype major composition | [PNG](03_archetype_major_composition.png) | [PDF](03_archetype_major_composition.pdf) | [SVG](03_archetype_major_composition.svg) | [CSV](03_archetype_major_composition.data.csv) |
| Archetype industry mix | [PNG](04_archetype_industry_mix.png) | [PDF](04_archetype_industry_mix.pdf) | [SVG](04_archetype_industry_mix.svg) | [CSV](04_archetype_industry_mix.data.csv) |
| Archetype geographic concentration | [PNG](05_archetype_geographic_concentration.png) | [PDF](05_archetype_geographic_concentration.pdf) | [SVG](05_archetype_geographic_concentration.svg) | [CSV](05_archetype_geographic_concentration.data.csv) |

## Reading the charts

- **Archetype cluster selection:** Shared score scale; points represent tried k values, not a learning curve.
- **Pooled archetype sizes and promotion rates:** Point rates have no invented intervals. Full labels and counts remain in plotting data.
- **Archetype major composition:** Counts computed from saved pooled assignments, avoiding rounding in the major_mix display field.
- **Archetype industry mix:** Shared 0–100% sequential color scale; absent combinations have zero count.
- **Archetype geographic concentration:** Fixed LQ color limits 0.5–1.5, midpoint 1; hub outlines are descriptive, not significance marks.

Regenerate with the project virtual environment:

```sh
.venv/bin/python "analysis being run/create_charts.py" --section 2
```
