"""Geography spine: parent derivation, PHN resolution, rollup conservation."""

import polars as pl
import pytest

from lana.geography import (
    derive_parents,
    dim_geography,
    geo_spine,
    phn_bridge,
    rollup,
    target_sa2_codes,
)


def test_derive_parents():
    assert derive_parents("315031408") == ("31503", "315")


def test_western_queensland_has_12_sa2s():
    codes = target_sa2_codes("Western Queensland")
    assert len(codes) == 12
    assert all(len(c) == 9 for c in codes)


def test_unknown_phn_raises():
    with pytest.raises(ValueError):
        target_sa2_codes("Atlantis Health Network")


def test_spine_parent_codes_match_prefix():
    spine = geo_spine()
    row = spine.filter(pl.col("sa2_code") == "315031408").row(0, named=True)
    assert row["sa3_code"] == "31503"
    assert row["sa4_code"] == "315"


def test_phn_bridge_is_many_to_many():
    bridge = phn_bridge()
    # bridge has at least one more row than there are unique SA2s -> a straddling SA2 exists
    assert bridge.height > bridge["sa2_code"].n_unique()
    # every (sa2, phn) pair is unique
    assert bridge.height == bridge.unique(subset=["sa2_code", "phn_name"]).height
    # dim_geography keeps each SA2 once (primary PHN); the bridge carries the extra straddle rows
    dim = dim_geography()
    assert dim["sa2_code"].n_unique() == bridge["sa2_code"].n_unique()
    assert dim.height < bridge.height
    assert bridge.group_by("sa2_code").len().filter(pl.col("len") > 1).height >= 1


def test_rollup_conserves_totals():
    codes = target_sa2_codes("Western Queensland")
    fact = pl.DataFrame({"sa2_code": codes, "value": [float(i + 1) for i in range(len(codes))]})
    out = rollup(fact, level="phn", group_dims=[], value_col="value")
    assert out.height == 1
    assert out["value"][0] == fact["value"].sum()
