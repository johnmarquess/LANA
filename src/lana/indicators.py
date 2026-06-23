"""L3/L4 Gold — assemble conformed indicator tables from the silver facts.

Inputs are normalised (silver) frames for G01 (person characteristics), G19
(long-term health conditions) and SEIFA. Output is a dict of analysis-ready
Polars frames, one per workbook sheet, all joined to the geography spine.
"""

from __future__ import annotations

import polars as pl

from lana.config import Settings
from lana.constants import SEIFA_INDEXES
from lana.geography import geo_spine, phn_bridge
from lana.standardise import age_standardised_rate

PERSONS = "3"  # sexp code for 'Persons'
G19_DENOM = "Total (Persons)"
G19_NON_CONDITIONS = {G19_DENOM, "No long-term health condition(s)", "Not stated"}
AGE_TOTAL = "Total"


# --------------------------------------------------------------------------
# Demographic + socio-economic (G01)
# --------------------------------------------------------------------------
def demographic_sa2(g01: pl.DataFrame) -> pl.DataFrame:
    """Per-SA2 totals: population, Indigenous %, other-language %, Year-12 %."""
    persons = g01.filter(pl.col("sexp") == PERSONS)

    age = (
        persons.filter(pl.col("pchar_label").str.starts_with("Age groups: "))
        .filter(pl.col("pchar_label") != "Age groups: Total")
        .group_by("sa2_code")
        .agg(pl.col("persons").sum().alias("total_pop"))
    )

    def _count(label: str, name: str) -> pl.DataFrame:
        return (
            persons.filter(pl.col("pchar_label") == label)
            .group_by("sa2_code")
            .agg(pl.col("persons").sum().alias(name))
        )

    indig = _count("Aboriginal and/or Torres Strait Islander persons: Total", "indigenous")
    other_lang = _count("Language used at home: Other language", "other_language")
    year12 = _count("Highest year of school completed: Year 12 or equivalent", "year12")

    out = age
    for frame in (indig, other_lang, year12):
        out = out.join(frame, on="sa2_code", how="left")

    def _pct(col: str) -> pl.Expr:
        # zero-population SA2s -> null (blank), never NaN
        return (
            pl.when(pl.col("total_pop") > 0)
            .then((pl.col(col) / pl.col("total_pop") * 100).round(1))
            .otherwise(None)
            .alias(f"{col}_pct")
        )

    return (
        out.fill_null(0)
        .with_columns(_pct("indigenous"), _pct("other_language"), _pct("year12"))
        .sort("sa2_code")
    )


# --------------------------------------------------------------------------
# SEIFA (socio-economic indexes)
# --------------------------------------------------------------------------
def seifa_sa2(seifa: pl.DataFrame) -> pl.DataFrame:
    """Per-SA2 SEIFA: score + national decile (RWAD) for each of the four indexes."""
    keep = seifa.filter(
        pl.col("seifaindextype").is_in(list(SEIFA_INDEXES))
        & pl.col("seifa_measure").is_in(["SCORE", "RWAD", "URP"])
    ).with_columns(
        pl.col("seifaindextype").replace(SEIFA_INDEXES).alias("idx"),
    )

    # URP (population) is index-invariant — take it once.
    urp = (
        keep.filter(pl.col("seifa_measure") == "URP")
        .group_by("sa2_code")
        .agg(pl.col("value").first().alias("urp"))
    )

    metric = keep.filter(pl.col("seifa_measure").is_in(["SCORE", "RWAD"])).with_columns(
        (
            pl.col("idx")
            + pl.when(pl.col("seifa_measure") == "SCORE")
            .then(pl.lit("_score"))
            .otherwise(pl.lit("_decile"))
        ).alias("col")
    )
    wide = metric.pivot(values="value", index="sa2_code", on="col", aggregate_function="first")
    return wide.join(urp, on="sa2_code", how="left").sort("sa2_code")


def seifa_phn_summary(
    seifa_sa2_df: pl.DataFrame,
    *,
    phn: str | None = None,
    settings: Settings | None = None,
) -> pl.DataFrame:
    """PHN-level SEIFA: deciles can't be averaged, so summarise the SA2 distribution.

    `irsd_decile_median` is the **unweighted** median of the SA2 IRSD deciles within
    the PHN. `pop_pct_in_bottom2_deciles` is the URP-weighted share of the PHN
    population residing in the two most-disadvantaged deciles.

    If `phn` is given, only that PHN's members (via the bridge) are aggregated and a
    single row is returned. Without `phn`, all PHNs are returned (useful for the
    warehouse path where no single target PHN exists).
    """
    bridge = phn_bridge(settings).select("sa2_code", "phn_name")
    df = seifa_sa2_df.join(bridge, on="sa2_code", how="left")
    if phn is not None:
        df = df.filter(pl.col("phn_name") == phn)
    return (
        df.group_by("phn_name")
        .agg(
            pl.col("irsd_decile").min().alias("irsd_decile_min"),
            pl.col("irsd_decile").median().alias("irsd_decile_median"),  # ponytail: unweighted median; switch to a population-weighted median if PHN disadvantage summaries need it
            pl.col("irsd_decile").max().alias("irsd_decile_max"),
            pl.when(pl.col("urp").sum() > 0)
            .then(
                (
                    (pl.col("urp") * (pl.col("irsd_decile") <= 2)).sum() / pl.col("urp").sum() * 100
                ).round(1)
            )
            .otherwise(None)
            .alias("pop_pct_in_bottom2_deciles"),
            pl.col("sa2_code").n_unique().alias("n_sa2"),
        )
        .sort("phn_name")
    )


