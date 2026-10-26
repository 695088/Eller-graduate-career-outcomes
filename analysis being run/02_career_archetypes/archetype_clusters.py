"""Career archetype clusters.

Clusters alumni into career archetypes using what they actually do (normalized
job titles, O*NET occupations, industry, and course-derived skills) instead of
their major label. Runs once within each major and once pooled across all
majors, choosing the number of clusters by silhouette score. Each archetype is
then profiled: title progression, industry mix, geographic hubs, salary,
promotion, and job zone movement.
"""
import sys
from pathlib import Path

import numpy as np
import polars as pl
from scipy import sparse
from scipy.stats import chi2_contingency
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import MultiLabelBinarizer, OneHotEncoder, normalize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import data  # noqa: E402

OUT = data.outputs_dir(__file__)

SEED = 42
K_RANGE_MAJOR = range(2, 7)
K_RANGE_POOLED = range(4, 15)
SILHOUETTE_SAMPLE = 3000
SKILL_SVD_COMPONENTS = 15
# Relative influence of each feature block on the clustering distance.
BLOCK_WEIGHTS = {"titles": 1.0, "occupations": 0.75, "industry": 0.75, "skills": 0.5}
HUB_MIN_ALUMNI = 30
HUB_MIN_LQ = 1.2


def feature_matrix(alumni: pl.DataFrame):
    """Weighted, row-normalized feature blocks stacked side by side."""
    titles = (alumni["first_title"] + " " + alumni["yr3_title"]).to_list()
    title_vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    blocks = {
        "titles": title_vec.fit_transform(titles),
        "occupations": OneHotEncoder(handle_unknown="ignore").fit_transform(
            alumni.select("first_onet_soc", "yr3_onet_soc").to_numpy()),
        "industry": OneHotEncoder(handle_unknown="ignore").fit_transform(
            alumni.select("industry_sector").to_numpy()),
    }
    skills = MultiLabelBinarizer(sparse_output=True).fit_transform(alumni["skills_obtained"].to_list())
    n_comp = min(SKILL_SVD_COMPONENTS, skills.shape[1] - 1)
    blocks["skills"] = sparse.csr_matrix(TruncatedSVD(n_comp, random_state=SEED).fit_transform(skills))
    stacked = sparse.hstack([normalize(blocks[name]) * w for name, w in BLOCK_WEIGHTS.items()]).tocsr()
    return stacked, title_vec


def choose_k(X, k_range, group: str):
    rows, best = [], None
    for k in k_range:
        if k >= X.shape[0]:
            break
        km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(X)
        sil = silhouette_score(X, km.labels_, sample_size=min(SILHOUETTE_SAMPLE, X.shape[0]), random_state=SEED)
        rows.append({"group": group, "k": k, "silhouette": round(float(sil), 4), "inertia": round(float(km.inertia_), 2)})
        if best is None or sil > best[0]:
            best = (sil, km)
    return best[1], rows


def label_clusters(alumni: pl.DataFrame, labels: np.ndarray) -> dict:
    """Name each cluster '<most common entry title> -> <most common year-3 title> | <top industry>'."""
    df = alumni.with_columns(cluster=pl.Series(labels))
    names = {}
    for c in sorted(set(labels)):
        sub = df.filter(pl.col("cluster") == c)
        first = sub["first_title"].mode().sort()[0]
        yr3 = sub["yr3_title"].mode().sort()[0]
        industry = sub["industry_sector"].mode().sort()[0]
        names[c] = f"{first} -> {yr3} | {industry}"
    return names


def top_values(series: pl.Series, n: int = 3) -> str:
    counts = series.value_counts().sort("count", descending=True).head(n)
    total = len(series)
    return "; ".join(f"{v} ({c / total:.0%})" for v, c in counts.iter_rows())


def profile(assigned: pl.DataFrame, occupations: pl.DataFrame) -> pl.DataFrame:
    zones = dict(zip(occupations["onet_soc_code"], occupations["job_zone"]))
    titles = dict(zip(occupations["onet_soc_code"], occupations["soc_title"]))
    with_zone = assigned.with_columns(
        first_zone=pl.col("first_onet_soc").replace_strict(zones, default=None, return_dtype=pl.Int64),
        yr3_zone=pl.col("yr3_onet_soc").replace_strict(zones, default=None, return_dtype=pl.Int64),
    )
    group_sizes = with_zone.group_by("group").len("group_n")
    rows = []
    for (group, archetype_id, label), sub in with_zone.group_by("group", "archetype_id", "archetype_label"):
        rows.append({
            "group": group,
            "archetype_id": archetype_id,
            "archetype_label": label,
            "n_alumni": len(sub),
            "major_mix": top_values(sub["major"], 4),
            "top_entry_titles": top_values(sub["first_title"]),
            "top_yr3_titles": top_values(sub["yr3_title"]),
            "top_entry_occupation": top_values(sub["first_onet_soc"].replace_strict(titles, default="Unknown"), 2),
            "top_industries": top_values(sub["industry_sector"]),
            "top_metros": top_values(sub["location_metro"]),
            "internship_rate": round(sub["had_internship"].mean(), 4),
            "median_starting_salary": sub["starting_salary_mid"].median(),
            "mean_starting_salary": round(sub["starting_salary_mid"].mean(), 0),
            "promotion_rate_3yr": round(sub["promoted_within_3yr"].mean(), 4),
            "median_months_to_promo": sub["months_to_promo"].median(),
            "mean_entry_job_zone": round(sub["first_zone"].mean(), 2) if sub["first_zone"].drop_nulls().len() else None,
            "mean_yr3_job_zone": round(sub["yr3_zone"].mean(), 2) if sub["yr3_zone"].drop_nulls().len() else None,
            "mean_job_zone_jump": round((sub["yr3_zone"] - sub["first_zone"]).mean(), 3)
            if (sub["yr3_zone"] - sub["first_zone"]).drop_nulls().len() else None,
        })
    return (pl.DataFrame(rows).join(group_sizes, on="group")
            .with_columns(share_of_group=(pl.col("n_alumni") / pl.col("group_n")).round(4)).drop("group_n")
            .sort("group", "n_alumni", descending=[False, True]))


