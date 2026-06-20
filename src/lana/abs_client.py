"""ABS Data API (SDMX REST) client. Open API — no auth/key required.

Ported and slimmed from the legacy `_ABS_Data/src/api_client.py`, switched to
Polars and given retry/backoff + on-disk structure caching.
"""

from __future__ import annotations

import json
import time
from io import StringIO

import httpx
import polars as pl

from lana.config import Settings

_STRUCTURE_JSON = "application/vnd.sdmx.structure+json"
_DATA_CSV = "application/vnd.sdmx.data+csv;labels=both"

# Transient HTTP statuses worth retrying; other 4xx (e.g. 404) are not.
_RETRYABLE_STATUS = (429, 500, 502, 503, 504)

# Dimension-id fragments that identify the geography dimension across GCP/SEIFA dataflows.
_GEO_HINTS = ("REGION", "ASGS", "SA2", "SA1", "SA3", "SA4", "LGA", "STE")


class ABSClient:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or Settings()

    # -- low level ---------------------------------------------------------
    def _get(self, url: str, accept: str, params: dict | None = None) -> httpx.Response:
        """GET with exponential backoff on transient failures.

        Retries timeouts, transport errors and transient HTTP statuses
        (429/5xx). Non-retryable client errors (e.g. 404 from a wrong dataflow
        id) are raised immediately with the real status, not masked behind a
        generic "failed after retries" error.
        """
        last_exc: Exception | None = None
        for attempt in range(self.s.api_max_retries):
            try:
                with httpx.Client(timeout=self.s.api_timeout) as c:
                    r = c.get(url, params=params, headers={"Accept": accept})
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_exc = e
                time.sleep(2.0**attempt)
                continue
            if r.status_code in _RETRYABLE_STATUS:
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {r.status_code}", request=r.request, response=r
                )
                time.sleep(2.0**attempt)
                continue
            r.raise_for_status()  # non-retryable 4xx surface immediately
            time.sleep(self.s.api_throttle_seconds)  # polite spacing
            return r
        raise RuntimeError(
            f"ABS API request failed after {self.s.api_max_retries} retries: {url}"
        ) from last_exc

    # -- structure ---------------------------------------------------------
    def get_structure(self, dataflow_id: str) -> dict:
        """Fetch a dataflow's DSD (dimensions + codelists), cached to disk."""
        cache = self.s.reference_dir / "_structure_cache" / f"{dataflow_id}.json"
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        url = f"{self.s.api_base_url}/dataflow/{self.s.api_agency_id}/{dataflow_id}"
        data = self._get(url, _STRUCTURE_JSON, params={"references": "descendants"}).json()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data), encoding="utf-8")
        return data

    @staticmethod
    def dimension_order(structure: dict) -> list[str]:
        """Ordered dimension ids (excluding TIME_PERIOD), by SDMX position."""
        ds = structure["data"]["dataStructures"][0]
        dims = ds["dataStructureComponents"]["dimensionList"]["dimensions"]
        dims = sorted(dims, key=lambda d: d.get("position", 0))
        return [d["id"] for d in dims if d["id"] != "TIME_PERIOD"]

    @classmethod
    def geography_dimension(cls, structure: dict) -> str:
        for dim in cls.dimension_order(structure):
            if any(h in dim.upper() for h in _GEO_HINTS):
                return dim
        raise ValueError("Could not locate a geography dimension in the DSD")

    # -- data --------------------------------------------------------------
    def get_data(
        self,
        dataflow_id: str,
        data_key: str = "all",
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> pl.DataFrame:
        """Return data as a Polars DataFrame (CSV with both codes and labels)."""
        flow = dataflow_id if "," in dataflow_id else f"{self.s.api_agency_id},{dataflow_id}"
        url = f"{self.s.api_base_url}/data/{flow}/{data_key}"
        params: dict[str, str] = {}
        if start_period:
            params["startPeriod"] = start_period
        if end_period:
            params["endPeriod"] = end_period
        text = self._get(url, _DATA_CSV, params=params).text
        if not text.strip():
            return pl.DataFrame()
        return pl.read_csv(StringIO(text), infer_schema_length=2000)
