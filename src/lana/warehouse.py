"""Gold warehouse — normalised flat files (CSV + Parquet) for DB loading.

One `dim_geography` + one tidy fact per domain, keyed `(sa2_code, census_year, …)`.
PHN/SA3/SA4/LGA are reachable by joining `dim_geography` on `sa2_code`.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from lana.abs_client import ABSClient
from lana.attribution import attribution_text
from lana.config import Settings
from lana.extract import extract_bronze
from lana.facts import build_fact
from lana.geography import all_qld_sa2_codes, dim_geography, phn_bridge
from lana.indicators import health_asr
from lana.normalise import normalise
from lana.registry import REGISTRY

_SEIFA_INDEX = {"IRSD": "irsd", "IRSAD": "irsad", "IER": "ier", "IEO": "ieo"}
_SEIFA_MEASURE = {"SCORE": "score", "RWAD": "decile_australia", "RWSD": "decile_state", "URP": "population"}


# -- bespoke-shape facts ---------------------------------------------------
def build_population(g01: pl.DataFrame) -> pl.DataFrame:
    """Age structure by sex from G01 (2021). Proportion within (sa2, sex)."""
    age = (
        g01.filter(pl.col("pchar_label").str.starts_with("Age groups: "))
        .filter(pl.col("pchar_label") != "Age groups: Total")
        .with_columns(
            pl.col("pchar_label").str.replace("^Age groups: ", "").alias("age_group"),
            pl.col("sexp_label").alias("sex"),
        )
        .group_by("sa2_code", "year", "sex", "age_group")
        .agg(pl.col("persons").sum().round(0).cast(pl.Int64).alias("count"))
    )
    den = age.group_by("sa2_code", "year", "sex").agg(pl.col("count").sum().alias("denominator"))
    return (
        age.join(den, on=["sa2_code", "year", "sex"])
        .with_columns(
            pl.when(pl.col("denominator") > 0)
            .then((pl.col("count") / pl.col("denominator") * 100).round(2))
            .otherwise(None)
            .alias("proportion")
        )
        .rename({"year": "census_year"})
        .select("sa2_code", "census_year", "sex", "age_group", "count", "denominator", "proportion")
        .sort("sa2_code", "census_year", "sex", "age_group")
    )


def build_seifa(seifa: pl.DataFrame) -> pl.DataFrame:
    """Long SEIFA: one row per (sa2, index, measure) with a tidy value."""
    return (
        seifa.filter(
            pl.col("seifaindextype").is_in(list(_SEIFA_INDEX))
            & pl.col("seifa_measure").is_in(list(_SEIFA_MEASURE))
        )
        .with_columns(
            pl.col("seifaindextype").replace(_SEIFA_INDEX).alias("index"),
            pl.col("seifa_measure").replace(_SEIFA_MEASURE).alias("measure"),
            pl.col("year").alias("census_year"),
        )
        .select("sa2_code", "census_year", "index", "measure", "value")
        .sort("sa2_code", "index", "measure")
    )


def build_medians(g02: pl.DataFrame) -> pl.DataFrame:
    return (
        g02.select(
            "sa2_code",
            pl.col("year").alias("census_year"),
            pl.col("medavg_label").alias("measure"),
            "value",
        ).sort("sa2_code", "measure")
    )


def build_health(g19: pl.DataFrame, settings: Settings) -> pl.DataFrame:
    """Age-standardised + crude prevalence per condition (2021), via the Phase-1 engine."""
    asr = health_asr(g19, level="sa2", settings=settings)
    return asr.with_columns(pl.lit(2021).cast(pl.Int32).alias("census_year")).select(
        "sa2_code", "census_year", "condition", "asr", "crude", "denominator"
    )


# -- writers ---------------------------------------------------------------
def write_table(df: pl.DataFrame, name: str, settings: Settings) -> None:
    for fmt in settings.file_formats:
        path = settings.warehouse_dir / f"{name}.{fmt}"
        if fmt == "csv":
            df.write_csv(path)
        elif fmt == "parquet":
            df.write_parquet(path)
    print(f"  wrote {name} ({df.height} rows)")


def _schema_md(tables: dict[str, pl.DataFrame]) -> str:
    lines = [
        "# LANA gold warehouse — schema",
        "",
        "Normalised flat files (CSV + Parquet). Join every `fact_*` to `dim_geography`",
        "on `sa2_code` to reach SA3/SA4/LGA. Grain: `(sa2_code, census_year, …)`.",
        "",
        "## PHN joins",
        "PHN is **many-to-many**: a few SA2s straddle two PHN boundaries. Join `fact_*` →",
        "`bridge_sa2_phn` (sa2_code → phn_name) for correct PHN analysis. `dim_geography.phn_name`",
        "is only the *primary* (deduped) assignment, kept for convenience — using it will under-",
        "count the straddling SA2s.",
        "",
        "## Caveats",
        "- Time-series facts (country_of_birth, language, education_institution, labour_force,",
        "  family/household_composition, tenure) span **2011/2016/2021 on ASGS-2021 boundaries**",
        "  via ABS Time Series tables. Other facts are **2021 only**.",
        "- `fact_health_conditions` is 2021 only (long-term health condition was new in 2021);",
        "  `asr` = direct age-standardised rate per 100,000 (ASP-2001).",
        "- `fact_language` includes `Uses English only` as a category (table sums to 100%);",
        "  filter it out for the non-English-at-home view the needs assessment usually wants.",
        "- `fact_income_medians` and `fact_seifa` are value-only (no proportion).",
        "- Proportions on tiny denominators are noisy; `denominator` is carried; zero -> null.",
        "- SEIFA is 2021 only (2016 SEIFA uses 2016 boundaries — excluded to keep one geography).",
        "",
        "## Source & attribution",
        "See `ATTRIBUTION.txt` (shipped alongside these files) and the repo `ATTRIBUTION.md`.",
        "",
        "```",
        attribution_text().rstrip(),
        "```",
        "",
        "## Tables",
    ]
    for name in sorted(tables):
        df = tables[name]
        years = sorted(df["census_year"].unique().to_list()) if "census_year" in df.columns else []
        lines.append(f"\n### {name}  ({df.height} rows, years: {years})")
        lines.append("| column | dtype |")
        lines.append("|---|---|")
        for col, dt in df.schema.items():
            lines.append(f"| {col} | {dt} |")
    return "\n".join(lines) + "\n"


# -- orchestrator ----------------------------------------------------------
def build_warehouse(settings: Settings | None = None, refresh: bool = False) -> dict[str, pl.DataFrame]:
    s = settings or Settings()
    s.ensure_dirs()
    client = ABSClient(s)
    sa2 = all_qld_sa2_codes(s)
    print(f"Building warehouse for {len(sa2)} QLD SA2s")

    def _norm(flow: str, *, timeseries: bool = False, measure: str = "value") -> pl.DataFrame:
        sp, ep = (s.census_period_start, s.census_period_end) if timeseries else (s.census_year, s.census_year)
        bronze = extract_bronze(
            flow, sa2, cache_tag="qld", start_period=sp, end_period=ep,
            client=client, settings=s, refresh=refresh,
        )
        return normalise(bronze, measure=measure)

    tables: dict[str, pl.DataFrame] = {
        "dim_geography": dim_geography(s),
        "bridge_sa2_phn": phn_bridge(s),
    }

    print("fact_population ...")
    tables["fact_population"] = build_population(_norm("C21_G01_SA2", measure="persons"))

    for spec in REGISTRY:
        print(f"fact_{spec.name} ...")
        tables[f"fact_{spec.name}"] = build_fact(_norm(spec.dataflow, timeseries=spec.timeseries), spec)

    print("fact_health_conditions ...")
    tables["fact_health_conditions"] = build_health(_norm("C21_G19_SA2", measure="persons"), s)
    print("fact_seifa ...")
    tables["fact_seifa"] = build_seifa(_norm("ABS_SEIFA2021_SA2"))
    print("fact_income_medians ...")
    tables["fact_income_medians"] = build_medians(_norm("C21_G02_SA2"))

    for name, df in tables.items():
        write_table(df, name, s)
    (s.warehouse_dir / "schema.md").write_text(_schema_md(tables), encoding="utf-8")
    (s.warehouse_dir / "ATTRIBUTION.txt").write_text(attribution_text(), encoding="utf-8")
    print(f"Warehouse written to {s.warehouse_dir}")
    return tables
