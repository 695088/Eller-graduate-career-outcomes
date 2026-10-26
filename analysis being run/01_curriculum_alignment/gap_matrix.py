"""Curriculum alignment and gap matrix.

Every term (course skill or O*NET Hot Technology) gets a supply score from its
TF-IDF cosine similarity to Eller course descriptions and a demand score from
O*NET task, technology, and job-posting data for the occupations alumni hold.
Percentile ranks on both axes place each term in a quadrant:

    High Alignment  demand >= cutoff, supply >= cutoff
    Market Gap      demand >= cutoff, supply <  cutoff
    Over-Supply     demand <  cutoff, supply >= cutoff
    Low Priority    demand <  cutoff, supply <  cutoff

Run build_market_demand.py first.
"""
import re
import sys
from pathlib import Path

import numpy as np
import polars as pl
from nltk.stem import PorterStemmer
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import data  # noqa: E402

OUT = data.outputs_dir(__file__)

QUADRANT_CUTOFF = 0.5        # percentile rank splitting high from low
CORE_COURSE_SHARE = 0.5      # a course is "core" if at least this share of alumni took it
COURSE_MATCH_SIM = 0.20      # a course "covers" a term at or above this cosine similarity
TECH_MATCH_SIM = 0.50        # a course skill inherits a Hot Technology's postings at or above this


_stemmer = PorterStemmer()


def stemmed_tokens(text: str) -> list[str]:
    """Lowercase, drop stop words, Porter-stem ("negotiation" and "negotiate" -> "negoti")."""
    words = re.findall(r"[a-z0-9][a-z0-9+#]*", text.lower())
    return [_stemmer.stem(w) for w in words if w not in ENGLISH_STOP_WORDS]


def split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?;])\s+", text) if s.strip()] or [""]


def pct_rank(values: np.ndarray) -> np.ndarray:
    """Average-rank percentile in (0, 1]; ties share a rank."""
    return pl.Series(values).rank("average").to_numpy() / len(values)


def build_terms(skills: pl.DataFrame, national: pl.DataFrame) -> pl.DataFrame:
    """One row per term with the phrases used to match it (name plus synonyms)."""
    course_terms = skills.select(
        term_id="skill_id",
        term="skill_name",
        term_source=pl.lit("course_skill"),
        category="skill_category",
        phrases=pl.concat_list([pl.col("skill_name").str.to_lowercase(), "search_synonyms"]).list.unique(maintain_order=True),
    )
    tech_terms = national.select(
        term_id=pl.lit("HT_") + pl.int_range(1, pl.len() + 1).cast(pl.Utf8).str.zfill(3),
        term="technology",
        term_source=pl.lit("onet_hot_technology"),
        category=pl.lit("Market / Technology"),
        phrases=pl.concat_list([pl.col("technology")]),
    )
    return pl.concat([course_terms, tech_terms])


def phrase_max_similarity(phrase_vecs, phrase_term, n_terms: int, doc_vecs) -> np.ndarray:
    """Term x document cosine similarity, taking the best-matching phrase of each term."""
    sim = cosine_similarity(phrase_vecs, doc_vecs)
    out = np.zeros((n_terms, sim.shape[1]))
    np.maximum.at(out, phrase_term, sim)
    return out


