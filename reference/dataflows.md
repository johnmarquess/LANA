# ABS dataflows & dimensions (confirmed against the live API)

API: `https://data.api.abs.gov.au/rest` — SDMX REST, **open (no auth/key)**.
All values verified by probing the API on 2026-06-20.

> **Attribution.** Source titles, catalogue numbers (e.g. SEIFA cat. 2033.0.55.001) and the
> required CC BY 4.0 attribution/disclaimer live in [`../ATTRIBUTION.md`](../ATTRIBUTION.md).
> The PHN concordance is published by the Dept of Health, not the ABS.

## Census 2021 General Community Profile (GCP)

Full table set `C21_G01_SA2` … `C21_G62_SA2` is published at SA2. Pull at SA2,
roll up via the geography spine. Request with
`Accept: application/vnd.sdmx.data+csv;labels=both` → columns are `"CODE: Label"`.

### C21_G01_SA2 — Selected Person Characteristics
- Dimensions (order): `SEXP, PCHAR, REGION, REGION_TYPE, STATE` (+ TIME_PERIOD). Geo dim = **REGION**.
- `SEXP`: 1=Males, 2=Females, **3=Persons**.
- `PCHAR` (selected person characteristic) is a grab-bag. Useful labels:
  - `Age groups: 0-4 years` … `85 years and over` → age structure / total population (sum, sexp=3).
  - `Aboriginal and/or Torres Strait Islander persons: Total` → Indigenous count.
  - `Language used at home: Other language` → CALD proxy.
  - `Highest year of school completed: Year 12 or equivalent` → education.

### C21_G19_SA2 — Type of Long-Term Health Condition
- Dimensions: `SEXP, LTHP, AGEP, REGION, REGION_TYPE, STATE`. Geo dim = **REGION**.
- `LTHP`: named conditions + `Total (Persons)` (population denominator),
  `No long-term health condition(s)`, `Not stated`, `Any other long-term health condition(s)`.
- `AGEP` labels: `0-14 years, 15-24, 25-34, 35-44, 45-54, 55-64, 65-74, 75-84, 85 years and over`, `Total`.
- Prevalence = condition count / `Total (Persons)`, by age, sexp=3. Self-consistent denominator.

## SEIFA 2021

- `ABS_SEIFA2021_SA2`, `ABS_SEIFA2021_LGA`, `ABS_SEIFA2021_SA1` (also 2016/2011 vintages).
- Dimensions: `ASGS_2021, SEIFAINDEXTYPE, SEIFA_MEASURE`. Geo dim = **ASGS_2021** (SA2 code).
- `SEIFAINDEXTYPE`: `IRSD` (disadvantage), `IRSAD` (adv+disadv), `IER` (economic resources), `IEO` (education & occupation).
- `SEIFA_MEASURE`: `SCORE`, `RWAD` (rank Australia decile), `RWSD` (rank state decile),
  `RWAR/RWSR` (ranks), `RWAP/RWSP` (percentiles), `URP` (usual resident population), `MINS/MAXS`.
- **Caveat:** scores/deciles are SA1/SA2-relative and **must not be averaged** to PHN. Summarise the
  SA2 distribution (population-weighted median decile, share in bottom deciles) instead.

## Geography crosswalks (in `data/reference/`)

- `geo_correspondence_2021.csv`: SA2 → SA3 → SA4 → LGA (ASGS 2021). SA3 = SA2[:5], SA4 = SA2[:3].
- `phn_2023_to_SA2_2021.csv`: SA2 → PHN (2023). QLD only (7 PHNs, 553 SA2s). Western Queensland = 12 SA2s.

## Extraction notes

- Data key is dot-separated by dimension order; SA2 codes OR'd (`+`) in the geo slot, wildcards elsewhere.
- Batch SA2s (`sa2_batch_size`, default 50) and cache bronze Parquet — the API times out on large pulls.
- Structure (DSD) responses are cached to `data/reference/_structure_cache/`.

## Phase 2 candidates (same generic normaliser)

`C21_G07` (Indigenous by age), `C21_G09`/`C21_G13` (CALD: birthplace / language),
`C21_G17` (income), `C21_G18` (need for assistance), `C21_G43`/`C21_G46` (education),
labour-force tables (confirm titles via the DSD at runtime).
