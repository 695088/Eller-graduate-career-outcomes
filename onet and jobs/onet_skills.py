"""Build the O*NET occupations table from the Eller course skills dictionary.

Each skill in course_skills.csv is searched in O*NET; the top matches are
kept, then enriched with job zone, career cluster, and national median pay.

Outputs (next to this script):
  onet_occupations.csv         one row per occupation (the requested table)
  skill_occupation_bridge.csv  which skill surfaced which occupation, by rank
"""
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import polars as pl
import requests

API_KEY = os.environ.get("ONET_API_KEY", "FN345-dVeev-UlNVP-i5Uc2")
BASE_URL = "https://api-v2.onetcenter.org"
TOP_N_PER_SKILL = 5

# O*NET keyword search matches individual words ("product launch" -> Aircraft
# Launch Officers, "excel" -> Automotive Technicians). Only occupations in SOC
# groups a business graduate plausibly enters are kept. Set to None to disable.
ELLER_RELEVANT_SOC_GROUPS = (
    "11",    # Management
    "13",    # Business and Financial Operations
    "15",    # Computer and Mathematical
    "17-2",  # Engineers (industrial, systems)
    "19-3",  # Social Scientists (economists, survey researchers)
    "23",    # Legal
    "27-3",  # Media and Communication
    "41",    # Sales
    "43",    # Office and Administrative Support
)

HERE = Path(__file__).resolve().parent
SKILLS_CSV = HERE.parent / "data" / "skills from courses" / "course_skills.csv"
CACHE_DIR = HERE / "cache"

# O*NET lists many occupations under several clusters. When one of them matches
# the occupation's SOC major group, that one is used as the primary cluster.
SOC_GROUP_CLUSTER = {
    "11": "Management & Entrepreneurship",
    "13-1": "Management & Entrepreneurship",
    "13-2": "Financial Services",
    "15": "Digital Technology",
    "17": "Advanced Manufacturing",
    "21": "Healthcare & Human Services",
    "23": "Public Service & Safety",
    "25": "Education",
    "27": "Arts, Entertainment, & Design",
    "29": "Healthcare & Human Services",
    "31": "Healthcare & Human Services",
    "33": "Public Service & Safety",
    "35": "Hospitality, Events, & Tourism",
    "41": "Marketing & Sales",
    "45": "Agriculture",
    "47": "Construction",
    "51": "Advanced Manufacturing",
    "53": "Supply Chain & Transportation",
}

session = requests.Session()
session.headers.update({"X-API-Key": API_KEY, "Accept": "application/json"})


def get(path: str, **params):
    """GET with an on-disk cache and retry on rate limiting / transient errors."""
    key = json.dumps([path.strip("/"), sorted(params.items())])
    cache_file = CACHE_DIR / f"{hashlib.sha1(key.encode()).hexdigest()}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    for attempt in range(5):
        response = session.get(f"{BASE_URL}/{path.lstrip('/')}", params=params, timeout=30)
        # 404/422: no data for this occupation (e.g. "All Other" catch-all codes)
        if response.status_code in (404, 422):
            data = None
            break
        if response.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        response.raise_for_status()
        data = response.json()
        break
    else:
        response.raise_for_status()

    cache_file.write_text(json.dumps(data))
    return data


def search_occupations(keyword: str, limit: int = TOP_N_PER_SKILL):
    """Top keyword-search matches, excluding O*NET's unranked filler.

    After the relevance-ranked hits, O*NET lists every other occupation that
    mentions the term in ascending code order (e.g. "SQL" returns 2 ranked hits,
    then Chief Executives, Legislators, ...). That trailing ascending run is cut.
    """
    occupations = (get("online/search", keyword=keyword, end=30) or {}).get("occupation", [])
    codes = [occ["code"] for occ in occupations]
    cutoff = len(codes) - 1
    while cutoff > 0 and codes[cutoff - 1] < codes[cutoff]:
        cutoff -= 1
    return [occ for occ in occupations[:cutoff] if is_relevant(occ["code"])][:limit]


def get_hot_technology_occupations(title: str, limit: int = TOP_N_PER_SKILL):
    """Occupations whose job postings most often mention a technology."""
    data = get(f"online/hot_technology/{title}", end=200) or {}
    ranked = sorted(data.get("occupation", []), key=lambda occ: -occ.get("percentage", 0))
    return [occ for occ in ranked if is_relevant(occ["code"])][:limit]


def is_relevant(onet_soc_code: str):
    return ELLER_RELEVANT_SOC_GROUPS is None or onet_soc_code.startswith(ELLER_RELEVANT_SOC_GROUPS)


