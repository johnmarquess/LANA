"""Gold layer — indicators: demographic_sa2, seifa_sa2, health_asr, equity_sa2, seifa_phn_summary."""

from __future__ import annotations

import polars as pl

from lana.geography import target_sa2_codes
from lana.indicators import (
    _health_num_den,
    demographic_sa2,
    equity_sa2,
    health_asr,
    seifa_phn_summary,
    seifa_sa2,
)

# ---------------------------------------------------------------------------
# demographic_sa2
# ---------------------------------------------------------------------------


def _g01_frame() -> pl.DataFrame:
    """Minimal G01 silver: two SA2s, sexp==3 (Persons), plus a Male row to be ignored."""
    rows = [
        # SA2 "A" — Persons rows
        {
            "sa2_code": "A",
            "year": 2021,
            "sexp": "3",
            "sexp_label": "Persons",
            "pchar_label": "Age groups: 0-4 years",
            "persons": 100.0,
        },
        {
            "sa2_code": "A",
            "year": 2021,
            "sexp": "3",
            "sexp_label": "Persons",
            "pchar_label": "Age groups: 5-14 years",
            "persons": 200.0,
        },
        {
            "sa2_code": "A",
            "year": 2021,
            "sexp": "3",
            "sexp_label": "Persons",
            "pchar_label": "Age groups: Total",
            "persons": 300.0,
        },  # must be excluded
        {
            "sa2_code": "A",
            "year": 2021,
            "sexp": "3",
            "sexp_label": "Persons",
            "pchar_label": "Aboriginal and/or Torres Strait Islander persons: Total",
            "persons": 60.0,
        },
        {
            "sa2_code": "A",
            "year": 2021,
            "sexp": "3",
            "sexp_label": "Persons",
            "pchar_label": "Language used at home: Other language",
            "persons": 90.0,
        },
        {
            "sa2_code": "A",
            "year": 2021,
            "sexp": "3",
            "sexp_label": "Persons",
            "pchar_label": "Highest year of school completed: Year 12 or equivalent",
            "persons": 150.0,
        },
        # SA2 "A" — Males row (sexp != 3, must be ignored)
        {
            "sa2_code": "A",
            "year": 2021,
            "sexp": "1",
            "sexp_label": "Males",
            "pchar_label": "Age groups: 0-4 years",
            "persons": 50.0,
        },
        # SA2 "B" — zero population (all age leaf rows are 0)
        {
            "sa2_code": "B",
            "year": 2021,
            "sexp": "3",
            "sexp_label": "Persons",
            "pchar_label": "Age groups: 0-4 years",
            "persons": 0.0,
        },
        {
            "sa2_code": "B",
            "year": 2021,
            "sexp": "3",
            "sexp_label": "Persons",
            "pchar_label": "Age groups: Total",
            "persons": 0.0,
        },
        {
            "sa2_code": "B",
            "year": 2021,
            "sexp": "3",
            "sexp_label": "Persons",
            "pchar_label": "Aboriginal and/or Torres Strait Islander persons: Total",
            "persons": 0.0,
        },
        {
            "sa2_code": "B",
            "year": 2021,
            "sexp": "3",
            "sexp_label": "Persons",
            "pchar_label": "Language used at home: Other language",
            "persons": 0.0,
        },
        {
            "sa2_code": "B",
            "year": 2021,
            "sexp": "3",
            "sexp_label": "Persons",
            "pchar_label": "Highest year of school completed: Year 12 or equivalent",
            "persons": 0.0,
        },
    ]
    return pl.DataFrame(rows)


def test_demographic_sa2_total_pop_excludes_age_total():
    out = demographic_sa2(_g01_frame())
    row_a = out.filter(pl.col("sa2_code") == "A").to_dicts()[0]
    # 100 + 200 = 300 (not 300 from the "Total" row)
    assert row_a["total_pop"] == 300


def test_demographic_sa2_percentages():
    out = demographic_sa2(_g01_frame())
    row_a = out.filter(pl.col("sa2_code") == "A").to_dicts()[0]
    assert row_a["indigenous_pct"] == round(60 / 300 * 100, 1)
    assert row_a["other_language_pct"] == round(90 / 300 * 100, 1)
    assert row_a["year12_pct"] == round(150 / 300 * 100, 1)


