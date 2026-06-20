"""ABS client DSD parsing and retry behaviour — pure functions, no network."""

import httpx
import polars as pl
import pytest

from lana import abs_client
from lana.abs_client import ABSClient
from lana.config import Settings


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


# --- retry behaviour ------------------------------------------------------
class _FakeClient:
    """Context-manager stand-in for httpx.Client; .get returns a fixed status."""

    def __init__(self, status: int, text: str = "ok"):
        self._status = status
        self._text = text

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, params=None, headers=None):
        return httpx.Response(self._status, request=httpx.Request("GET", url), text=self._text)


def _patch(monkeypatch, statuses):
    it = iter(statuses)
    monkeypatch.setattr(abs_client.httpx, "Client", lambda *a, **k: _FakeClient(next(it)))
    monkeypatch.setattr(abs_client.time, "sleep", lambda *_: None)  # no real backoff waits


def test_get_retries_transient_then_succeeds(monkeypatch):
    _patch(monkeypatch, [503, 200])
    r = ABSClient(Settings())._get("http://x", "application/json")
    assert r.status_code == 200


def test_get_raises_immediately_on_non_retryable(monkeypatch):
    calls: list[int] = []

    def factory(*a, **k):
        calls.append(1)
        return _FakeClient(404)

    monkeypatch.setattr(abs_client.httpx, "Client", factory)
    monkeypatch.setattr(abs_client.time, "sleep", lambda *_: None)
    with pytest.raises(httpx.HTTPStatusError):
        ABSClient(Settings())._get("http://x", "application/json")
    assert len(calls) == 1  # the 404 is not retried


def test_get_raises_runtimeerror_after_exhausting_retries(monkeypatch):
    _patch(monkeypatch, [503, 503, 503, 503])  # api_max_retries default = 4
    with pytest.raises(RuntimeError):
        ABSClient(Settings())._get("http://x", "application/json")


def test_get_data_handles_type_change_after_inference_window(monkeypatch):
    # OBS_VALUE is integer for >2000 rows then a decimal — full-scan inference must
    # pick Float64 (not truncate at 2000 rows and fail to parse 1.5 as int).
    n = 2001
    rows = [f"100: A,{i}" for i in range(n)] + ["100: A,1.5"]
    csv = "REGION: Region,OBS_VALUE\n" + "\n".join(rows)
    monkeypatch.setattr(abs_client.httpx, "Client", lambda *a, **k: _FakeClient(200, text=csv))
    monkeypatch.setattr(abs_client.time, "sleep", lambda *_: None)
    df = ABSClient(Settings()).get_data("ABS,FLOW", "all")
    assert df.height == n + 1
    assert df["OBS_VALUE"].dtype == pl.Float64
    assert df["OBS_VALUE"][-1] == 1.5