def main():
    alumni = data.load_alumni()
    occupations = data.load_occupations()

    selection_rows, assignments = [], []
    groups = [(m, alumni.filter(pl.col("major") == m), K_RANGE_MAJOR) for m in sorted(alumni["major"].unique())]
    groups.append(("ALL", alumni, K_RANGE_POOLED))
    for group, sub, k_range in groups:
        X, _ = feature_matrix(sub)
        km, rows = choose_k(X, k_range, group)
        selection_rows.extend(rows)
        names = label_clusters(sub, km.labels_)
        # Number archetypes by size so A1 is always the largest.
        order = {c: i + 1 for i, (c, _) in enumerate(sorted(
            ((c, (km.labels_ == c).sum()) for c in set(km.labels_)), key=lambda t: -t[1]))}
        assignments.append(sub.with_columns(
            group=pl.lit(group),
            archetype_id=pl.Series([f"{group}-A{order[c]}" for c in km.labels_]),
            archetype_label=pl.Series([names[c] for c in km.labels_]),
        ))
        print(f"{group}: k={km.n_clusters} (silhouette {max(r['silhouette'] for r in rows):.3f})")

    assigned = pl.concat(assignments)
    pl.DataFrame(selection_rows).write_csv(OUT / "cluster_selection.csv")
    assigned.select("alumni_id", "major", "group", "archetype_id", "archetype_label").write_csv(OUT / "archetype_assignments.csv")
    profile(assigned, occupations).write_csv(OUT / "archetype_profiles.csv")

    # Title progression within each archetype: P(year-3 title | entry title).
    transitions = (
        assigned.group_by("group", "archetype_id", "first_title", "yr3_title").len("n_alumni")
        .with_columns(p_yr3_given_entry=(pl.col("n_alumni") / pl.col("n_alumni").sum().over("archetype_id", "first_title")).round(4))
        .sort("archetype_id", "n_alumni", descending=[False, True])
    )
    transitions.write_csv(OUT / "archetype_title_transitions.csv")

    industry = (
        assigned.group_by("group", "archetype_id", "industry_sector").len("n_alumni")
        .with_columns(share=(pl.col("n_alumni") / pl.col("n_alumni").sum().over("archetype_id")).round(4))
        .sort("archetype_id", "share", descending=[False, True])
    )
    industry.write_csv(OUT / "archetype_industry_distribution.csv")

    # Geographic hubs: location quotient = archetype's metro share / all alumni metro share.
    overall_share = alumni.group_by("location_metro").len("n").with_columns(base_share=pl.col("n") / len(alumni)).drop("n")
    geo = (
        assigned.group_by("group", "archetype_id", "location_metro").len("n_alumni")
        .with_columns(share=pl.col("n_alumni") / pl.col("n_alumni").sum().over("archetype_id"))
        .join(overall_share, on="location_metro")
        .with_columns(location_quotient=(pl.col("share") / pl.col("base_share")).round(3), share=pl.col("share").round(4))
        .with_columns(is_hub=(pl.col("location_quotient") >= HUB_MIN_LQ) & (pl.col("n_alumni") >= HUB_MIN_ALUMNI))
        .drop("base_share").sort("archetype_id", "location_quotient", descending=[False, True])
    )
    geo.write_csv(OUT / "archetype_geo_hubs.csv")

    # Are metro and industry distributions actually different across archetypes?
    tests = []
    for group, sub in assigned.group_by("group"):
        for column in ("location_metro", "industry_sector"):
            table = sub.pivot(on=column, index="archetype_id", values="alumni_id", aggregate_function="len").fill_null(0)
            chi2, p, dof, _ = chi2_contingency(table.drop("archetype_id").to_numpy())
            n = table.drop("archetype_id").to_numpy().sum()
            cramers_v = np.sqrt(chi2 / (n * (min(table.shape[0], table.shape[1] - 1) - 1))) if min(table.shape[0], table.shape[1] - 1) > 1 else None
            tests.append({"group": group[0], "variable": column, "chi2": round(chi2, 2), "dof": dof,
                          "p_value": p, "cramers_v": round(cramers_v, 4) if cramers_v is not None else None})
    pl.DataFrame(tests).sort("group", "variable").write_csv(OUT / "archetype_independence_tests.csv")


if __name__ == "__main__":
    main()