def test_demographic_sa2_zero_pop_yields_null_pct():
    out = demographic_sa2(_g01_frame())
    row_b = out.filter(pl.col("sa2_code") == "B").to_dicts()[0]
    assert row_b["total_pop"] == 0
    assert row_b["indigenous_pct"] is None
    assert row_b["other_language_pct"] is None
    assert row_b["year12_pct"] is None


# ---------------------------------------------------------------------------
# seifa_sa2
# ---------------------------------------------------------------------------


def _seifa_frame() -> pl.DataFrame:
    """Minimal SEIFA silver: one SA2 with IRSD score, decile (RWAD), and population (URP)."""
    rows = [
        {
            "sa2_code": "S1",
            "year": 2021,
            "seifaindextype": "IRSD",
            "seifa_measure": "SCORE",
            "value": 950.0,
        },
        {
            "sa2_code": "S1",
            "year": 2021,
            "seifaindextype": "IRSD",
            "seifa_measure": "RWAD",
            "value": 3.0,
        },
        {
            "sa2_code": "S1",
            "year": 2021,
            "seifaindextype": "IRSD",
            "seifa_measure": "URP",
            "value": 5000.0,
        },
        {
            "sa2_code": "S1",
            "year": 2021,
            "seifaindextype": "IRSAD",
            "seifa_measure": "SCORE",
            "value": 980.0,
        },
        {
            "sa2_code": "S1",
            "year": 2021,
            "seifaindextype": "IRSAD",
            "seifa_measure": "RWAD",
            "value": 4.0,
        },
        {
            "sa2_code": "S1",
            "year": 2021,
            "seifaindextype": "IRSAD",
            "seifa_measure": "URP",
            "value": 5000.0,
        },
        # IER / IEO omitted — function filters to SEIFA_INDEXES which includes all four,
        # but our frame only has two; the test just checks the columns we care about.
    ]
    return pl.DataFrame(rows)


def test_seifa_sa2_score_and_decile_columns():
    out = seifa_sa2(_seifa_frame())
    assert "irsd_score" in out.columns
    assert "irsd_decile" in out.columns


def test_seifa_sa2_decile_from_rwad():
    # RWAD is the national decile measure — must land in irsd_decile
    out = seifa_sa2(_seifa_frame())
    row = out.filter(pl.col("sa2_code") == "S1").to_dicts()[0]
    assert row["irsd_decile"] == 3.0


def test_seifa_sa2_urp_taken_once():
    # URP appears for every index type; must collapse to a single urp value per SA2
    out = seifa_sa2(_seifa_frame())
    row = out.filter(pl.col("sa2_code") == "S1").to_dicts()[0]
    assert row["urp"] == 5000.0


# ---------------------------------------------------------------------------
# _health_num_den / health_asr (SA2 level)
# ---------------------------------------------------------------------------


def _g19_frame() -> pl.DataFrame:
    """Minimal G19 silver: two age groups, one condition, two non-condition labels, sexp==3."""
    rows = []
    for age in ["0-4 years", "5-14 years"]:
        for lthp in [
            "Total (Persons)",  # denominator — must NOT enter numerator
            "No long-term health condition(s)",  # excluded
            "Not stated",  # excluded
            "Arthritis",  # condition
        ]:
            rows.append(
                {
                    "sa2_code": "H1",
                    "sexp": "3",
                    "sexp_label": "Persons",
                    "agep_label": age,
                    "lthp_label": lthp,
                    "persons": 10.0
                    if lthp == "Total (Persons)"
                    else (5.0 if lthp == "Arthritis" else 0.0),
                }
            )
    # Add a Total age row — must be excluded
    rows.append(
        {
            "sa2_code": "H1",
            "sexp": "3",
            "sexp_label": "Persons",
            "agep_label": "Total",
            "lthp_label": "Total (Persons)",
            "persons": 999.0,
        }
    )
    # Add a Males row — must be excluded (sexp != 3)
    rows.append(
        {
            "sa2_code": "H1",
            "sexp": "1",
            "sexp_label": "Males",
            "agep_label": "0-4 years",
            "lthp_label": "Total (Persons)",
            "persons": 999.0,
        }
    )
    return pl.DataFrame(rows)


def test_health_num_den_excludes_age_total():
    nd = _health_num_den(_g19_frame())
    assert "Total" not in nd["agep_label"].to_list()


