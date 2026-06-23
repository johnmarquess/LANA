"""Silver normaliser: code/label split, measure/time casting, geo disambiguation."""

import polars as pl

from lana.normalise import normalise


def _raw():
    return pl.DataFrame(
        {
            "DATAFLOW": ["ABS:C21_G01_SA2", "ABS:C21_G01_SA2"],
            "SEXP: Sex": ["3: Persons", "1: Males"],
            "REGION: Region": ["315031408: Barcaldine - Blackall", "307011171: Balonne"],
            "REGION_TYPE: Region Type": [
                "SA2: Statistical Area Level 2",
                "SA2: Statistical Area Level 2",
            ],
            "TIME_PERIOD: Time Period": ["2021", "2021"],
            "OBS_VALUE": ["123", "45"],
        }
    )


def test_code_label_split_and_casts():
    out = normalise(_raw(), measure="persons", geo_dim="REGION")
    assert out["sa2_code"].to_list() == ["315031408", "307011171"]
    assert out["sa2_name"].to_list() == ["Barcaldine - Blackall", "Balonne"]
    assert out["sexp"].to_list() == ["3", "1"]
    assert out["persons"].to_list() == [123.0, 45.0]
    assert out["year"].to_list() == [2021, 2021]
    assert out["persons"].dtype == pl.Float64


def test_region_type_not_treated_as_geography():
    # REGION_TYPE contains 'REGION' but must NOT overwrite sa2_code; it becomes its own dim.
    out = normalise(_raw(), measure="persons", geo_dim="REGION")
    assert "region_type" in out.columns
    assert out["sa2_code"].to_list() == ["315031408", "307011171"]


def test_value_without_colon():
    df = pl.DataFrame({"SEXP: Sex": ["Total"], "OBS_VALUE": ["7"]})
    out = normalise(df, measure="persons")
    assert out["sexp"].to_list() == ["Total"]
    assert out["sexp_label"].to_list() == [None]


def test_auto_detect_region_geo_dim():
    # REGION column auto-detected as geography without passing geo_dim.
    df = pl.DataFrame(
        {
            "REGION: Region": ["315031408: Barcaldine - Blackall"],
            "OBS_VALUE": ["99"],
        }
    )
    out = normalise(df, measure="persons")
    assert out["sa2_code"].to_list() == ["315031408"]
    assert out["sa2_name"].to_list() == ["Barcaldine - Blackall"]


def test_auto_detect_asgs_2021_geo_dim():
    # ASGS_2021 column auto-detected as geography without passing geo_dim.
    df = pl.DataFrame(
        {
            "ASGS_2021: Region": ["101021007: Gungahlin"],
            "OBS_VALUE": ["55"],
        }
    )
    out = normalise(df, measure="value")
    assert out["sa2_code"].to_list() == ["101021007"]
    assert out["sa2_name"].to_list() == ["Gungahlin"]
