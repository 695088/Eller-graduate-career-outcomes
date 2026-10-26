"""Shared paths, loaders, and title normalization for every analysis section."""
import json
import re
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
COMMON = Path(__file__).resolve().parent

ALUMNI_CSV = DATA / "alumni" / "synthetic_alumni.csv"
ALUMNI_METADATA = DATA / "alumni" / "synthetic_alumni_metadata.json"
SKILLS_CSV = DATA / "skills from courses" / "course_skills.csv"
EVIDENCE_CSV = DATA / "skills from courses" / "skill_course_evidence.csv"
COURSES_CSV = DATA / "eller courses" / "processed data" / "eller_courses_combined.csv"
OCCUPATIONS_CSV = ROOT / "onet and jobs" / "onet_occupations.csv"
COMPANY_TIERS_CSV = COMMON / "company_tiers.csv"
METRO_COL_CSV = COMMON / "metro_cost_of_living.csv"

SOC = {"first_onet_soc": pl.Utf8, "yr3_onet_soc": pl.Utf8, "onet_soc_code": pl.Utf8}


def outputs_dir(script_file: str) -> Path:
    out = Path(script_file).resolve().parent / "outputs"
    out.mkdir(exist_ok=True)
    return out


def load_alumni() -> pl.DataFrame:
    """Alumni records with JSON array columns parsed into lists."""
    alumni = pl.read_csv(ALUMNI_CSV, schema_overrides=SOC)
    return alumni.with_columns(
        pl.col("courses_taken").str.json_decode(pl.List(pl.Utf8)),
        pl.col("skills_obtained").str.json_decode(pl.List(pl.Utf8)),
        first_title=pl.col("first_job_title_raw").map_elements(normalize_title, return_dtype=pl.Utf8),
        yr3_title=pl.col("yr3_job_title_raw").map_elements(normalize_title, return_dtype=pl.Utf8),
    )


def alumni_is_synthetic() -> bool:
    return ALUMNI_METADATA.exists() and json.loads(ALUMNI_METADATA.read_text()).get("synthetic", False)


def load_skills() -> pl.DataFrame:
    skills = pl.read_csv(SKILLS_CSV)
    return skills.with_columns(pl.col("search_synonyms").str.json_decode(pl.List(pl.Utf8)))


def load_courses() -> pl.DataFrame:
    """Eller catalog with a 'SUBJ 123' course_key matching alumni courses_taken."""
    courses = pl.read_csv(COURSES_CSV, infer_schema_length=0)
    return courses.select(
        course_key=pl.col("Subject code") + " " + pl.col("Catalog Number"),
        course_title=pl.col("Course Title"),
        description=pl.col("Course Description").fill_null(""),
    ).unique("course_key", keep="first")


def load_occupations() -> pl.DataFrame:
    return pl.read_csv(OCCUPATIONS_CSV, schema_overrides=SOC)


def load_company_tiers() -> pl.DataFrame:
    return pl.read_csv(COMPANY_TIERS_CSV, comment_prefix="#")


def load_metro_cost_of_living() -> pl.DataFrame | None:
    """Regional price parity per metro, or None until the template is filled in."""
    col = pl.read_csv(METRO_COL_CSV, comment_prefix="#")
    return col if col["rpp_index"].null_count() == 0 else None


# Level markers that vary between employers for the same job ("Analyst I",
# "Jr. Analyst", "Assoc. Consultant"). Seniority words such as "Senior" are kept.
_LEVEL_PATTERNS = [r"\b(I|II|III|1|2|3)\b$", r"^\s*(Jr\.?|Junior|Assoc\.?|Associate)\s+(?=\w+\s+\w+)"]


def normalize_title(title: str) -> str:
    clean = title.strip()
    for pattern in _LEVEL_PATTERNS:
        clean = re.sub(pattern, "", clean, flags=re.IGNORECASE).strip()
    clean = clean.replace("HR ", "Human Resources ")
    return re.sub(r"\s+", " ", clean)


# Latent role states used when raw titles are inconsistent. Rules are checked in
# order; the first match wins. Edit here to change the state definitions.
ROLE_STATE_RULES = [
    ("Functional Lead", r"\b(senior|sr\.?|lead|manager|director|head|principal|supervisor)\b"),
    ("Client-Facing Operator", r"\b(consult\w*|audit|tax|advis\w*|sales|account (executive|manager)|relationship|client|recruit\w*|human resources|marketing (specialist|associate)|growth marketing|market development)\b"),
    ("Individual Contributor", r".*"),
]


def role_state(title: str) -> str:
    for state, pattern in ROLE_STATE_RULES:
        if re.search(pattern, title, flags=re.IGNORECASE):
            return state
    return "Individual Contributor"


def import_onet_get():
    """Reuse the cached O*NET client from 'onet and jobs/onet_skills.py'."""
    sys.path.insert(0, str(ROOT / "onet and jobs"))
    import onet_skills

    onet_skills.CACHE_DIR.mkdir(exist_ok=True)
    return onet_skills.get
