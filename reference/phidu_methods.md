# PHIDU methods — reference for replication (NOT a live data source)

PHIDU (Torrens University *Social Health Atlas of Australia*) is being
decommissioned and is not a sustainable dependency. We do **not** ingest its
Excel workbooks into the pipeline. This file records the **methods** to
replicate ourselves, and how PHIDU values can serve as an offline sanity check.
Offline PHIDU files (supplied by the user) go in `data/reference/phidu/` if needed.

## 1. Direct age-standardisation — IMPLEMENTED

Already replicated in `src/lana/standardize.py`. Method (per AIHW/ABS):

1. age-specific rate `r_g = numerator_g / denominator_g`
2. expected cases `e_g = r_g × std_pop_g`
3. `ASR = (Σ e_g / Σ std_pop_g) × per` (per = 100,000)

Standard population: ABS "Standard Population for use in Age-Standardisation"
(2001 ERP, total **19,413,240**), stored single-year-of-age in
`data/reference/asp_2001_single_year.csv` and summed to the data's own age bands
at runtime. PHIDU uses the same 2001 standard, so its published age-standardised
rates are directly comparable as a validation oracle.

**Still to add (Phase 3):** 95% confidence intervals / relative standard error,
and small-area reliability flags (suppress rates on unstable denominators —
PHIDU suppresses small numbers; ABS already perturbs small counts).

## 2. Small-area estimation / forecasting — TO REPLICATE (later phase)

The user specifically wants PHIDU's forecasting approach captured. Document here
once the offline workbooks/method notes are available. Expected components:
- modelled estimates for indicators not directly measured at small-area level
  (e.g. survey-based prevalence pushed down to PHA/SA2 via synthetic estimation);
- population projections used as denominators for forward-looking rates.
Action: extract the exact technique from PHIDU's metadata sheets and reproduce
with ABS ERP projections + Census correlates. **Placeholder until files provided.**

## 3. Benchmark indicators (definitions to reproduce from ABS/AIHW sources)

PHIDU headline measures we will compute ourselves (not from Census alone — these
need administrative/mortality data, a later phase):
- **Premature mortality** — deaths under age 75, age-standardised (needs ABS deaths data).
- **Potentially preventable hospitalisations (PPH)** — age-standardised admissions for
  ambulatory-care-sensitive conditions (needs hospital admin data, e.g. via state health).
- **Chronic disease prevalence** — our Census G19 long-term-condition rates are the
  closest open analogue; PHIDU's modelled prevalence can validate magnitude.

## 4. Validation use

For a matching indicator and geography, compare our ABS-derived age-standardised
rate to the PHIDU published rate; flag deviations beyond tolerance. This is a
manual offline check, not an automated join.