def score(terms, course_sim, courses, alumni, weights, tech_postings, national, profile_sim, profile_codes, term_tech_sim):
    """Supply and demand metrics for one population (all alumni or one major)."""
    n_alumni = len(alumni)

    # Supply: similarity to the catalog, to core courses, and alumni exposure.
    enrollment = (
        alumni.select(pl.col("courses_taken").explode().alias("course_key"))
        .group_by("course_key").len("n").with_columns(share=pl.col("n") / n_alumni)
    )
    share = dict(zip(enrollment["course_key"], enrollment["share"]))
    course_share = np.array([share.get(k, 0.0) for k in courses["course_key"]])
    core_mask = course_share >= CORE_COURSE_SHARE

    catalog_similarity = course_sim.max(axis=1)
    best_course = courses["course_key"].to_numpy()[course_sim.argmax(axis=1)]
    core_similarity = course_sim[:, core_mask].max(axis=1) if core_mask.any() else np.zeros(len(terms))

    # Exposure: share of alumni who took at least one course covering the term.
    covers = (course_sim >= COURSE_MATCH_SIM).astype(np.float32)
    key_index = {k: i for i, k in enumerate(courses["course_key"])}
    taken = np.zeros((n_alumni, len(courses)), dtype=np.float32)
    for row, course_list in enumerate(alumni["courses_taken"]):
        taken[row, [key_index[c] for c in course_list if c in key_index]] = 1
    exposure = ((taken @ covers.T) > 0).mean(axis=0)

    # Demand 1: alumni-weighted share of target-occupation postings naming the technology.
    w = dict(zip(weights["onet_soc_code"], weights["weight"]))
    posting_share = (
        tech_postings.with_columns(w=pl.col("onet_soc_code").replace_strict(w, default=0.0))
        .group_by("technology").agg(posting_share=(pl.col("w") * pl.col("posting_pct") / 100).sum())
    )
    tech_share = dict(zip(posting_share["technology"], posting_share["posting_share"]))
    tech_national = dict(zip(national["technology"], national["national_job_postings"]))

    # Course skills inherit postings from a matching Hot Technology; among several
    # matches (e.g. SQL -> PostgreSQL, Structured query language SQL) the most-posted wins.
    tech_titles = national["technology"].to_list()
    tech_postings_national = national["national_job_postings"].to_numpy()
    matched_tech = []
    for i, (term, source) in enumerate(zip(terms["term"], terms["term_source"])):
        if source == "onet_hot_technology":
            matched_tech.append(term)
            continue
        candidates = np.where(term_tech_sim[i] >= TECH_MATCH_SIM)[0]
        best = candidates[tech_postings_national[candidates].argmax()] if len(candidates) else None
        matched_tech.append(tech_titles[best] if best is not None else None)
    share_vals = np.array([tech_share.get(t, 0.0) if t else 0.0 for t in matched_tech])
    national_vals = np.array([tech_national.get(t, 0) if t else 0 for t in matched_tech])

    # Demand 2: alumni-weighted best match against each occupation's tasks and technology examples.
    task_relevance = np.zeros(len(terms))
    for code, weight in w.items():
        mask = profile_codes == code
        if mask.any():
            task_relevance += weight * profile_sim[:, mask].max(axis=1)

    demand_raw = task_relevance + share_vals
    demand_score = pct_rank(demand_raw)
    supply_score = (pct_rank(catalog_similarity) + pct_rank(exposure)) / 2

    high_d, high_s = demand_score >= QUADRANT_CUTOFF, supply_score >= QUADRANT_CUTOFF
    quadrant = np.select(
        [high_d & high_s, high_d & ~high_s, ~high_d & high_s],
        ["High Alignment", "Market Gap", "Over-Supply"],
        "Low Priority",
    )
    return terms.select("term_id", "term", "term_source", "category").with_columns(
        catalog_similarity=catalog_similarity.round(4),
        best_matching_course=best_course,
        core_similarity=core_similarity.round(4),
        alumni_exposure=exposure.round(4),
        matched_hot_technology=pl.Series(matched_tech, dtype=pl.Utf8),
        target_posting_share=share_vals.round(4),
        national_job_postings=national_vals.astype(int),
        task_relevance=task_relevance.round(4),
        demand_score=demand_score.round(4),
        supply_score=supply_score.round(4),
        alignment_gap=(demand_score - supply_score).round(4),
        quadrant=quadrant,
    )


