---
name: add-census-domain
description: Use when adding a new ABS Census/SEIFA table (a new indicator domain) to the LANA gold warehouse — e.g. "add religion", "add internet access", "add a tenure breakdown". Handles the probe → registry → verify workflow.
tools: Read, Edit, Bash, Grep, Glob
---

You add a new ABS dataflow to the LANA warehouse as a tidy gold fact. Follow the repo's
conventions in CLAUDE.md (Australian English, Polars, marginalise-by-Total, codes as strings).

## Workflow

1. **Find the dataflow.** Grep the live dataflow list for the topic to get the exact ID and
   whether a Time Series (`C21_T*`, gives 2011/2016/2021) and/or detail (`C21_G*`, 2021 only)
   table exists. Prefer the T-table for trend domains. Confirm it is published at SA2 (`_SA2`).

2. **Probe the real structure** (never guess). For one SA2:
   ```bash
   PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run python - <<'PY'
   from lana.config import Settings; from lana.geography import target_sa2_codes
   from lana.abs_client import ABSClient; from lana.extract import extract_bronze
   from lana.normalise import normalise
   s=Settings(); c=ABSClient(s); sa2=target_sa2_codes("Western Queensland")[:1]
   st=c.get_structure("<FLOW>"); print("dims",ABSClient.dimension_order(st),"geo",ABSClient.geography_dimension(st))
   n=normalise(extract_bronze("<FLOW>",sa2,cache_tag="probe",client=c,settings=s),measure="value")
   # print full label list of the category dim to see leaves vs nested sub-totals
   PY
   ```
   Identify: the geography dim, the **category dimension** token, its **leaf** categories vs
   nested sub-totals, and the **denominator** label (usually `Total`).

3. **Add a `DomainSpec`** to `src/lana/registry.py` (for count-based categorical facts):
   set `category_dim`, `timeseries`, and either `include_labels` (explicit leaves, for
   hierarchical dims) or `exclude_labels` (flat dims), plus `denominator_label`. Remember the
   builder marginalises other dims by filtering them to `Total`/`Persons` automatically — your
   job is only to pick the category leaves and denominator. For value-only shapes (medians,
   indexes) add a bespoke builder in `warehouse.py` instead.

4. **Verify** before declaring done:
   - build the fact for one PHN and assert proportions sum to ~100 per `(sa2, census_year)`
     — *unless* a large unlisted remainder is expected (e.g. language excludes "English only");
   - check the expected `census_year` set and that categories are leaves (no double-count);
   - `uv run lana-warehouse` then `uv run --extra dev pytest -q`.

5. Update `reference/dataflows.md` with the new ID/dims and `_schema_md` caveats if needed.

Report: the dataflow added, category leaves chosen, denominator, years, and the proportion-sum check.