# --------------------------------------------------------------------------
# Health conditions — crude + age-standardised prevalence (G19)
# --------------------------------------------------------------------------
def _health_num_den(g19: pl.DataFrame) -> pl.DataFrame:
    """Long frame at (sa2_code, condition, agep_label) with numerator + denominator."""
    persons = g19.filter((pl.col("sexp") == PERSONS) & (pl.col("agep_label") != AGE_TOTAL))
    den = (
        persons.filter(pl.col("lthp_label") == G19_DENOM)
        .group_by("sa2_code", "agep_label")
        .agg(pl.col("persons").sum().alias("den"))
    )
    num = (
        persons.filter(~pl.col("lthp_label").is_in(list(G19_NON_CONDITIONS)))
        .group_by("sa2_code", "agep_label", "lthp_label")
        .agg(pl.col("persons").sum().alias("num"))
        .rename({"lthp_label": "condition"})
    )
    return num.join(den, on=["sa2_code", "agep_label"], how="inner")


def health_asr(
    g19: pl.DataFrame,
    *,
    level: str,
    phn: str | None = None,
    settings: Settings | None = None,
) -> pl.DataFrame:
    """Age-standardised + crude prevalence per 100,000 by condition at `level`.

    level: 'sa2' or 'phn'. Counts are aggregated to the level BEFORE standardising.

    When level == 'phn', the join uses the authoritative many-to-many bridge so
    straddling SA2s are included in both their PHNs. If `phn` is given, only that
    PHN's rows are kept after the join (prevents straddling SA2s from emitting a
    phantom row for the other PHN in a single-PHN workbook).
    """
    base = _health_num_den(g19)
    if level == "phn":
        bridge = phn_bridge(settings).select("sa2_code", "phn_name")
        joined = base.join(bridge, on="sa2_code", how="left")
        if phn is not None:
            joined = joined.filter(pl.col("phn_name") == phn)
        base = joined.group_by("phn_name", "condition", "agep_label").agg(
            pl.col("num").sum(), pl.col("den").sum()
        )
        keys = ["phn_name", "condition"]
    else:
        keys = ["sa2_code", "condition"]

    return age_standardised_rate(
        base,
        group_keys=keys,
        age_label_col="agep_label",
        num_col="num",
        den_col="den",
        settings=settings,
    ).sort([keys[0], pl.col("asr")], descending=[False, True])


# --------------------------------------------------------------------------
# Equity — health gradient across SEIFA disadvantage (SA2)
# --------------------------------------------------------------------------
def equity_sa2(
    health_asr_sa2: pl.DataFrame, seifa_sa2_df: pl.DataFrame, demo: pl.DataFrame
) -> tuple[str, pl.DataFrame]:
    """For the most-prevalent condition, join each SA2's ASR to its IRSD decile."""
    default = (
        health_asr_sa2.group_by("condition")
        .agg(pl.col("denominator").sum().alias("d"), pl.col("asr").mean().alias("m"))
        .sort("m", descending=True)
        .head(1)["condition"][0]
    )
    sel = health_asr_sa2.filter(pl.col("condition") == default).select("sa2_code", "asr")
    out = (
        seifa_sa2_df.select("sa2_code", "irsd_score", "irsd_decile")
        .join(sel, on="sa2_code", how="inner")
        .join(demo.select("sa2_code", "total_pop"), on="sa2_code", how="left")
        .sort("irsd_decile")
    )
    return default, out


# --------------------------------------------------------------------------
# Orchestrate the gold layer
# --------------------------------------------------------------------------
def build_gold(
    g01: pl.DataFrame,
    g19: pl.DataFrame,
    seifa: pl.DataFrame,
    *,
    phn: str,
    settings: Settings | None = None,
) -> dict[str, pl.DataFrame]:
    """Build the gold layer for a single target PHN.

    `phn` must be the authoritative PHN name from the crosswalk. All PHN-level
    aggregations use the many-to-many bridge so straddling SA2s are included in
    both their PHNs' workbooks and never produce phantom rows for other PHNs.
    """
    s = settings or Settings()
    spine = geo_spine(s)
    bridge = phn_bridge(s)
    phn_sa2s = bridge.filter(pl.col("phn_name") == phn)["sa2_code"].to_list()

    demo = demographic_sa2(g01).join(
        spine.select("sa2_code", "sa2_name", "sa3_name", "lga_name", "phn_name"),
        on="sa2_code",
        how="left",
    )
    seif = seifa_sa2(seifa)
    h_sa2 = health_asr(g19, level="sa2", settings=s)
    h_phn = health_asr(g19, level="phn", phn=phn, settings=s)
    default_condition, equity = equity_sa2(h_sa2, seif, demo)

    return {
        "geography": spine.filter(pl.col("sa2_code").is_in(phn_sa2s)),
        "demographic": demo,
        "socioeconomic": seif.join(
            spine.select("sa2_code", "sa2_name", "phn_name"), on="sa2_code", how="left"
        ),
        "seifa_phn": seifa_phn_summary(seif, phn=phn, settings=s),
        "health_sa2": h_sa2,
        "health_phn": h_phn,
        "equity": equity,
        "_meta": pl.DataFrame({"key": ["default_condition"], "value": [default_condition]}),
    }