def test_health_num_den_denominator_from_total_persons():
    nd = _health_num_den(_g19_frame())
    # Every row's den must equal the "Total (Persons)" value for that (sa2, age) — which is 10
    for row in nd.to_dicts():
        assert row["den"] == 10.0


def test_health_num_den_excludes_non_conditions():
    nd = _health_num_den(_g19_frame())
    # Only "Arthritis" should appear as a condition
    assert set(nd["condition"].to_list()) == {"Arthritis"}


def test_health_asr_produces_asr_crude_denominator():
    out = health_asr(_g19_frame(), level="sa2")
    assert {"sa2_code", "condition", "asr", "crude", "denominator"}.issubset(set(out.columns))


def test_health_asr_worked_example():
    # num=5, den=10 per age group; age groups '0-4 years' and '5-14 years'
    # std pops (from asp_2001_single_year.csv): 1_282_357 and 2_704_841
    # ASR = ((5/10)*1282357 + (5/10)*2704841) / (1282357+2704841) * 100000
    sp0 = 1_282_357
    sp1 = 2_704_841
    expected_asr = ((5 / 10 * sp0) + (5 / 10 * sp1)) / (sp0 + sp1) * 100_000
    out = health_asr(_g19_frame(), level="sa2")
    row = out.filter(pl.col("condition") == "Arthritis").to_dicts()[0]
    assert abs(row["asr"] - expected_asr) < 1e-6
    assert row["crude"] == 5 / 10 * 100_000
    assert row["denominator"] == 20  # sum of den across both age groups


# ---------------------------------------------------------------------------
# equity_sa2
# ---------------------------------------------------------------------------


