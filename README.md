# LANA — Local & Regional Area Needs Assessment

LANA programmatically extracts, processes and synthesises Australian Bureau of Statistics (ABS)
Census and socio-economic data into an analysis-ready dataset for **regional health and social
needs assessment** — identifying service gaps, population health needs and health inequities.

It builds a **normalised "gold" data warehouse** (flat CSV + Parquet files) keyed on
Statistical Area Level 2 (SA2) and Primary Health Network (PHN), ready to load into a database,
plus an optional per-PHN Excel needs-assessment workbook.

> Scope today: **Queensland** (7 PHNs, ~546 SA2s), census years **2011 / 2016 / 2021**.
> The design is geography-agnostic; national coverage needs a national PHN→SA2 crosswalk.

---

## What it produces

A set of tidy, normalised tables in `data/warehouse/` (each as `.csv` and `.parquet`):

| Table | Years | ABS source | Grain |
|---|---|---|---|
| `dim_geography` | — | crosswalks | one row per SA2 → SA3/SA4/LGA + primary PHN |
| `bridge_sa2_phn` | — | crosswalk | many-to-many SA2 ↔ PHN (authoritative for PHN joins) |
| `fact_population` | 2021 | G01 | sa2 × sex × age group |
| `fact_country_of_birth` | 2011/16/21 | T08 | sa2 × year × country |
| `fact_language` | 2011/16/21 | T10 | sa2 × year × language (incl. "Uses English only") |
| `fact_education_institution` | 2011/16/21 | T13 | sa2 × year × institution type |
| `fact_labour_force` | 2011/16/21 | T33 | sa2 × year × labour force status |
| `fact_income_personal` | 2021 | G17 | sa2 × weekly income bracket |
| `fact_income_medians` | 2021 | G02 | sa2 × median measure (value only) |
| `fact_family_composition` | 2011/16/21 | T14 | sa2 × year × family type |
| `fact_household_composition` | 2011/16/21 | T14 | sa2 × year × household type |
| `fact_tenure` | 2011/16/21 | T18 | sa2 × year × tenure & landlord type |
| `fact_health_conditions` | 2021 | G19 | sa2 × condition, with age-standardised rate |
| `fact_seifa` | 2021 | SEIFA 2021 | sa2 × index × measure (score/decile) |

Categorical facts carry `count`, `denominator` and `proportion`. Every fact joins to
`dim_geography` on `sa2_code`; join to `bridge_sa2_phn` for PHN aggregation. A generated
`data/warehouse/schema.md` documents every column and the caveats.

---

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python package/-project manager)
- Python ≥ 3.13 (uv will fetch it if needed)
- Internet access to the ABS Data API (open, no key required)

## Install

```bash
git clone https://github.com/johnmarquess/LANA.git
cd LANA
uv sync                 # creates .venv and installs dependencies
```

## Usage

### Build the warehouse (primary output)
```bash
uv run lana-warehouse            # extracts all QLD SA2s, writes data/warehouse/
uv run lana-warehouse --refresh  # ignore the bronze cache and re-fetch from the API
```
The first run pulls ~13 dataflows in SA2 batches (a few minutes) and caches raw responses under
`data/bronze/`; subsequent runs reprocess from cache in seconds. Outputs land in
`data/warehouse/` as CSV + Parquet, with `schema.md`.

### Optional: per-PHN Excel workbook
```bash
uv run lana --phn "Western Queensland"   # -> data/output/<phn>_needs_assessment.xlsx
```
Sheets: Index, Demographic Baseline, Socio-Economic, SEIFA by PHN, Health-Risk (PHN & SA2),
Equity-Gap. Valid PHN names: Brisbane North, Brisbane South, Central Queensland Wide Bay Sunshine
Coast, Darling Downs and West Moreton, Gold Coast, Northern Queensland, Western Queensland.

### Tests
```bash
uv run --extra dev pytest -q
```

