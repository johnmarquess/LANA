"""L1 Bronze — pull a dataflow for a set of SA2 codes and cache to Parquet.

Filters server-side via the SDMX data key (SA2 codes OR'd in the geography
dimension position) so we never download the whole nation. Idempotent: a cached
bronze Parquet short-circuits the API.
"""

from __future__ import annotations

import polars as pl

from lana.abs_client import ABSClient
from lana.config import Settings


def _build_keys(structure: dict, sa2_codes: list[str], batch_size: int) -> list[str]:
    """Build dot-separated SDMX data keys with SA2 codes in the geography slot."""
    order = ABSClient.dimension_order(structure)
    geo_dim = ABSClient.geography_dimension(structure)
    geo_pos = order.index(geo_dim)
    keys = []
    for i in range(0, len(sa2_codes), batch_size):
        batch = sa2_codes[i : i + batch_size]
        parts = ["" for _ in order]
        parts[geo_pos] = "+".join(batch)
        keys.append(".".join(parts))
    return keys


def extract_bronze(
    dataflow_id: str,
    sa2_codes: list[str],
    *,
    cache_tag: str,
    start_period: str | None = None,
    end_period: str | None = None,
    client: ABSClient | None = None,
    settings: Settings | None = None,
    refresh: bool = False,
) -> pl.DataFrame:
    """Extract `dataflow_id` for `sa2_codes`, caching to bronze/<id>__<tag>[__sp_ep].parquet.

    `start_period`/`end_period` default to the single census year; pass a range
    (e.g. 2011..2021) for Time Series (C21_T*) tables.
    """
    s = settings or Settings()
    s.ensure_dirs()
    client = client or ABSClient(s)

    sp = start_period or s.census_year
    ep = end_period or s.census_year
    period_tag = f"__{sp}_{ep}" if (start_period or end_period) else ""
    out = s.bronze_dir / f"{dataflow_id}__{cache_tag}{period_tag}.parquet"
    if out.exists() and not refresh:
        return pl.read_parquet(out)

    structure = client.get_structure(dataflow_id)
    keys = _build_keys(structure, sa2_codes, s.sa2_batch_size)

    frames = []
    for n, key in enumerate(keys, 1):
        print(f"  [{dataflow_id}] batch {n}/{len(keys)} ({key.count('+') + 1} SA2s) {sp}-{ep}")
        df = client.get_data(dataflow_id, key, sp, ep)
        if df.height:
            frames.append(df)

    combined = pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame()
    combined.write_parquet(out)
    print(f"  saved bronze: {out.name} ({combined.height} rows)")
    return combined
