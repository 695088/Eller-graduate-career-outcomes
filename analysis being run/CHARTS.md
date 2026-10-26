# Research charts

**20 figures** visualize the saved tables in the four analysis sections. Each figure is in its section's `outputs/charts/` folder, with a 300 dpi PNG, PDF, SVG, and `.data.csv` file containing the rows actually plotted. Original analysis tables are preserved.

| Section | Figures | Browse charts |
|---|---:|---|
| Curriculum alignment | 4 | [Chart index](01_curriculum_alignment/outputs/charts/README.md) |
| Career archetypes | 5 | [Chart index](02_career_archetypes/outputs/charts/README.md) |
| Transition dynamics | 5 | [Chart index](03_transition_dynamics/outputs/charts/README.md) |
| Hedonic salary | 6 | [Chart index](04_hedonic_salary/outputs/charts/README.md) |

## Format

The renderer imports `configure`, `clean_axes`, `bars`, `color`, and `export` from the installed `matplotlib-research-charts` skill. It uses the pinned Tailwind palette, a white canvas, quiet regular-weight titles, thin axes, matching bar outlines, direct labels, and restrained decorative dot grids. Numeric data remain in data coordinates; dot grids are decorative.

The installed **Graphik** regular face was available and used for chart text. **B612 Mono** is registered for literal/code typography; there are no token-chip panels in these statistical charts. The renderer falls back to **IBM Plex Sans** when Graphik is unavailable and fails explicitly if neither is available. No font files are copied into the project. Mathematical operators that are unsupported by the installed Graphik face are written as ordinary words (for example, `Phi` and `chi-square`) to avoid missing glyphs or an undisclosed alternate typeface. PDF embeds font subsets and SVG uses paths to preserve appearance.

Figure sizes are chosen for readable standalone figures (approximately 11–15 inches wide), including wider labels and larger small multiples. A figure should be exported again at an appropriate font size if needed for a narrow paper column.

## Quantitative conventions

- Nonnegative comparison bars begin at zero. Signed coefficient estimates use points, intervals, and a zero reference line.
- Quadrant charts show percentile-rank scores, not posting counts. Source identity remains intact when a course skill and a Hot Technology have the same display name.
- Probability and composition plots label their denominators. Heatmap percentage scales run from 0% to 100%; geography uses a fixed location-quotient scale centered at 1.
- Transition intervals are the **95% Wilson score intervals** already in the analysis outputs. An unobserved Functional Lead entry-state row is not manufactured.
- OLS coefficient intervals are the saved **pointwise 95% HC1-robust intervals**, transformed to dollars as `(exp(log-coefficient endpoint) - 1) × mean salary`. They are not simultaneous or FDR-adjusted intervals. The selected skill-coefficient figure notes that no estimated bundle passes FDR q < 0.05.
- Cross-validation R² error bars show **one standard deviation across folds**, not confidence intervals. No RMSE error bars or other unavailable uncertainty is invented.
- SHAP plots use aggregate tables rather than a fabricated beeswarm. Importance is mean absolute attribution, not a causal premium. The top-interaction table contains individual off-diagonal entries; the requested-pair table uses doubled joint interactions, so their axes and captions distinguish these scales.
- Missing interaction estimates remain missing. The requested-pair figure shows zero only for estimated pairs whose reported interaction is zero.
- The year-three transition endpoint is observed; years six and nine are clearly labeled **absorbing-chain scenarios**, with dashed paths. The caption states that the saved first-order Markov test rejects the assumption.

## Scope and reproducibility

All alumni-dependent charts use the current **synthetic testing data**, with 15,000 alumni in the saved run. They describe the generator and model pipeline, not observed outcomes of real graduates. Market inputs come from the saved O*NET tables; chart rendering performs no network requests and refits no models. Course-derived skills are exposure tags, not demonstrated proficiency.

Regenerate all charts from the project root:

```sh
.venv/bin/python "analysis being run/create_charts.py"
```

Render a single section:

```sh
.venv/bin/python "analysis being run/create_charts.py" --section 3
```

Use `--skill-root /path/to/matplotlib-research-charts` if the skill is installed elsewhere, or set `MATPLOTLIB_RESEARCH_CHARTS_SKILL`. `--font-dir /path/to/fonts` registers locally supplied licensed fonts. The default skill path is resolved from the current user's home directory rather than the skill author's machine.

Each section has a `charts_manifest.json` recording the actual fonts, source-table SHA-256 hashes, plot selection, and interpretation notes. The root `charts_manifest.json` describes the latest render invocation and also fingerprints the alumni file. A section-only render updates that section and records only the figures rendered in that invocation in the root manifest.