### Loading into a database
The flat files are long/tidy and load directly. Example (DuckDB):
```sql
CREATE TABLE dim_geography  AS SELECT * FROM 'data/warehouse/dim_geography.parquet';
CREATE TABLE bridge_sa2_phn AS SELECT * FROM 'data/warehouse/bridge_sa2_phn.parquet';
CREATE TABLE fact_labour_force AS SELECT * FROM 'data/warehouse/fact_labour_force.parquet';

-- Unemployment trend by PHN (join via the bridge, not dim_geography.phn_name):
SELECT b.phn_name, f.census_year,
       SUM(f.count) FILTER (WHERE f.category LIKE 'Unemployed%') AS unemployed,
       SUM(f.count)                                             AS persons_15plus
FROM fact_labour_force f
JOIN bridge_sa2_phn b USING (sa2_code)
GROUP BY 1, 2 ORDER BY 1, 2;
```

---

## How it works (pipeline)

A four-layer medallion pipeline, all [Polars](https://pola.rs):

```
ABS SDMX API ─► bronze (raw, cached) ─► silver (tidy long facts) ─► gold (facts + geography spine
                                                                     + age-standardised rates) ─► warehouse / workbook
```

Key modules in `src/lana/`: `abs_client` (SDMX REST), `extract` (bronze), `normalise` (silver),
`geography` (SA2→SA3/SA4/LGA/PHN spine + bridge), `registry` (per-domain specs), `facts` (generic
gold builder), `standardise` (direct age-standardisation), `warehouse`/`workbook` (outputs).

## Methodology notes

- **Longitudinal on consistent boundaries.** SA2 boundaries changed between 2016 and 2021, so
  2011/2016 data is drawn from ABS **Time Series tables** published on **2021 (ASGS 2021)
  boundaries** — no boundary apportionment error. (There are no `C16_*` SA2 dataflows on the API.)
- **Age-standardisation.** `fact_health_conditions.asr` is a **direct age-standardised rate per
  100,000** against the ABS *Australian Standard Population 2001* (total 19,413,240), stored at
  single year of age in `data/reference/asp_2001_single_year.csv` and re-banded at runtime.
- **PHN is many-to-many.** A few SA2s straddle two PHN boundaries; use `bridge_sa2_phn` for
  correct PHN totals. `dim_geography.phn_name` is only a convenience *primary* assignment.
- **Small areas.** ABS perturbs small counts; proportions on tiny denominators are noisy, so the
  `denominator` is always carried and zero-population areas yield `null` (never `NaN`).
- **SEIFA at PHN.** SEIFA deciles are not averaged; aggregate the SA2 distribution instead.

## Configuration

Override any setting via env vars prefixed `LANA_` or a `.env` file (see `src/lana/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `LANA_TARGET_PHN` | `Western Queensland` | default PHN for the workbook |
| `LANA_CENSUS_PERIOD_START` / `_END` | `2011` / `2021` | time-series year range |
| `LANA_SA2_BATCH_SIZE` | `50` | SA2s per API request |
| `LANA_FILE_FORMATS` | `csv,parquet` | warehouse output formats |

## Project layout

```
src/lana/          pipeline modules
tests/             pytest suite
data/reference/    tracked crosswalks (SA2↔SA3/SA4/LGA, PHN) + ASP-2001
data/{bronze,silver,gold,warehouse,output}/  generated (gitignored)
reference/         design docs (dataflows.md, phidu_methods.md)
CLAUDE.md          contributor guide / coding standards
```

## Contributing

Standards live in [`CLAUDE.md`](CLAUDE.md): Polars only (no pandas), `uv` for everything,
**Australian English** across code and docs, and the data invariants that keep results correct
(SA2 grain, codes as strings, read dimensions from the DSD, marginalise cross-tabs by filtering
to `Total` not summing, guard zero denominators).

## Licence

This repository is licensed under the
[Creative Commons Attribution 4.0 International licence (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
— see [`LICENSE`](LICENSE). You may share and adapt the work, including commercially, provided you
give appropriate credit.

> © 2026 John Marquess. When reusing, attribute as: *"LANA by John Marquess, licensed under CC BY 4.0."*

## Data source & attribution

Built on data from the **Australian Bureau of Statistics**, used under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). SEIFA and Census data © Commonwealth of
Australia (ABS). This project is an independent tool and is not endorsed by the ABS.