def find_occupations(terms: list[str], hot_tech_titles: dict, limit: int = TOP_N_PER_SKILL):
    """Rank occupations by agreement across a skill's name and synonyms.

    Each term is searched separately; an occupation earns 1/rank per term that
    surfaces it. Single-word coincidences (e.g. "launch" -> Artillery Crew) tend
    to appear for one phrasing only, so they fall below consistent matches.
    """
    scores, hits, titles = {}, {}, {}
    for term in dict.fromkeys(terms):
        ranked = search_occupations(term)
        if term in hot_tech_titles:
            ranked = ranked + get_hot_technology_occupations(hot_tech_titles[term])
        for rank, occ in enumerate(ranked, start=1):
            code = occ["code"]
            scores[code] = scores.get(code, 0) + 1 / rank
            hits[code] = hits.get(code, 0) + 1
            titles[code] = occ["title"]
    best = sorted(scores, key=lambda c: (-scores[c], c))[:limit]
    return [{"code": c, "title": titles[c], "match_score": round(scores[c], 3), "terms_matched": hits[c]} for c in best]


def get_job_zone(onet_soc_code: str):
    data = get(f"online/occupations/{onet_soc_code}/summary/job_zone")
    return data.get("code") if data else None


def get_median_pay(onet_soc_code: str):
    data = get(f"mnm/careers/{onet_soc_code}/job_outlook")
    salary = (data or {}).get("salary") or {}
    median = salary.get("annual_median")
    return float(median) if median is not None else None


def get_career_cluster_map():
    """Map onet_soc_code -> list of career cluster titles, in O*NET listing order."""
    clusters = get("online/career_clusters")
    cluster_map = {}
    for cluster in clusters:
        if cluster["title"] == "All Career Clusters":
            continue
        start = 1
        while True:
            page = get(f"online/career_clusters/{cluster['code']}", start=start, end=start + 999)
            for occ in page.get("occupation", []):
                cluster_map.setdefault(occ["code"], []).append(cluster["title"])
            if page["end"] >= page["total"]:
                break
            start = page["end"] + 1
    return cluster_map


def primary_cluster(onet_soc_code: str, clusters: list[str]):
    if not clusters:
        return None
    preferred = SOC_GROUP_CLUSTER.get(onet_soc_code[:4]) or SOC_GROUP_CLUSTER.get(onet_soc_code[:2])
    return preferred if preferred in clusters else clusters[0]


def main():
    CACHE_DIR.mkdir(exist_ok=True)
    skills = pl.read_csv(SKILLS_CSV)

    # 1. Skill -> occupation matches
    hot_tech_titles = {t["title"].lower(): t["title"] for t in get("online/hot_technology/", end=2000)}
    terms = [
        [name.lower(), *json.loads(synonyms)]
        for name, synonyms in zip(skills["skill_name"], skills["search_synonyms"])
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda t: find_occupations(t, hot_tech_titles), terms))

    bridge_rows, titles, unmatched = [], {}, []
    for skill_id, skill_name, matches in zip(skills["skill_id"], skills["skill_name"], results):
        if not matches:
            unmatched.append(skill_name)
        for rank, occ in enumerate(matches, start=1):
            bridge_rows.append({
                "skill_id": skill_id,
                "skill_name": skill_name,
                "onet_soc_code": occ["code"],
                "match_rank": rank,
                "match_score": occ["match_score"],
                "terms_matched": occ["terms_matched"],
            })
            titles[occ["code"]] = occ["title"]
    bridge = pl.DataFrame(bridge_rows)
    codes = sorted(titles)
    print(f"{len(skills)} skills -> {len(codes)} unique occupations")
    print(f"{len(unmatched)} skills had no ranked O*NET match: {unmatched}")

    # 2. Enrich each occupation
    cluster_map = get_career_cluster_map()
    with ThreadPoolExecutor(max_workers=8) as pool:
        job_zones = list(pool.map(get_job_zone, codes))
        median_pays = list(pool.map(get_median_pay, codes))

    occupations = pl.DataFrame({
        "onet_soc_code": codes,
        "soc_title": [titles[c] for c in codes],
        "job_zone": job_zones,
        "career_cluster": [primary_cluster(c, cluster_map.get(c, [])) for c in codes],
        "national_median_pay": median_pays,
    }, schema={
        "onet_soc_code": pl.Utf8,
        "soc_title": pl.Utf8,
        "job_zone": pl.Int64,
        "career_cluster": pl.Utf8,
        "national_median_pay": pl.Float64,
    })

    occupations.write_csv(HERE / "onet_occupations.csv")
    bridge.write_csv(HERE / "skill_occupation_bridge.csv")

    print(occupations.head(10))
    print(occupations.null_count())


if __name__ == "__main__":
    main()
