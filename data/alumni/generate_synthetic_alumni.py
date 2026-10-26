#!/usr/bin/env python3
"""Generate synthetic alumni fixtures with local course, skill, and occupation keys.

Standard library only. Defaults: 1,000 alumni, seed 42, cohorts 2018–2022.
All records assume a complete 36-month follow-up. Simulation assumptions are
for pipeline testing, not estimates of Eller alumni or employer outcomes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FIELDS = [
    'alumni_id', 'grad_year', 'major', 'secondary_major', 'gender',
    'had_internship', 'internship_employer', 'first_job_title_raw',
    'first_onet_soc', 'employer_clean', 'industry_sector', 'location_metro',
    'starting_salary_band', 'starting_salary_mid', 'yr3_job_title_raw',
    'yr3_onet_soc', 'promoted_within_3yr', 'months_to_promo',
    'courses_taken', 'skills_obtained', 'gpa_final',
]
TEXT_LIMITS = {
    'alumni_id': 16, 'major': 32, 'secondary_major': 32, 'gender': 16,
    'internship_employer': 64, 'first_job_title_raw': 128, 'first_onet_soc': 10,
    'employer_clean': 64, 'industry_sector': 64, 'location_metro': 64,
    'yr3_job_title_raw': 128, 'yr3_onet_soc': 10,
}
# Canonical major codes; ENTR is a synthetic grouping, not a source department.
MAJOR_SUBJECTS = {
    'ACCT': ('ACCT',), 'FIN': ('FIN',), 'MIS': ('MIS',), 'MKTG': ('MKTG',),
    'ECON': ('ECON',), 'BMGT': ('MGMT',), 'OSCM': ('OSCM', 'MGMT'),
    'ENTR': ('MGMT', 'FIN', 'MKTG'), 'BNAD': ('BNAD', 'MGMT'),
}
# (entry SOC, raw title variants, promoted SOC, promoted raw title).
# A promotion often retains the same occupation code.
ROLES = {
    'ACCT': [
        ('13-2011.00', ('Staff Accountant', 'Accountant I'), '13-2011.00', 'Senior Accountant'),
        ('13-2011.00', ('Audit Associate', 'Tax Associate I'), '13-2011.00', 'Senior Audit/Tax Associate'),
    ],
    'FIN': [
        ('13-2051.00', ('Financial Analyst I', 'Jr. Investment Analyst'), '13-2051.00', 'Senior Financial Analyst'),
        ('13-2054.00', ('Risk Analyst I', 'Financial Risk Analyst'), '13-2054.00', 'Senior Risk Analyst'),
    ],
    'MIS': [
        ('15-1211.00', ('Assoc. Tech Consultant I', 'Systems Analyst I'), '13-1111.00', 'Senior Consultant'),
        ('15-1211.00', ('IT Business Analyst', 'Jr. Systems Analyst'), '15-1211.00', 'Senior Systems Analyst'),
    ],
    'MKTG': [
        ('13-1161.00', ('Marketing Analyst I', 'Digital Marketing Associate'), '13-1161.00', 'Senior Marketing Analyst'),
        ('13-1161.00', ('Market Research Associate', 'Marketing Specialist I'), '13-1161.00', 'Senior Marketing Specialist'),
    ],
    'ECON': [
        ('13-2051.00', ('Economic Research Analyst', 'Research Analyst I'), '13-2051.00', 'Senior Research Analyst'),
        ('13-1111.00', ('Business Analyst I', 'Economic Consulting Analyst'), '13-1111.00', 'Senior Business Analyst'),
    ],
    'BMGT': [
        ('13-1071.00', ('HR Associate', 'Human Resources Specialist I'), '13-1071.00', 'Senior HR Specialist'),
        ('13-1111.00', ('Operations Analyst I', 'Management Consulting Associate'), '13-1111.00', 'Senior Operations Analyst'),
    ],
    'OSCM': [
        ('13-1081.00', ('Supply Chain Analyst I', 'Logistics Coordinator'), '13-1081.00', 'Senior Supply Chain Analyst'),
        ('13-1081.00', ('Procurement Analyst I', 'Logistics Analyst'), '13-1081.00', 'Senior Logistics Analyst'),
    ],
    'ENTR': [
        ('13-1199.00', ('Business Operations Associate', 'Startup Operations Analyst'), '13-1199.00', 'Senior Business Operations Specialist'),
        ('13-1161.00', ('Growth Marketing Associate', 'Market Development Analyst'), '13-1161.00', 'Senior Growth Marketing Specialist'),
    ],
    'BNAD': [
        ('13-1199.00', ('Business Operations Analyst I', 'Business Associate'), '13-1199.00', 'Senior Business Operations Analyst'),
        ('13-1111.00', ('Business Analyst I', 'Management Analyst I'), '13-1111.00', 'Senior Management Analyst'),
    ],
}
# Hand-selected fixture buckets: NAICS-style labels, not formal NAICS coding.
EMPLOYERS = {
    'Deloitte': 'Consulting & Advisory', 'Accenture': 'Consulting & Advisory',
    'Protiviti': 'Consulting & Advisory', 'PwC': 'Consulting & Advisory',
    'KPMG LLP': 'Consulting & Advisory', 'Ernst & Young': 'Consulting & Advisory',
    'JPMorgan Chase': 'Financial Services', 'Charles Schwab': 'Financial Services',
    'Wells Fargo': 'Financial Services', 'Vanguard': 'Financial Services',
    'Honeywell': 'Manufacturing', 'Intel': 'Manufacturing',
    'Microsoft': 'Technology', 'Google': 'Technology', 'Oracle': 'Technology',
    'Amazon': 'Retail & E-Commerce', 'Target': 'Retail & E-Commerce',
    'Nielsen': 'Market Research', 'Madden Media': 'Advertising & Marketing',
    'Knight Transportation': 'Transportation & Logistics',
}
EMPLOYER_ALIASES = {'JP Morgan': 'JPMorgan Chase', 'Chase': 'JPMorgan Chase', 'Intel Corporation': 'Intel'}
MAJOR_EMPLOYERS = {
    'ACCT': ('Deloitte', 'PwC', 'KPMG LLP', 'Ernst & Young', 'Honeywell'),
    'FIN': ('JPMorgan Chase', 'Charles Schwab', 'Wells Fargo', 'Vanguard', 'Honeywell'),
    'MIS': ('Deloitte', 'Accenture', 'Protiviti', 'Microsoft', 'Google', 'Oracle'),
    'MKTG': ('Nielsen', 'Madden Media', 'Amazon', 'Target', 'Google'),
    'ECON': ('Deloitte', 'JPMorgan Chase', 'Wells Fargo', 'Nielsen'),
    'BMGT': ('Honeywell', 'Amazon', 'Target', 'Accenture'),
    'OSCM': ('Honeywell', 'Intel', 'Amazon', 'Target', 'Knight Transportation'),
    'ENTR': ('Microsoft', 'Google', 'Oracle', 'Amazon', 'Madden Media'),
    'BNAD': ('Honeywell', 'Amazon', 'Target', 'Wells Fargo', 'Accenture'),
}
METROS = (
    'Phoenix-Mesa-Chandler, AZ', 'Tucson, AZ', 'Los Angeles-Long Beach-Anaheim, CA',
    'San Francisco-Oakland-Berkeley, CA', 'Dallas-Fort Worth-Arlington, TX',
    'New York-Newark-Jersey City, NY-NJ', 'Denver-Aurora-Centennial, CO',
    'Chicago-Naperville-Elgin, IL-IN', 'Seattle-Tacoma-Bellevue, WA',
)
# These are fixture labels, not a versioned official MSA reference dataset.
METRO_WEIGHTS = (35, 15, 10, 7, 8, 7, 6, 6, 6)
CORE_COURSES = ('ACCT 200', 'ACCT 210', 'BCOM 214', 'BNAN 276', 'BNAN 277', 'ECON 200', 'MGMT 202')
SALARY_BANDS = [
    {'starting_salary_band': i, 'lower_usd_inclusive': 30000 + i * 10000,
     'upper_usd_exclusive': 40000 + i * 10000, 'starting_salary_mid': float(35000 + i * 10000)}
    for i in range(1, 13)
]


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def load_references(root: Path) -> dict:
    paths = {
        'courses': root / 'data/eller courses/processed data/eller_courses_combined.csv',
        'skills': root / 'data/skills from courses/course_skills.csv',
        'evidence': root / 'data/skills from courses/skill_course_evidence.csv',
        'occupations': root / 'onet and jobs/onet_occupations.csv',
        'companies': root / 'data/companies/companies.json',
    }
    for path in paths.values():
        if not path.is_file():
            raise ValueError(f'Required local reference is missing: {path}')
    course_rows = read_csv(paths['courses'])
    courses = {f"{c['Subject code']} {c['Catalog Number']}": c for c in course_rows}
    skills = {s['skill_id'] for s in read_csv(paths['skills'])}
    occupations = {o['onet_soc_code'] for o in read_csv(paths['occupations'])}
    companies = {EMPLOYER_ALIASES.get(c, c) for c in json.loads(paths['companies'].read_text(encoding='utf-8'))}
    if not set(EMPLOYERS) <= companies:
        raise ValueError(f'Fixture employers absent from company roster: {set(EMPLOYERS) - companies}')
    if not set(CORE_COURSES) <= courses.keys():
        raise ValueError('One or more core courses are missing from the course catalog.')
    for profiles in ROLES.values():
        for entry, _, followup, _ in profiles:
            if not {entry, followup} <= occupations:
                raise ValueError(f'Fixture occupation is missing from O*NET reference: {entry}, {followup}')
    course_skills = defaultdict(set)
    for row in read_csv(paths['evidence']):
        course = f"{row['subject_code']} {row['catalog_number']}"
        if course not in courses or row['skill_id'] not in skills:
            raise ValueError(f'Invalid course/skill reference in evidence: {course}, {row["skill_id"]}')
        course_skills[course].add(row['skill_id'])
    # Restrict to undergraduate content with useful evidence. Exclude generic
    # internships, honors, capstones, and independent studies as electives.
    pools = {}
    for major, subjects in MAJOR_SUBJECTS.items():
        pool = []
        for key, row in sorted(courses.items()):
            number_match = re.match(r'^\d+', row['Catalog Number'])
            if not number_match:
                continue
            number = int(number_match.group())
            if (row['Subject code'] not in subjects or not 300 <= number < 490
                    or key not in course_skills or key in CORE_COURSES):
                continue
            if major == 'OSCM' and row['Subject code'] == 'MGMT' and number not in {465, 473, 477, 485}:
                continue
            if major == 'ENTR' and key not in {
                'MGMT 380', 'MGMT 381', 'MGMT 382', 'MGMT 448', 'MGMT 468',
                'MGMT 471', 'MGMT 488', 'FIN 303', 'FIN 434', 'FIN 480', 'MKTG 459', 'MKTG 480',
            }:
                continue
            pool.append(key)
        if len(pool) < 3:
            raise ValueError(f'Not enough evidenced courses for {major}: {pool}')
        pools[major] = pool
    return dict(paths=paths, courses=courses, skills=skills, occupations=occupations,
                course_skills=course_skills, pools=pools)


def generate_records(count: int, seed: int, start_year: int, end_year: int, refs: dict) -> list[dict]:
    if count < 1 or not 1900 <= start_year <= end_year <= 2100:
        raise ValueError('Use a positive row count and 1900 <= start-year <= end-year <= 2100.')
    rng = random.Random(seed)
    majors = tuple(MAJOR_SUBJECTS)
    records = []
    salary_means = {'ACCT': 65000, 'FIN': 73000, 'MIS': 78000, 'MKTG': 59000,
                    'ECON': 68000, 'BMGT': 60000, 'OSCM': 67000, 'ENTR': 62000, 'BNAD': 60000}
    for index in range(count):
        # Cycle before shuffling to ensure useful major representation in small samples.
        major = majors[index % len(majors)]
        secondary = rng.choice([m for m in majors if m != major]) if rng.random() < 0.16 else None
        grad_year = rng.randint(start_year, end_year)
        gender = rng.choices(('F', 'M', 'Nonbinary', 'Not disclosed'), (48, 46, 3, 3))[0]
        gpa = round(min(4.0, max(2.0, rng.gauss(3.30, 0.35))), 2)
        had_internship = rng.random() < 0.70
        employer = rng.choice(MAJOR_EMPLOYERS[major])
        if had_internship:
            # 45% explicitly assigned conversion, plus chance employer matches.
            internship_employer = employer if rng.random() < 0.45 else rng.choice(tuple(EMPLOYERS))
        else:
            internship_employer = None
        entry_soc, titles, senior_soc, senior_title = rng.choice(ROLES[major])
        first_title = rng.choice(titles)
        selected = set(CORE_COURSES)
        pool = refs['pools'][major]
        selected.update(rng.sample(pool, min(len(pool), rng.randint(6, 10))))
        if secondary:
            pool = refs['pools'][secondary]
            selected.update(rng.sample(pool, min(len(pool), rng.randint(3, 5))))
        electives = sorted(set().union(*map(set, refs['pools'].values())) - selected)
        selected.update(rng.sample(electives, min(len(electives), rng.randint(1, 3))))
        courses_taken = sorted(selected)
        # The local evidence bridge is representative, so these are simulated
        # skill tags, not a claim that completion proves mastery.
        skills_obtained = sorted(set().union(*(refs['course_skills'][c] for c in courses_taken)))
        metro = rng.choices(METROS, METRO_WEIGHTS)[0]
        location_adjustment = 10000 if metro in {METROS[3], METROS[5], METROS[8]} else 0
        salary_draw = rng.gauss(salary_means[major] + 2000 * had_internship
                               + 1200 * (grad_year - 2020) + location_adjustment, 9000)
        salary_band = max(1, min(12, math.floor((salary_draw - 40000) / 10000) + 1))
        salary_mid = SALARY_BANDS[salary_band - 1]['starting_salary_mid']
        # Weak, deliberately planted testing relationships. Gender, eventual
        # titles, and occupation codes are not inputs to promotion probability.
        log_odds = -0.10 + 0.40 * had_internship + 0.45 * (gpa - 3.2) + 0.15 * bool(secondary)
        promoted = rng.random() < 1 / (1 + math.exp(-log_odds))
        months = round(min(36.0, max(3.0, rng.gauss(23.0 - 2.0 * had_internship, 6.0))), 1) if promoted else None
        synthetic_hash = hashlib.sha256(f'synthetic-alumni|{seed}|{index}'.encode()).hexdigest()[:12]
        records.append(dict(
            alumni_id=f'ALU_{synthetic_hash}', grad_year=grad_year, major=major,
            secondary_major=secondary, gender=gender, had_internship=had_internship,
            internship_employer=internship_employer, first_job_title_raw=first_title,
            first_onet_soc=entry_soc, employer_clean=employer,
            industry_sector=EMPLOYERS[employer], location_metro=metro,
            starting_salary_band=salary_band, starting_salary_mid=salary_mid,
            yr3_job_title_raw=senior_title if promoted else first_title,
            yr3_onet_soc=senior_soc if promoted else entry_soc,
            promoted_within_3yr=promoted, months_to_promo=months,
            courses_taken=courses_taken, skills_obtained=skills_obtained, gpa_final=gpa,
        ))
    rng.shuffle(records)
    validate_records(records, refs)
    return records


def validate_records(records: list[dict], refs: dict) -> None:
    """Check schema types, foreign keys, and cross-field consistency before export."""
    seen_ids = set()
    for row in records:
        def require(condition, message):
            if not condition:
                raise ValueError(f'{row.get("alumni_id")}: {message}')
        require(set(row) == set(FIELDS), 'Unexpected or missing columns')
        require(row['alumni_id'] not in seen_ids, 'Duplicate alumni ID')
        seen_ids.add(row['alumni_id'])
        for field, limit in TEXT_LIMITS.items():
            value = row[field]
            require(value is None or isinstance(value, str) and 0 < len(value) <= limit, f'Invalid {field}')
        require(type(row['grad_year']) is int, 'Graduation year must be an integer')
        require(row['major'] in MAJOR_SUBJECTS, 'Invalid major')
        require(row['secondary_major'] is None or row['secondary_major'] in MAJOR_SUBJECTS
                and row['secondary_major'] != row['major'], 'Invalid secondary major')
        require(row['gender'] in {'F', 'M', 'Nonbinary', 'Not disclosed'}, 'Invalid gender value')
        require(type(row['had_internship']) is bool and type(row['promoted_within_3yr']) is bool, 'Invalid boolean')
        require((row['internship_employer'] is not None) == row['had_internship'], 'Internship fields disagree')
        require(row['internship_employer'] is None or row['internship_employer'] in EMPLOYERS, 'Unknown internship employer')
        require(row['industry_sector'] == EMPLOYERS[row['employer_clean']], 'Employer and industry disagree')
        require(row['location_metro'] in METROS, 'Unknown metro')
        require(type(row['starting_salary_band']) is int and 1 <= row['starting_salary_band'] <= 12, 'Invalid salary band')
        require(row['starting_salary_mid'] == SALARY_BANDS[row['starting_salary_band'] - 1]['starting_salary_mid'], 'Salary fields disagree')
        require(row['first_onet_soc'] in refs['occupations'] and row['yr3_onet_soc'] in refs['occupations'], 'Unknown occupation code')
        require(2.0 <= row['gpa_final'] <= 4.0, 'Invalid GPA')
        for field, allowed in [('courses_taken', refs['courses']), ('skills_obtained', refs['skills'])]:
            values = row[field]
            require(isinstance(values, list) and bool(values) and len(values) == len(set(values)), f'Invalid array: {field}')
            require(all(isinstance(v, str) and v in allowed for v in values), f'Invalid foreign key in {field}')
        expected_skills = set().union(*(refs['course_skills'][c] for c in row['courses_taken']))
        require(set(row['skills_obtained']) == expected_skills, 'Skills do not agree with selected course evidence')
        months = row['months_to_promo']
        if row['promoted_within_3yr']:
            require(isinstance(months, float) and 0 < months <= 36, 'Invalid promotion time')
            require(row['yr3_job_title_raw'] != row['first_job_title_raw'], 'Promoted title did not change')
        else:
            require(months is None, 'Unpromoted alumni must have null promotion time')
            require(row['yr3_job_title_raw'] == row['first_job_title_raw'] and row['yr3_onet_soc'] == row['first_onet_soc'], 'Unpromoted role changed')


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value) if isinstance(value, list)
                             else str(value).lower() if isinstance(value, bool)
                             else value for key, value in row.items()})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', type=int, default=1000, help='Number of synthetic alumni (default: 1000)')
    parser.add_argument('--seed', type=int, default=42, help='Random seed (default: 42)')
    parser.add_argument('--start-year', type=int, default=2018)
    parser.add_argument('--end-year', type=int, default=2022)
    parser.add_argument('--project-root', type=Path, default=ROOT, help='Root containing data/ and onet and jobs/')
    parser.add_argument('--output-dir', type=Path, default=HERE, help='Output directory (default: script folder)')
    args = parser.parse_args()
    try:
        refs = load_references(args.project_root.resolve())
        records = generate_records(args.rows, args.seed, args.start_year, args.end_year, refs)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f'Error: {error}\n')
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / 'synthetic_alumni.csv', FIELDS, records)
    (output / 'synthetic_alumni.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
    write_csv(output / 'salary_bands.csv', list(SALARY_BANDS[0]), SALARY_BANDS)
    metadata = {
        'synthetic': True, 'rows': len(records), 'seed': args.seed,
        'cohort_years': [args.start_year, args.end_year], 'follow_up_months': 36,
        'major_counts': dict(sorted(Counter(r['major'] for r in records).items())),
        'promoted_count': sum(r['promoted_within_3yr'] for r in records),
        'internship_count': sum(r['had_internship'] for r in records),
        'reference_sha256': {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in refs['paths'].items()},
        'assumptions': [
            'All identities, demographics, course histories, salaries and employment outcomes are invented.',
            'Every record assumes a complete 36-month follow-up, regardless of cohort year.',
            'Major groups are evenly represented; distributions do not estimate real alumni outcomes.',
            'All recorded skills are the union of representative local course-skill evidence for selected courses.',
            'Selected courses are a partial synthetic transcript; degree, prerequisite and historical catalog requirements are not enforced.',
            'Promotion probability uses internship status, GPA and secondary major; gender has no programmed effect.',
            'Metros are fixture labels; industry buckets are hand-selected NAICS-style labels without official code verification.',
            'A promotion can retain the same O*NET occupation code.',
            'CSV nulls are empty cells; booleans are true/false; arrays are JSON strings.',
        ],
    }
    (output / 'synthetic_alumni_metadata.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(f'Generated and validated {len(records):,} synthetic alumni in {output}')
    print(f'CSV: {output / "synthetic_alumni.csv"}')
    print(f'JSON: {output / "synthetic_alumni.json"}')


if __name__ == '__main__':
    main()
