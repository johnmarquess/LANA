"""Age-standardisation: worked example against the real ASP-2001 constants."""

import polars as pl

from lana.standardise import age_standardised_rate, parse_age_range, std_pop_table


def test_parse_age_range():
    assert parse_age_range("25-34 years") == (25, 34)
    assert parse_age_range("Age groups: 0-14 years") == (0, 14)
    assert parse_age_range("85 years and over") == (85, 100)
    assert parse_age_range("Total") is None
    assert parse_age_range("Not stated") is None


def test_std_pop_known_sums():
    # Verified directly from the ABS data cube (total = 19,413,240).
    t = std_pop_table(["0-14 years", "15-24 years", "85 years and over", "Total"])
    got = dict(zip(t["age_label"].to_list(), t["std_pop"].to_list()))
    assert got["0-14 years"] == 3_987_198
    assert got["15-24 years"] == 2_655_157
    assert got["85 years and over"] == 265_235
    assert "Total" not in got  # totals dropped


def test_direct_asr_worked_example():
    # Two age groups, one region. Hand-computed against the real standard pops:
    # ASR = (0.1*3,987,198 + 0.2*2,655,157) / (3,987,198+2,655,157) * 100000
    df = pl.DataFrame(
        {
            "region": ["A", "A"],
            "agep_label": ["0-14 years", "15-24 years"],
            "num": [100, 200],
            "den": [1000, 1000],
        }
    )
    res = age_standardised_rate(
        df, group_keys=["region"], age_label_col="agep_label", num_col="num", den_col="den"
    )
    expected = (0.1 * 3_987_198 + 0.2 * 2_655_157) / (3_987_198 + 2_655_157) * 100_000
    assert abs(res["asr"][0] - expected) < 1e-6
    assert res["denominator"][0] == 2000


def test_zero_denominator_yields_null_not_nan():
    # A region with no population must give null rates, never NaN (xlsxwriter rejects NaN).
    df = pl.DataFrame(
        {
            "region": ["Z", "Z"],
            "agep_label": ["0-14 years", "15-24 years"],
            "num": [0, 0],
            "den": [0, 0],
        }
    )
    res = age_standardised_rate(
        df, group_keys=["region"], age_label_col="agep_label", num_col="num", den_col="den"
    )
    assert res["crude"][0] is None
    assert res["asr"][0] == 0.0  # expected cases are 0 over a positive standard pop
