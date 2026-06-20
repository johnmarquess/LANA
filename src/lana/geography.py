"""L3 — the conformed geography spine: SA2 -> SA3 -> SA4 -> LGA -> PHN.

The single crosswalk every source joins to. SA2 is the atomic grain; everything
coarser is an aggregation. Built from the two legacy crosswalk CSVs (ASGS 2021
SA2s, PHN 2023 boundaries).
"""

from __future__ import annotations

import polars as pl

from lana.config import Settings

_spine_cache: dict[str, pl.DataFrame] = {}

_CORR_RENAME = {
    "SA2_CODE_2021": "sa2_code", "SA2_NAME_2021": "sa2_name",
    "SA3_CODE_2021": "sa3_code", "SA3_NAME_2021": "sa3_name",
    "SA4_CODE_2021": "sa4_code", "SA4_NAME_2021": "sa4_name",
    "LGA_CODE_2021": "lga_code", "LGA_NAME_2021": "lga_name",
}


def derive_parents(sa2_code: str) -> tuple[str, str]:
    """SA3 (first 5 digits) and SA4 (first 3 digits) from a 9-digit SA2 code."""
    return sa2_code[:5], sa2_code[:3]


def geo_spine(settings: Settings | None = None) -> pl.DataFrame:
    """SA2-grain spine with SA3/SA4/LGA/PHN attached. Codes kept as strings."""
    s = settings or Settings()
    key = str(s.reference_dir)
    if key in _spine_cache:
        return _spine_cache[key]
    corr = pl.read_csv(s.reference_dir / "geo_correspondence_2021.csv", infer_schema=False)
    corr = corr.rename({k: v for k, v in _CORR_RENAME.items() if k in corr.columns})

    phn = pl.read_csv(s.reference_dir / "phn_2023_to_SA2_2021.csv", infer_schema=False)
    phn = phn.select(
        pl.col("SA2_CODE_2021").alias("sa2_code"),
        pl.col("PHN_NAME_2023").alias("phn_name"),
    ).unique(subset="sa2_code")

    spine = corr.join(phn, on="sa2_code", how="left").unique(subset="sa2_code").sort("sa2_code")
    _spine_cache[key] = spine
    return spine


def all_qld_sa2_codes(settings: Settings | None = None) -> list[str]:
    """Every SA2 in the QLD PHN crosswalk (across the 7 QLD PHNs)."""
    return geo_spine(settings).filter(pl.col("phn_name").is_not_null())["sa2_code"].to_list()


def phn_bridge(settings: Settings | None = None) -> pl.DataFrame:
    """Authoritative many-to-many SA2↔PHN mapping (every row of the crosswalk).

    A handful of SA2s straddle two PHN boundaries and so appear under both. Use
    this bridge for correct PHN analysis; `dim_geography.phn_name` is only the
    primary (deduped) assignment.
    """
    s = settings or Settings()
    phn = pl.read_csv(s.reference_dir / "phn_2023_to_SA2_2021.csv", infer_schema=False)
    return (
        phn.select(
            pl.col("SA2_CODE_2021").alias("sa2_code"),
            pl.col("PHN_NAME_2023").alias("phn_name"),
        )
        .unique()
        .sort("sa2_code", "phn_name")
    )


def dim_geography(settings: Settings | None = None) -> pl.DataFrame:
    """The geography dimension table for the warehouse (one row per SA2)."""
    return geo_spine(settings).select(
        "sa2_code", "sa2_name", "sa3_code", "sa3_name",
        "sa4_code", "sa4_name", "lga_code", "lga_name", "phn_name",
    )


def target_sa2_codes(phn_name: str, settings: Settings | None = None) -> list[str]:
    """SA2 codes belonging to a PHN. Raises if the PHN name is unknown."""
    spine = geo_spine(settings)
    codes = spine.filter(pl.col("phn_name") == phn_name)["sa2_code"].to_list()
    if not codes:
        known = sorted(spine["phn_name"].drop_nulls().unique().to_list())
        raise ValueError(f"Unknown PHN '{phn_name}'. Known: {known}")
    return codes


def rollup(
    fact: pl.DataFrame,
    *,
    level: str,
    group_dims: list[str],
    value_col: str = "value",
    settings: Settings | None = None,
) -> pl.DataFrame:
    """Aggregate an SA2-grain fact up to `level` ('phn'|'lga'|'sa3'|'sa4').

    `fact` must have an `sa2_code` column. `group_dims` are extra dimensions to
    keep (e.g. sex, age_group). Values are summed.
    """
    level_cols = {
        "phn": ["phn_name"],
        "lga": ["lga_code", "lga_name"],
        "sa3": ["sa3_code", "sa3_name"],
        "sa4": ["sa4_code", "sa4_name"],
        "sa2": ["sa2_code", "sa2_name"],
    }[level]
    spine = geo_spine(settings).select(["sa2_code", *level_cols])
    joined = fact.join(spine, on="sa2_code", how="left")
    return (
        joined.group_by([*level_cols, *group_dims])
        .agg(pl.col(value_col).sum())
        .sort([*level_cols, *group_dims])
    )
