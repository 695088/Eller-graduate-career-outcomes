# Synthetic alumni testing data

`generate_synthetic_alumni.py` creates all 21 requested columns using Python's standard library. It defaults to **1,000 records**, random seed **42**, and graduation cohorts **2018–2022**. All person-level records and outcomes are invented. Existing local course, skill, O*NET, and company references provide valid join keys and fixture names.

From the project root:

```sh
python3 data/alumni/generate_synthetic_alumni.py
```

To change size, seed, and cohorts:

```sh
python3 data/alumni/generate_synthetic_alumni.py --rows 5000 --seed 123 --start-year 2019 --end-year 2022
```

The default output folder is the script's folder, even when invoked from another working directory. Use `--output-dir /path/to/folder` to choose another destination. Running again replaces the generated files there. The same seed, arguments, script, and reference files produce identical records.

## Outputs and types

- `synthetic_alumni.csv`: 21 columns in the requested order. Empty cells represent NULL, booleans are `true`/`false`, and arrays are JSON strings inside CSV cells.
- `synthetic_alumni.json`: the same records with native arrays, booleans, numbers, and nulls.
- `salary_bands.csv`: twelve bounded salary bands and their midpoints. Band 1 is $40k–$50k; band 4 is $70k–$80k with midpoint 75000.0. Lower bounds are inclusive and upper bounds exclusive.
- `synthetic_alumni_metadata.json`: seed, cohort range, counts, simulation assumptions, and SHA-256 fingerprints of input references.

`alumni_id` is `ALU_` plus twelve hexadecimal characters from a SHA-256 digest of the synthetic seed and record index, fitting VARCHAR(16). No real identifiers are consumed. Majors use `ACCT`, `FIN`, `MIS`, `MKTG`, `ECON`, `BMGT`, `OSCM`, `ENTR`, and `BNAD`. A secondary major is different from the primary major or NULL. Gender fixture values are `F`, `M`, `Nonbinary`, and `Not disclosed`.

Employer names are normalized consistently for both internship and first-job fields. Industry buckets are hand-selected NAICS-style labels; no formal NAICS classification is assigned. Metro strings are fixture labels and are not joined to a versioned official MSA reference.

## Simulation assumptions

Each record assumes a **complete 36-month follow-up**, including any custom cohorts. Graduation year is a grouping variable; the generator does not derive observation time from today's date. For alumni without a promotion, `months_to_promo` is NULL and the year-three role stays unchanged. For promoted alumni, the time is between 3 and 36 months and the year-three title changes. A senior role can keep the same O*NET occupation code.

The synthetic promotion probability has small programmed associations with internship status, GPA, and a secondary major. Gender has no programmed effect. Major groups are evenly represented; salaries and all other distributions are illustrative testing assumptions. These relationships do not estimate real-world outcomes or support substantive research findings.

`courses_taken` is a partial simulated transcript built from common undergraduate courses, major-related courses, optional secondary-major courses, and electives. It does not enforce degree requirements, prerequisites, or historical course availability. `skills_obtained` is the union of the existing representative course-skill evidence for those selected courses. It simulates skill tags rather than measured mastery or complete curriculum coverage.

For a promotion classifier, `yr3_job_title_raw`, `yr3_onet_soc`, and `months_to_promo` reveal the outcome and should be excluded from entry-time predictors. For a 36-month survival fixture, use `promoted_within_3yr` as the event indicator and replace NULL promotion times with 36 months as the censoring time.

## Validation

Generation validates all records before writing, including schema lengths, unique IDs, valid foreign keys, course-skill consistency, salary consistency, internship fields, and promotion timing. Run the regression checks with:

```sh
python3 -m unittest discover -s data/alumni -p 'test_*.py' -v
```
