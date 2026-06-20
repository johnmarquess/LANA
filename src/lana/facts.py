"""Generic gold fact builder.

Turns a normalised (silver) frame into a tidy fact keyed
`(sa2_code, census_year, category)` with `count`, `denominator`, `proportion`.

Marginalisation rule: ABS cross-tabs include a Total in every dimension, so to
reduce to one category dimension we *filter* the other dimensions to their
Total/Persons row rather than summing (summing would double-count the totals).
"""

from __future__ import annotations

import polars as pl

from lana.registry import DomainSpec

# columns that are not analysis dimensions
_NON_DIMS = {"region_type", "state"}


def _other_dim_tokens(df: pl.DataFrame, category_dim: str) -> list[str]:
    toks = {c[:-6] for c in df.columns if c.endswith("_label")}
    return [t for t in toks if t != category_dim and t not in _NON_DIMS]


def _marginalise(df: pl.DataFrame, category_dim: str) -> pl.DataFrame:
    """Filter every non-category dimension to its Total (or Persons) row if it has one."""
    work = df
    for tok in _other_dim_tokens(df, category_dim):
        labels = set(work[f"{tok}_label"].unique().to_list())
        total = "Persons" if "Persons" in labels else ("Total" if "Total" in labels else None)
        if total is not None:
            work = work.filter(pl.col(f"{tok}_label") == total)
    return work


def build_fact(df: pl.DataFrame, spec: DomainSpec) -> pl.DataFrame:
    """Build a categorical fact from a normalised frame per `spec`."""
    cat = f"{spec.category_dim}_label"
    work = _marginalise(df, spec.category_dim)

    if spec.include_labels is not None:
        cats = work.filter(pl.col(cat).is_in(list(spec.include_labels)))
    else:
        cats = work.filter(~pl.col(cat).is_in(list(spec.exclude_labels)))

    counts = (
        cats.group_by("sa2_code", "year", cat)
        .agg(pl.col("value").sum().round(0).cast(pl.Int64).alias("count"))
    )

    if spec.denominator_label is not None:
        den = (
            work.filter(pl.col(cat) == spec.denominator_label)
            .group_by("sa2_code", "year")
            .agg(pl.col("value").sum().round(0).cast(pl.Int64).alias("denominator"))
        )
    else:
        den = counts.group_by("sa2_code", "year").agg(pl.col("count").sum().alias("denominator"))

    return (
        counts.join(den, on=["sa2_code", "year"], how="left")
        .with_columns(
            pl.when(pl.col("denominator") > 0)
            .then((pl.col("count") / pl.col("denominator") * 100).round(2))
            .otherwise(None)
            .alias("proportion")
        )
        .rename({"year": "census_year", cat: "category"})
        .select("sa2_code", "census_year", "category", "count", "denominator", "proportion")
        .sort("sa2_code", "census_year", "category")
    )
