"""ABS client DSD parsing — pure functions, no network."""

import pytest

from lana.abs_client import ABSClient


def _structure(dims: list[tuple[str, int]]) -> dict:
    """Build a minimal SDMX structure dict from (dimension_id, position) pairs."""
    return {
        "data": {
            "dataStructures": [
                {
                    "dataStructureComponents": {
                        "dimensionList": {"dimensions": [{"id": i, "position": p} for i, p in dims]}
                    }
                }
            ]
        }
    }


def test_dimension_order_sorts_by_position_and_drops_time():
    st = _structure([("REGION", 3), ("SEXP", 1), ("TIME_PERIOD", 9), ("LFSP", 2)])
    assert ABSClient.dimension_order(st) == ["SEXP", "LFSP", "REGION"]


def test_geography_dimension_picks_region_over_region_type():
    st = _structure([("SEXP", 1), ("REGION", 2), ("REGION_TYPE", 3), ("STATE", 4)])
    assert ABSClient.geography_dimension(st) == "REGION"


def test_geography_dimension_detects_asgs():
    st = _structure([("ASGS_2021", 1), ("SEIFAINDEXTYPE", 2), ("SEIFA_MEASURE", 3)])
    assert ABSClient.geography_dimension(st) == "ASGS_2021"


def test_geography_dimension_raises_when_absent():
    st = _structure([("SEXP", 1), ("INCP", 2)])
    with pytest.raises(ValueError):
        ABSClient.geography_dimension(st)
