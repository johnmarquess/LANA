"""Bronze data-key construction — pure function, no network."""

from lana.extract import _build_keys


def _structure(dim_ids: list[str]) -> dict:
    """Build a minimal SDMX structure dict; positions follow list order."""
    return {
        "data": {
            "dataStructures": [
                {
                    "dataStructureComponents": {
                        "dimensionList": {
                            "dimensions": [{"id": d, "position": n} for n, d in enumerate(dim_ids)]
                        }
                    }
                }
            ]
        }
    }


def test_build_keys_places_codes_in_geography_slot():
    # REGION is dimension index 2 of 5 -> codes go in the 3rd dot-separated slot.
    st = _structure(["SEXP", "LFSP", "REGION", "REGION_TYPE", "STATE"])
    assert _build_keys(st, ["111", "222"], batch_size=50) == ["..111+222.."]


def test_build_keys_batches_by_size():
    st = _structure(["SEXP", "REGION"])
    assert _build_keys(st, ["a", "b", "c"], batch_size=2) == [".a+b", ".c"]


def test_build_keys_single_batch_when_under_size():
    st = _structure(["REGION", "INCP"])
    assert _build_keys(st, ["x", "y"], batch_size=50) == ["x+y."]