def main():
    alumni = data.load_alumni()
    skills = data.load_skills()
    courses = data.load_courses()
    national = pl.read_csv(OUT / "market_hot_technologies.csv")
    weights = pl.read_csv(OUT / "target_occupation_weights.csv", schema_overrides=data.SOC)
    tech_postings = pl.read_csv(OUT / "occupation_technology_postings.csv", schema_overrides=data.SOC)
    profile_texts = pl.read_csv(OUT / "occupation_profile_texts.csv", schema_overrides=data.SOC)

    terms = build_terms(skills, national)
    phrases = terms.select(pl.int_range(pl.len()).alias("term_index"), "phrases").explode("phrases")
    phrase_term = phrases["term_index"].to_numpy()

    # Course descriptions are compared sentence by sentence so a single clear
    # mention ("SQL programming may be used") is not diluted by the rest of the text.
    sentences = courses.select(
        pl.int_range(pl.len()).alias("course_index"),
        pl.col("description").map_elements(split_sentences, return_dtype=pl.List(pl.Utf8)).alias("sentence"),
    ).explode("sentence")

    vectorizer = TfidfVectorizer(tokenizer=stemmed_tokens, token_pattern=None, lowercase=False,
                                 ngram_range=(1, 2), sublinear_tf=True)
    vectorizer.fit(pl.concat([sentences["sentence"], profile_texts["text"], phrases["phrases"]]).to_list())
    phrase_vecs = vectorizer.transform(phrases["phrases"].to_list())

    n = len(terms)
    sentence_sim = cosine_similarity(phrase_vecs, vectorizer.transform(sentences["sentence"].to_list()))
    course_sim = np.zeros((n, len(courses)))
    np.maximum.at(course_sim, (phrase_term[:, None], sentences["course_index"].to_numpy()[None, :]), sentence_sim)
    profile_sim = phrase_max_similarity(phrase_vecs, phrase_term, n, vectorizer.transform(profile_texts["text"].to_list()))
    tech_index = np.where(terms["term_source"].to_numpy() == "onet_hot_technology")[0]
    term_tech_sim = phrase_max_similarity(phrase_vecs, phrase_term, n, vectorizer.transform(terms["term"].to_numpy()[tech_index].tolist()))
    profile_codes = profile_texts["onet_soc_code"].to_numpy()

    results = []
    for major in ["ALL", *sorted(alumni["major"].unique())]:
        population = alumni if major == "ALL" else alumni.filter(pl.col("major") == major)
        result = score(
            terms, course_sim, courses, population, weights.filter(pl.col("major") == major),
            tech_postings, national, profile_sim, profile_codes, term_tech_sim,
        )
        results.append(result.with_columns(major=pl.lit(major)))

    by_major = pl.concat(results)
    overall = by_major.filter(pl.col("major") == "ALL").drop("major").sort("alignment_gap", descending=True)
    overall.write_csv(OUT / "gap_matrix.csv")
    by_major.filter(pl.col("major") != "ALL").sort("major", "alignment_gap", descending=[False, True]).write_csv(
        OUT / "gap_matrix_by_major.csv"
    )

    # Top 15 per quadrant: largest gaps first for gaps, strongest scores first otherwise.
    order = {"High Alignment": "demand_score", "Market Gap": "alignment_gap", "Over-Supply": "alignment_gap", "Low Priority": "demand_score"}
    descending = {"High Alignment": True, "Market Gap": True, "Over-Supply": False, "Low Priority": True}
    summary = pl.concat([
        overall.filter(pl.col("quadrant") == q).sort(col, descending=descending[q]).head(15)
        for q, col in order.items()
    ]).select("quadrant", "term", "term_source", "demand_score", "supply_score", "alignment_gap",
              "target_posting_share", "task_relevance", "national_job_postings", "best_matching_course", "catalog_similarity")
    summary.write_csv(OUT / "quadrant_summary.csv")

    print(overall["quadrant"].value_counts().sort("count", descending=True))
    with pl.Config(tbl_rows=60, fmt_str_lengths=40, tbl_width_chars=200):
        print(summary.select("quadrant", "term", "demand_score", "supply_score", "target_posting_share", "task_relevance"))


if __name__ == "__main__":
    main()
