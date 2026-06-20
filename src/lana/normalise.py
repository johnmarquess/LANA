"""L2 Silver — generic star-schema normaliser.

ABS CSV (labels=both) has columns like ``"REGION: Region"`` with values like
``"315031408: Barcaldine - Blackall"``. One generic transform splits every
``"CODE: Label"`` column into code + label and tidies the measure/time columns,
so we never write a bespoke module per GCP table (the legacy's failure mode).
"""

from __future__ import annotations

import polars as pl

from lana.constants import GEO_HINTS


def _is_geo_token(token: str) -> bool:
    t = token.upper()
    if t.endswith("_TYPE") or t.endswith("_STATUS"):
        return False
    return any(h in t for h in GEO_HINTS)


def normalise(
    df: pl.DataFrame,
    *,
    measure: str = "value",
    geo_dim: str | None = None,
) -> pl.DataFrame:
    """Tidy a raw ABS CSV frame into a long fact.

    - the geography dimension becomes ``sa2_code`` + ``sa2_name``
    - every other ``"TOKEN: ..."`` dimension becomes ``token`` (code) + ``token_label``
    - ``OBS_VALUE`` -> ``measure`` (float); ``TIME_PERIOD`` -> ``year`` (int)

    `geo_dim` (the dimension id from the DSD) disambiguates when several columns
    look geographic (e.g. REGION vs REGION_TYPE); auto-detected if omitted.
    """
    if df.is_empty():
        return df

    exprs: list[pl.Expr] = []
    geo_assigned = False
    for c in df.columns:
        if c == "DATAFLOW":
            continue
        if c == "OBS_VALUE":
            exprs.append(pl.col(c).cast(pl.Float64, strict=False).alias(measure))
            continue
        if ":" not in c:  # plain passthrough column (e.g. OBS_STATUS)
            exprs.append(pl.col(c).alias(c.strip().lower()))
            continue

        token = c.split(":", 1)[0].strip()
        if token == "TIME_PERIOD":
            exprs.append(pl.col(c).cast(pl.Int32, strict=False).alias("year"))
            continue

        split = pl.col(c).cast(pl.Utf8).str.splitn(": ", 2)
        is_geo = (token == geo_dim) if geo_dim else _is_geo_token(token)
        if is_geo and not geo_assigned:
            exprs.append(split.struct.field("field_0").str.strip_chars().alias("sa2_code"))
            exprs.append(split.struct.field("field_1").str.strip_chars().alias("sa2_name"))
            geo_assigned = True
        else:
            base = token.lower()
            exprs.append(split.struct.field("field_0").str.strip_chars().alias(base))
            exprs.append(split.struct.field("field_1").str.strip_chars().alias(f"{base}_label"))

    return df.select(exprs)
