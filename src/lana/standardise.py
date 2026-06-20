"""L3 — direct age-standardisation against the 2001 Australian Standard Population.

Direct method (per AIHW/ABS):
  1. age-specific rate  r_g = numerator_g / denominator_g
  2. expected cases     e_g = r_g * std_pop_g
  3. ASR = (Σ e_g / Σ std_pop_g) * per

Standard population is the ABS "Standard Population for use in Age-Standardisation"
(2001 ERP, total = 19,413,240), stored at single year of age in
``data/reference/asp_2001_single_year.csv`` and summed to match the data's own
age groups at runtime — so it works regardless of how a given GCP table bands age.
"""

from __future__ import annotations

import re

import polars as pl

from lana.config import Settings

_asp_cache: dict[str, list[tuple[int, int]]] = {}


def _asp(settings: Settings | None = None) -> list[tuple[int, int]]:
    s = settings or Settings()
    key = str(s.reference_dir)
    if key not in _asp_cache:
        df = pl.read_csv(s.reference_dir / "asp_2001_single_year.csv")
        _asp_cache[key] = list(zip(df["age"].to_list(), df["std_pop"].to_list()))
    return _asp_cache[key]


def parse_age_range(label: str) -> tuple[int, int] | None:
    """('25-34 years') -> (25, 34); ('85 years and over') -> (85, 100).

    Returns None for totals / not-stated / unparseable labels (which must be
    excluded from a direct standardisation).
    """
    if label is None:
        return None
    text = re.sub(r"(?i)^age groups?:\s*", "", str(label)).strip()
    if re.search(r"(?i)total|not stated|^_", text):
        return None
    m = re.search(r"(\d+)\s*[-–]\s*(\d+)", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+)\s*(?:years?\s*)?(?:and|or)\s*over", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), 100
    return None


def _std_pop_for(low: int, high: int, settings: Settings | None = None) -> int:
    return sum(pop for age, pop in _asp(settings) if low <= age <= high)


def std_pop_table(age_labels: list[str], settings: Settings | None = None) -> pl.DataFrame:
    """Map each distinct age label to its summed standard population (totals dropped)."""
    rows = []
    for lbl in dict.fromkeys(age_labels):  # preserve order, dedupe
        rng = parse_age_range(lbl)
        if rng is not None:
            rows.append({"age_label": lbl, "std_pop": _std_pop_for(*rng, settings=settings)})
    return pl.DataFrame(rows, schema={"age_label": pl.Utf8, "std_pop": pl.Int64})


def age_standardised_rate(
    df: pl.DataFrame,
    *,
    group_keys: list[str],
    age_label_col: str,
    num_col: str,
    den_col: str,
    per: int = 100_000,
    settings: Settings | None = None,
) -> pl.DataFrame:
    """Direct age-standardised rate per `group_keys`.

    `df` is at (group_keys x age) grain with a numerator and denominator column.
    Returns one row per group with `asr` (per `per`) and `crude` for comparison.
    """
    std = std_pop_table(df[age_label_col].to_list(), settings)
    work = (
        df.join(std, left_on=age_label_col, right_on="age_label", how="inner")  # drops totals
        .with_columns(
            pl.when(pl.col(den_col) > 0)
            .then(pl.col(num_col) / pl.col(den_col) * pl.col("std_pop"))
            .otherwise(0.0)
            .alias("_expected")
        )
    )
    return (
        work.group_by(group_keys)
        .agg(
            pl.when(pl.col("std_pop").sum() > 0)
            .then(pl.col("_expected").sum() / pl.col("std_pop").sum() * per)
            .otherwise(None)
            .alias("asr"),
            pl.when(pl.col(den_col).sum() > 0)
            .then(pl.col(num_col).sum() / pl.col(den_col).sum() * per)
            .otherwise(None)
            .alias("crude"),
            pl.col(den_col).sum().alias("denominator"),
        )
        .sort(group_keys)
    )
