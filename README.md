# LANA — Local & Regional Area Needs Assessment

Extracts, processes and synthesises ABS Census + SEIFA data into a regional
needs-assessment workbook, scoped to Primary Health Networks (PHNs). SA2 is the
atomic grain; everything coarser (SA3/LGA/PHN) is an aggregation.

See the architecture plan for the full design. Pipeline layers: bronze (raw
extract) → silver (tidy) → gold (geo spine + age-standardised rates + SEIFA) →
synthesis (Excel + Parquet).

## Run

```powershell
uv sync
uv run lana --phn "Western Queensland"
uv run pytest
```

Output: `data/output/<phn>_needs_assessment.xlsx` + gold Parquet.
