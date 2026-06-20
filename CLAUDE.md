# CLAUDE.md — LANA

Guidance for working in this repo. Read this before editing.

## What this is
LANA (Local & Regional Area Needs Assessment) extracts ABS Census (2011/2016/2021) and SEIFA
at SA2 level, normalises it, age-standardises health rates, and emits a **normalised gold
warehouse** (flat files keyed on SA2/PHN) for loading into a database — plus an optional
per-PHN Excel workbook. Currently scoped to Queensland (7 PHNs).

## Commands (always via `uv` — never `pip`/`python` directly)
```bash
uv run lana-warehouse            # build the gold warehouse (all QLD SA2s) -> data/warehouse/
uv run lana --phn "Gold Coast"   # optional per-PHN Excel workbook
uv run --extra dev pytest -q     # tests
```
On Windows, prefix one-off scripts that print ABS labels with `PYTHONIOENCODING=utf-8 PYTHONUTF8=1`
(the console is cp1252 and chokes on unicode dashes/accents).

## Pipeline (medallion — reuse these layers, don't reinvent)
`abs_client` (SDMX REST) → `extract` (bronze, cached) → `normalise` (silver, generic
`"CODE: Label"` → long fact) → `facts`/`indicators` (gold) → `warehouse`/`workbook`.
`geography` is the conformed spine (SA2→SA3/SA4/LGA/PHN); `registry` declares each domain;
`standardise` does direct age-standardisation (ASP-2001).

## Rules

### Language — Australian English, across the repo
Use Australian/British spelling in **all** prose, comments, docstrings, schema docs, and
**new identifiers**: `normalise`, `standardise`, `optimise`, `behaviour`, `catalogue`,
`centre`, `licence` (noun). **Exceptions** (do not "fix"): external identifiers we don't
own — ABS dimension tokens (`SEXP`, `LFSP`), dataflow IDs, and Python stdlib/3rd-party APIs.

### Code
- Python ≥3.13, full type hints, `from __future__ import annotations`.
- **Polars only — never pandas.** (pandas is the legacy's mistake.)
- Add deps with `uv add`; they go in `pyproject.toml`. Never hand-edit the lockfile.
- Laziness is the house style (see "Ponytail" below): stdlib/native before deps, shortest
  working diff, delete over add. Mark deliberate shortcuts with a `# ponytail:` comment.
- Non-trivial logic leaves **one runnable check** behind (a `tests/test_*.py`, asserts only —
  no fixtures/frameworks unless asked). Trivial one-liners need no test.

### Data & domain invariants (violating these silently corrupts results)
- **SA2 is the atomic grain.** Everything coarser (SA3/SA4/LGA/PHN) is an aggregation.
- **Geographic codes are strings, never ints** (leading digits / vintage codes matter).
- **Read dimensions from the DSD at runtime** (`abs_client.dimension_order`/`geography_dimension`).
  Never hardcode dimension order — it varies per dataflow.
- **Marginalise cross-tabs by filtering other dimensions to their `Total`/`Persons` row,
  never by summing** — ABS tables carry a Total in every dimension; summing double-counts.
- **Guard zero denominators → `null`, never `NaN`** (xlsxwriter rejects NaN; NaN also breaks
  joins). Carry the `denominator` column so downstream can recompute rates.
- **PHN is many-to-many**: a few SA2s straddle two PHNs. Join via `bridge_sa2_phn`, not
  `dim_geography.phn_name` (which is only the primary assignment).
- **ABS Data API is open (no key) but times out on large pulls** → batch SA2s and cache bronze;
  re-runs must hit the cache, not the network.
- Watch nested **sub-totals** in hierarchical classifications (e.g. `Chinese: Total`,
  `Rented: Total`) — include the leaves you want, exclude the rollups, or proportions exceed 100%.

## Layout
`src/lana/` pipeline modules · `tests/` · `data/reference/` tracked crosswalks + ASP-2001 ·
`data/{bronze,silver,gold,warehouse,output}/` generated (gitignored) · `reference/` design docs
(`dataflows.md`, `phidu_methods.md`).

## Don't touch
`_ABS_Data/` and `_CensusData/` are **legacy reference only** (gitignored, own git history) —
read for context, never modify or depend on at runtime.

## Agents
- `add-census-domain` — add a new ABS table to the warehouse (probe → registry → verify).
- `warehouse-verifier` — integrity-check the generated warehouse.

## Ponytail
The repo runs in "ponytail" mode (lazy senior dev): question whether code needs to exist,
prefer stdlib/native, one line over fifty, shortest diff that works. Don't simplify away input
validation, error handling that prevents data loss, or correctness of the data invariants above.
