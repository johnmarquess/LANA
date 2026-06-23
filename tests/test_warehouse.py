"""Gold warehouse builders: build_population, build_seifa, build_health."""

from __future__ import annotations

import polars as pl

from lana.constants import SEIFA_INDEXES
from lana.warehouse import _SEIFA_MEASURE, build_health, build_population, build_seifa

# ---------------------------------------------------------------------------
# build_population
# ---------------------------------------------------------------------------


def _g01_warehouse_frame() -> pl.DataFrame:
    """Minimal G01 silver at (sa2, year, sexp, pchar) grain."""
    rows = []
    for sex_code, sex_label in [("1", "Males"), ("2", "Females"), ("3", "Persons")]:
        for age_label, count in [
            ("Age groups: 0-4 years", 100),
            ("Age groups: 5-14 years", 200),
            ("Age groups: Total", 300),  # must be excluded
        ]:
            rows.append(
                {
                    "sa2_code": "W1",
                    "year": 2021,
                    "sexp": sex_code,
                    "sexp_label": sex_label,
                    "pchar_label": age_label,
                    "persons": float(count),
                }
            )
    # Second SA2 with zero count to test null proportion
    rows.append(
        {
            "sa2_code": "W2",
            "year": 2021,
            "sexp": "1",
            "sexp_label": "Males",
            "pchar_label": "Age groups: 0-4 years",
            "persons": 0.0,
        }
    )
    rows.append(
        {
            "sa2_code": "W2",
            "year": 2021,
            "sexp": "1",
            "sexp_label": "Males",
            "pchar_label": "Age groups: 5-14 years",
            "persons": 0.0,
        }
    )
    return pl.DataFrame(rows)


def test_build_population_excludes_age_total():
    out = build_population(_g01_warehouse_frame())
    assert "Total" not in out["age_group"].to_list()


def test_build_population_proportions_within_sa2_sex():
    out = build_population(_g01_warehouse_frame())
    # For W1 / Males: 0-4 = 100, 5-14 = 200 → denominator 300
    males_w1 = out.filter((pl.col("sa2_code") == "W1") & (pl.col("sex") == "Males"))
    rows = {r["age_group"]: r for r in males_w1.to_dicts()}
    assert rows["0-4 years"]["proportion"] == round(100 / 300 * 100, 2)
    assert rows["5-14 years"]["proportion"] == round(200 / 300 * 100, 2)
    # Proportions within a (sa2, sex) should sum to 100
    assert abs(males_w1["proportion"].sum() - 100.0) < 1e-6


def test_build_population_zero_denominator_yields_null():
    out = build_population(_g01_warehouse_frame())
    w2 = out.filter(pl.col("sa2_code") == "W2")
    for row in w2.to_dicts():
        assert row["proportion"] is None


def test_build_population_output_columns():
    out = build_population(_g01_warehouse_frame())
    expected = {"sa2_code", "census_year", "sex", "age_group", "count", "denominator", "proportion"}
    assert expected == set(out.columns)


def test_build_population_census_year_renamed():
    out = build_population(_g01_warehouse_frame())
    assert "census_year" in out.columns
    assert "year" not in out.columns


# ---------------------------------------------------------------------------
# build_seifa
# ---------------------------------------------------------------------------


def _seifa_warehouse_frame() -> pl.DataFrame:
    """Minimal SEIFA silver for all four indexes and all measures."""
    rows = []
    for idx in SEIFA_INDEXES:
        for measure in ["SCORE", "RWAD", "RWSD", "URP"]:
            rows.append(
                {
                    "sa2_code": "S1",
                    "year": 2021,
                    "seifaindextype": idx,
                    "seifa_measure": measure,
                    "value": 100.0,
                }
            )
    return pl.DataFrame(rows)


def test_build_seifa_output_columns():
    out = build_seifa(_seifa_warehouse_frame())
    assert set(out.columns) == {"sa2_code", "census_year", "index", "measure", "value"}


def test_build_seifa_index_names_mapped():
    out = build_seifa(_seifa_warehouse_frame())
    # SEIFA_INDEXES values are the friendly names (e.g. "irsd")
    assert set(out["index"].unique().to_list()) == set(SEIFA_INDEXES.values())


def test_build_seifa_measure_names_mapped():
    out = build_seifa(_seifa_warehouse_frame())
    # _SEIFA_MEASURE maps "SCORE"->"score", "RWAD"->"decile_australia", etc.
    assert set(out["measure"].unique().to_list()) == set(_SEIFA_MEASURE.values())


def test_build_seifa_long_shape():
    out = build_seifa(_seifa_warehouse_frame())
    # 4 indexes × 4 measures × 1 SA2 = 16 rows
    assert out.height == 16


# ---------------------------------------------------------------------------
# build_health
# ---------------------------------------------------------------------------


def _g19_warehouse_frame() -> pl.DataFrame:
    """Minimal G19 silver for build_health (needs sexp, agep_label, lthp_label, persons)."""
    rows = []
    for age in ["0-4 years", "5-14 years"]:
        for lthp in ["Total (Persons)", "Arthritis"]:
            rows.append(
                {
                    "sa2_code": "H1",
                    "sexp": "3",
                    "sexp_label": "Persons",
                    "agep_label": age,
                    "lthp_label": lthp,
                    "persons": 10.0 if lthp == "Total (Persons)" else 3.0,
                }
            )
    return pl.DataFrame(rows)


def test_build_health_stamps_census_year_2021():
    from lana.config import Settings

    out = build_health(_g19_warehouse_frame(), Settings())
    assert out["census_year"].to_list() == [2021]


def test_build_health_output_columns():
    from lana.config import Settings

    out = build_health(_g19_warehouse_frame(), Settings())
    assert set(out.columns) == {
        "sa2_code",
        "census_year",
        "condition",
        "asr",
        "crude",
        "denominator",
    }
