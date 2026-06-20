"""L4 Synthesis — write the analyst-facing multi-sheet Excel workbook.

Uses Polars' built-in `write_excel` (xlsxwriter backend) so we don't hand-roll
cell formatting. One Workbook, several sheets.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import xlsxwriter


def _index_frame(meta: dict[str, str]) -> pl.DataFrame:
    return pl.DataFrame({"Item": list(meta.keys()), "Detail": list(meta.values())})


def _finite(df: pl.DataFrame) -> pl.DataFrame:
    """Replace NaN/Inf in float columns with null — xlsxwriter rejects non-finite values."""
    floats = [c for c, t in df.schema.items() if t in (pl.Float32, pl.Float64)]
    if not floats:
        return df
    return df.with_columns(
        pl.when(pl.col(c).is_finite()).then(pl.col(c)).otherwise(None).alias(c) for c in floats
    )


def write_workbook(path: Path, gold: dict[str, pl.DataFrame], meta: dict[str, str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with xlsxwriter.Workbook(str(path)) as wb:
        _index_frame(meta).write_excel(wb, worksheet="Index", autofit=True, header_format={"bold": True})

        sheets = [
            ("Demographic Baseline", gold["demographic"].select(
                "sa2_code", "sa2_name", "sa3_name", "lga_name",
                "total_pop", "indigenous_pct", "other_language_pct", "year12_pct")),
            ("Socio-Economic", gold["socioeconomic"]),
            ("SEIFA by PHN", gold["seifa_phn"]),
            ("Health-Risk (PHN)", gold["health_phn"]),
            ("Health-Risk (SA2)", gold["health_sa2"]),
            ("Equity-Gap", gold["equity"]),
        ]
        for name, df in sheets:
            _finite(df).write_excel(wb, worksheet=name, autofit=True, header_format={"bold": True})
    return path
