"""Source attribution & compliance text (CC BY 4.0) — single source of truth.

LANA is a derivative work built on open government data. The ABS and the
Department of Health release under CC BY 4.0, which obliges us to attribute each
source, indicate the data has been modified, and not imply endorsement. These
strings are embedded into every distributed output (warehouse `ATTRIBUTION.txt`,
`schema.md`, the Excel Index sheet) and rendered into the repo's `ATTRIBUTION.md`
so no copy drifts. Australian English throughout.
"""

from __future__ import annotations

# (publisher, title/product, reference)
SOURCES: list[tuple[str, str, str]] = [
    (
        "Australian Bureau of Statistics",
        "Census of Population and Housing, 2021 — General Community Profile & Time Series Profile",
        "DataPacks released 12 October 2022",
    ),
    (
        "Australian Bureau of Statistics",
        "Census of Population and Housing: Socio-Economic Indexes for Areas (SEIFA), Australia, 2021",
        "cat. no. 2033.0.55.001, released 27 April 2023",
    ),
    (
        "Australian Bureau of Statistics",
        "Standard Population for use in Age-Standardisation (2001 estimated resident population)",
        "from National, state and territory population, cat. no. 3101.0",
    ),
    (
        "Australian Bureau of Statistics",
        "Australian Statistical Geography Standard (ASGS) Edition 3, 2021 — SA2/SA3/SA4/LGA correspondences",
        "released July 2021",
    ),
    (
        "Australian Government Department of Health, Disability and Ageing",
        "Primary Health Networks (PHN) (2023) – Statistical Area Level 2 (2021) concordance",
        "published at health.gov.au",
    ),
]

CC_BY_URL = "https://creativecommons.org/licenses/by/4.0/"

ATTRIBUTION = (
    "This product uses the following source data, each licensed under Creative Commons "
    "Attribution 4.0 International (CC BY 4.0):\n"
    + "\n".join(f"  - {pub}, {title} ({ref})." for pub, title, ref in SOURCES)
)

DISCLAIMER = (
    "This product includes data that has been transformed, aggregated, age-standardised and "
    "otherwise derived by the LANA project. These derived results are the work of LANA and are "
    "NOT endorsed by, affiliated with, or guaranteed by the Australian Bureau of Statistics or "
    "the Australian Government Department of Health, Disability and Ageing. Any errors introduced "
    "by transformation are LANA's own."
)


def attribution_text() -> str:
    """Plain-text notice for embedding alongside distributed data."""
    return f"{ATTRIBUTION}\n\n{DISCLAIMER}\n"


def render_markdown() -> str:
    """Body of ATTRIBUTION.md, generated from SOURCES so the docs can't drift."""
    rows = "\n".join(f"| {pub} | {title} | {ref} | CC BY 4.0 |" for pub, title, ref in SOURCES)
    return (
        "<!-- Generated from src/lana/attribution.py — run `uv run python -m lana.attribution > ATTRIBUTION.md` -->\n"
        "# Attribution & data sources\n\n"
        "LANA is a derivative work built on open government data. Each source below is used under "
        f"[CC BY 4.0]({CC_BY_URL}). The LANA code and its outputs are also released under CC BY 4.0 "
        "(see `LICENSE`).\n\n"
        "## Sources\n\n"
        "| Publisher | Title / product | Reference | Licence |\n"
        "|---|---|---|---|\n"
        f"{rows}\n\n"
        "## Attribution statement\n\n"
        f"{ATTRIBUTION}\n\n"
        "## Modifications & non-endorsement\n\n"
        f"{DISCLAIMER}\n\n"
        "## Where this notice appears\n\n"
        "Distributed outputs carry an embedded copy: the warehouse writes "
        "`data/warehouse/ATTRIBUTION.txt` and documents it in `schema.md`; the per-PHN Excel "
        "workbook states it on the Index sheet.\n"
    )


if __name__ == "__main__":
    print(render_markdown())