def _equity_inputs() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Minimal inputs: two conditions; 'Arthritis' clearly most prevalent."""
    health = pl.DataFrame(
        {
            "sa2_code": ["H1", "H1"],
            "condition": ["Arthritis", "Asthma"],
            "asr": [50_000.0, 10_000.0],
            "crude": [40_000.0, 8_000.0],
            "denominator": [200.0, 200.0],
        }
    )
    seif = pl.DataFrame(
        {
            "sa2_code": ["H1"],
            "irsd_score": [950.0],
            "irsd_decile": [3.0],
        }
    )
    demo = pl.DataFrame(
        {
            "sa2_code": ["H1"],
            "total_pop": [300],
        }
    )
    return health, seif, demo


def test_equity_sa2_selects_most_prevalent_condition():
    health, seif, demo = _equity_inputs()
    condition, out = equity_sa2(health, seif, demo)
    assert condition == "Arthritis"


def test_equity_sa2_output_has_required_columns():
    health, seif, demo = _equity_inputs()
    _, out = equity_sa2(health, seif, demo)
    assert {"sa2_code", "irsd_decile", "asr"}.issubset(set(out.columns))


def test_equity_sa2_joins_irsd_decile():
    health, seif, demo = _equity_inputs()
    _, out = equity_sa2(health, seif, demo)
    row = out.filter(pl.col("sa2_code") == "H1").to_dicts()[0]
    assert row["irsd_decile"] == 3.0
    assert row["asr"] == 50_000.0


# ---------------------------------------------------------------------------
# seifa_phn_summary
# ---------------------------------------------------------------------------


def test_seifa_phn_summary_n_sa2_and_median():
    # Use real Western Queensland SA2 codes so the geo_spine join succeeds.
    codes = target_sa2_codes("Western Queensland")[:4]  # ponytail: small slice
    seif_df = pl.DataFrame(
        {
            "sa2_code": codes,
            "irsd_score": [900.0, 920.0, 880.0, 960.0],
            "irsd_decile": [2.0, 3.0, 1.0, 4.0],
            "urp": [1000.0, 2000.0, 1500.0, 500.0],
        }
    )
    out = seifa_phn_summary(seif_df)
    row = out.filter(pl.col("phn_name") == "Western Queensland").to_dicts()[0]
    # n_sa2 counts distinct SA2 codes in this PHN
    assert row["n_sa2"] == 4
    # irsd_decile_median: plain (unweighted) median of [2, 3, 1, 4] = 2.5
    assert row["irsd_decile_median"] == 2.5


def test_seifa_phn_summary_pop_pct_bottom2_deciles_is_urp_weighted():
    codes = target_sa2_codes("Western Queensland")[:4]
    # deciles 1 and 2 are "bottom 2"; their URP = 1000 + 1500 = 2500 out of 5000 total -> 50%
    seif_df = pl.DataFrame(
        {
            "sa2_code": codes,
            "irsd_score": [900.0, 920.0, 880.0, 960.0],
            "irsd_decile": [2.0, 3.0, 1.0, 4.0],
            "urp": [1000.0, 2000.0, 1500.0, 500.0],
        }
    )
    out = seifa_phn_summary(seif_df)
    row = out.filter(pl.col("phn_name") == "Western Queensland").to_dicts()[0]
    assert row["pop_pct_in_bottom2_deciles"] == 50.0


# ---------------------------------------------------------------------------
# Straddler behaviour — SA2 309041242 (Tamborine-Canungra) straddles
# Gold Coast AND Brisbane South; it must be included in both and must not
# produce phantom rows for a third PHN.
# ---------------------------------------------------------------------------

_STRADDLER = "309041242"  # Tamborine-Canungra: Gold Coast + Brisbane South


def _g19_straddler() -> pl.DataFrame:
    """Minimal G19 silver for the straddling SA2 only (Total=10, Arthritis=4 per age)."""
    rows = []
    for age in ["0-4 years", "5-14 years"]:
        rows.append(
            {
                "sa2_code": _STRADDLER,
                "sexp": "3",
                "sexp_label": "Persons",
                "agep_label": age,
                "lthp_label": "Total (Persons)",
                "persons": 10.0,
            }
        )
        rows.append(
            {
                "sa2_code": _STRADDLER,
                "sexp": "3",
                "sexp_label": "Persons",
                "agep_label": age,
                "lthp_label": "Arthritis",
                "persons": 4.0,
            }
        )
    return pl.DataFrame(rows)


def _seifa_straddler() -> pl.DataFrame:
    """Minimal SEIFA silver for the straddling SA2 only."""
    return pl.DataFrame(
        {
            "sa2_code": [_STRADDLER],
            "irsd_score": [950.0],
            "irsd_decile": [5.0],
            "urp": [1000.0],
        }
    )


def test_health_asr_straddler_included_in_both_phns():
    """health_asr(level='phn', phn=X) must include the straddling SA2 under each PHN.

    The arbitrary-primary geo_spine assignment would have dropped 309041242 from
    one of its two PHNs; the bridge keeps it in both. den == 20 (10+10 across the
    two age groups) under EACH of Gold Coast and Brisbane South.
    """
    g19 = _g19_straddler()

    gc_out = health_asr(g19, level="phn", phn="Gold Coast")
    bs_out = health_asr(g19, level="phn", phn="Brisbane South")

    gc_row = gc_out.filter(pl.col("condition") == "Arthritis").to_dicts()[0]
    assert gc_row["denominator"] == 20

    bs_row = bs_out.filter(pl.col("condition") == "Arthritis").to_dicts()[0]
    assert bs_row["denominator"] == 20


def test_health_asr_no_phantom_phn_rows():
    """health_asr(level='phn', phn='Gold Coast') must produce exactly one PHN row."""
    g19 = _g19_straddler()
    out = health_asr(g19, level="phn", phn="Gold Coast")
    assert out["phn_name"].n_unique() == 1
    assert out["phn_name"][0] == "Gold Coast"


def test_seifa_phn_summary_straddler_included_in_both_phns():
    """seifa_phn_summary(phn=X) must include the straddling SA2 under each PHN."""
    seif = _seifa_straddler()

    gc_out = seifa_phn_summary(seif, phn="Gold Coast")
    bs_out = seifa_phn_summary(seif, phn="Brisbane South")

    gc_row = gc_out.filter(pl.col("phn_name") == "Gold Coast").to_dicts()[0]
    assert gc_row["n_sa2"] == 1

    bs_row = bs_out.filter(pl.col("phn_name") == "Brisbane South").to_dicts()[0]
    assert bs_row["n_sa2"] == 1


def test_seifa_phn_summary_no_phantom_phn_rows():
    """seifa_phn_summary(phn='Gold Coast') must produce exactly one PHN row."""
    seif = _seifa_straddler()
    out = seifa_phn_summary(seif, phn="Gold Coast")
    assert out.height == 1
    assert out["phn_name"][0] == "Gold Coast"
