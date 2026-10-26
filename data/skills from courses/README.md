# Skills extracted from Eller courses

`course_skills.csv` contains **354 unique skills and domain knowledge areas** extracted by reviewing the titles and descriptions of all **244 course rows** in `processed data/eller_courses_combined.csv`.

The four columns are `skill_id`, `skill_name`, `skill_category`, and `search_synonyms`. Categories start with `Technical /` for tools, methods, and subject expertise, or `Professional /` for communication, leadership, collaboration, thinking, ethics, and career skills. There are 324 technical and 30 professional entries. `SK_001` is SQL.

## Files

- `course_skills.csv`: the requested canonical skills table.
- `skills_schema.csv`: the supplied column-name, type, example, and purpose specification.
- `skill_course_evidence.csv`: representative supporting course references and verbatim source excerpts for every skill. `source_csv_row` counts the CSV header as row 1 and refers to logical CSV records, not physical text lines. Cross-listed offerings retain their subject and catalog number alongside the original course ID.
- `extraction_summary.json`: source fingerprint and extraction counts.
- `extract_course_skills.py`: curated definitions, source references, and reproducible CSV export using Python's standard library.

## Interpretation

The dictionary includes explicit course topics and competencies developed through assignments, such as thesis writing, presentations, and teamwork. It consolidates naming variants while retaining meaningful specializations, such as linear versus logistic regression. Domain knowledge is included alongside practical skills, so the dictionary can support curriculum and employment-text comparisons.

Only course titles and descriptions establish a skill's inclusion. Requisites, enrollment rules, and generic internship or independent-study descriptions do not establish additional skills. Prior knowledge assumed by a course, such as the probability prerequisites in BNAN 276, is not treated as a newly taught skill. Routine submission deadlines do not establish time-management instruction.

Coverage includes every level present in the source, including graduate courses. Conditional topics remain included: ECON 454 says SQL **may** be used, and several statistical methods **may** be covered. Bloomberg is named in FIN 401's title. Evidence records distinguish title evidence from description evidence and preserve conditional wording. A catalog topic indicates curriculum coverage, not verified student proficiency.

`search_synonyms` is a JSON array serialized inside a CSV field; parse it as JSON to obtain `ARRAY<STR>`. Entries are lowercase literal lookup terms, not executable regular expressions. Escape them before building regexes and apply word boundaries and appropriate context for ambiguous terms. SQL-family aliases such as PostgreSQL, MySQL, and T-SQL support future text matching; they do not claim these specific products are taught. Synonyms alone do not create additional skill records.

Evidence references are curated supporting examples, not an exhaustive course-to-skill bridge table. Course rows without an evidence reference can be generic offerings or redundant support for an existing skill. Every dictionary skill has at least one supporting excerpt.

## Regeneration

From the project root, run:

```sh
python3 'skills from courses/extract_course_skills.py'
```

The exporter verifies the source file's SHA-256 before using curated row references, and validates unique names, field lengths, and supporting phrases before writing the outputs. Keep existing definition order and append new skills to preserve assigned IDs when extending this dictionary. If the source CSV changes, review the row references and update the expected fingerprint before regenerating.
