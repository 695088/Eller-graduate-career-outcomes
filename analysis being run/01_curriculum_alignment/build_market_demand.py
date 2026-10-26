"""Pull the market-demand side of the gap matrix from O*NET.

Target occupations are the O*NET codes alumni actually hold (first job and
year 3), weighted by how many alumni hold them. For each one this fetches the
share of its job postings mentioning each Hot Technology, its task statements,
and its technology-skill examples. The national Hot Technologies list supplies
total job-posting counts.
"""
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import data  # noqa: E402

get = data.import_onet_get()
OUT = data.outputs_dir(__file__)


def fetch_all(path: str, key: str, page_size: int = 200) -> list:
    """Follow O*NET's start/end paging until every item of `key` is collected."""
    items, start = [], 1
    while True:
        page = get(path, start=start, end=start + page_size - 1) or {}
        items.extend(page.get(key, []))
        if not page or page.get("end", 0) >= page.get("total", 0):
            return items
        start = page["end"] + 1


def target_occupation_weights(alumni: pl.DataFrame) -> pl.DataFrame:
    """Alumni-observation counts per (major, occupation), first job and year 3 pooled."""
    held = pl.concat([
        alumni.select("major", onet_soc_code="first_onet_soc"),
        alumni.select("major", onet_soc_code="yr3_onet_soc"),
    ])
    by_major = held.group_by("major", "onet_soc_code").len("n_alumni_obs")
    overall = held.group_by("onet_soc_code").len("n_alumni_obs").with_columns(major=pl.lit("ALL"))
    weights = pl.concat([by_major, overall.select(by_major.columns)])
    return weights.with_columns(
        weight=pl.col("n_alumni_obs") / pl.col("n_alumni_obs").sum().over("major")
    ).sort("major", "weight", descending=[False, True])


def main():
    alumni = data.load_alumni()
    weights = target_occupation_weights(alumni)
    codes = weights["onet_soc_code"].unique().sort().to_list()

    national = pl.DataFrame(
        [{"technology": t["title"], "national_job_postings": t["job_postings"]} for t in get("online/hot_technology/", end=2000)]
    )

    tech_rows, task_rows, example_rows = [], [], []
    for code in codes:
        for ex in fetch_all(f"online/occupations/{code}/hot_technology", "example"):
            tech_rows.append({
                "onet_soc_code": code,
                "technology": ex["title"],
                "posting_pct": float(ex.get("percentage") or 0),
                "in_demand": bool(ex.get("in_demand")),
            })
        for task in fetch_all(f"online/occupations/{code}/details/tasks", "task"):
            task_rows.append({"onet_soc_code": code, "text": task["title"], "source": "task"})
        for category in fetch_all(f"online/occupations/{code}/details/technology_skills", "category"):
            for ex in category.get("example", []):
                example_rows.append({"onet_soc_code": code, "text": ex["title"], "source": "technology_example"})

    weights.write_csv(OUT / "target_occupation_weights.csv")
    national.write_csv(OUT / "market_hot_technologies.csv")
    pl.DataFrame(tech_rows).write_csv(OUT / "occupation_technology_postings.csv")
    pl.DataFrame(task_rows + example_rows).write_csv(OUT / "occupation_profile_texts.csv")
    print(f"{len(codes)} target occupations, {len(national)} hot technologies, "
          f"{len(tech_rows)} occupation-technology rows, {len(task_rows) + len(example_rows)} profile texts")


if __name__ == "__main__":
    main()
