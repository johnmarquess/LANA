"""End-to-end orchestration: run the full 4-layer pipeline for one PHN.

uv run lana --phn "Western Queensland"
"""

from __future__ import annotations

import argparse
import re

import polars as pl

from lana.abs_client import ABSClient
from lana.config import Settings
from lana.extract import extract_bronze
from lana.geography import target_sa2_codes
from lana.indicators import build_gold
from lana.normalise import normalise
from lana.workbook import write_workbook

# (dataflow_id, measure_name, geography_dimension_id)
SOURCES = {
    "g01": ("C21_G01_SA2", "persons", "REGION"),
    "g19": ("C21_G19_SA2", "persons", "REGION"),
    "seifa": ("ABS_SEIFA2021_SA2", "value", "ASGS_2021"),
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def run_phn(phn: str, settings: Settings | None = None, refresh: bool = False) -> dict:
    s = settings or Settings()
    s.ensure_dirs()
    client = ABSClient(s)
    tag = _slug(phn)

    sa2_codes = target_sa2_codes(phn, s)
    print(f"PHN '{phn}': {len(sa2_codes)} SA2s")

    silver: dict[str, pl.DataFrame] = {}
    for key, (flow, measure, geo_dim) in SOURCES.items():
        print(f"Extracting {flow} ...")
        bronze = extract_bronze(
            flow, sa2_codes, cache_tag=tag, client=client, settings=s, refresh=refresh
        )
        df = normalise(bronze, measure=measure, geo_dim=geo_dim)
        df.write_parquet(s.silver_dir / f"{flow}__{tag}.parquet")
        silver[key] = df

    print("Building gold layer ...")
    gold = build_gold(silver["g01"], silver["g19"], silver["seifa"], settings=s)

    for name, df in gold.items():
        if not name.startswith("_"):
            df.write_parquet(s.gold_dir / f"{name}__{tag}.parquet")

    default_condition = gold["_meta"].filter(pl.col("key") == "default_condition")["value"][0]
    meta = {
        "Tool": "LANA — Local & Regional Area Needs Assessment",
        "Primary Health Network": phn,
        "SA2 count": str(len(sa2_codes)),
        "Census": f"ABS Census {s.census_year} (General Community Profile)",
        "Source dataflows": "C21_G01_SA2, C21_G19_SA2, ABS_SEIFA2021_SA2",
        "Geography": "ASGS 2021 SA2 -> SA3/SA4/LGA, PHN 2023 boundaries",
        "Standardisation": "Direct, Australian Standard Population 2001 (per 100,000)",
        "Equity headline condition": default_condition,
        "Caveat — SEIFA at PHN": "Deciles are not averaged; PHN shows the SA2 distribution.",
        "Caveat — small areas": "Rates on small SA2 populations are unstable (ABS perturbs small counts).",
    }
    out = write_workbook(s.output_dir / f"{tag}_needs_assessment.xlsx", gold, meta)
    print(f"Wrote {out}")
    return {"output": out, "gold": gold, "sa2_count": len(sa2_codes)}


def main() -> None:
    p = argparse.ArgumentParser(description="Build the per-PHN needs-assessment workbook.")
    p.add_argument("--phn", default=None, help="Target Primary Health Network name")
    p.add_argument("--refresh", action="store_true", help="Ignore bronze cache and re-fetch")
    args = p.parse_args()
    s = Settings()
    run_phn(args.phn or s.target_phn, s, refresh=args.refresh)


def warehouse_main() -> None:
    from lana.warehouse import build_warehouse

    p = argparse.ArgumentParser(description="Build the normalised gold warehouse (all QLD SA2s).")
    p.add_argument("--refresh", action="store_true", help="Ignore bronze cache and re-fetch")
    args = p.parse_args()
    build_warehouse(Settings(), refresh=args.refresh)


if __name__ == "__main__":
    main()
