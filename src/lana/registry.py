"""Source registry — declares each categorical gold fact and how to derive it.

Category leaf-lists and denominators were confirmed by probing the live DSDs.
These ABS cross-tabs carry a *Total in every dimension*, so the fact builder
marginalises other dimensions by filtering them to their Total/Persons row
(never summing), and excludes nested sub-totals from the category itself.

Population, health, SEIFA and medians have bespoke shapes and are built directly
in `warehouse.py`, not from this registry.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainSpec:
    name: str  # gold table name -> fact_<name>
    dataflow: str
    category_dim: str  # dimension token kept as `category`
    description: str
    timeseries: bool = False  # True -> pull 2011..2021 (T-tables)
    include_labels: tuple[str, ...] | None = None  # explicit leaves (hierarchical dims)
    exclude_labels: tuple[str, ...] = ()  # category values to drop (flat dims)
    denominator_label: str | None = None  # category value used as the denominator


REGISTRY: list[DomainSpec] = [
    DomainSpec(
        "country_of_birth",
        "C21_T08_SA2",
        "bplp",
        "Country of birth of person (top countries), % of persons.",
        timeseries=True,
        exclude_labels=("Total",),
        denominator_label="Total",
    ),
    DomainSpec(
        "language",
        "C21_T10_SA2",
        "lanp",
        "Language used at home (incl. 'Uses English only'), % of persons. "
        "Filter out 'Uses English only' for the non-English view.",
        timeseries=True,
        # 'Chinese: Total' is a nested subtotal of Cantonese/Mandarin/Other — exclude to avoid double count.
        exclude_labels=("Total", "Chinese: Total"),
        denominator_label="Total",
    ),
    DomainSpec(
        "education_institution",
        "C21_T13_SA2",
        "tystap",
        "Type of educational institution attending, % of persons attending.",
        timeseries=True,
        denominator_label="Total",
        include_labels=(
            "Preschool",
            "Primary - Total",
            "Secondary - Total",
            "University or other higher education - Total",
            "Vocational education (including TAFE and private training providers) - Total",
            "Other - Total",
            "Type of educational institution not stated",
        ),
    ),
    DomainSpec(
        "labour_force",
        "C21_T33_SA2",
        "lfsp",
        "Labour force status (persons 15+), % of persons 15+.",
        timeseries=True,
        denominator_label="Total",
        include_labels=(
            "Employed, worked full-time",
            "Employed, worked part-time",
            "Employed, away from work",
            "Employed, hours of work not stated",
            "Unemployed, looking for full-time work",
            "Unemployed, looking for part-time work",
            "Not in the labour force",
            "Labour force status not stated",
        ),
    ),
    DomainSpec(
        "income_personal",
        "C21_G17_SA2",
        "incp",
        "Total personal income (weekly) brackets, % of persons 15+.",
        exclude_labels=("Total",),
        denominator_label="Total",
    ),
    DomainSpec(
        "family_composition",
        "C21_T14_SA2",
        "hhcfmcd",
        "Family composition (within family households), % of family households.",
        timeseries=True,
        denominator_label="Family Household: Total",
        include_labels=(
            "Family household: Couple family with children",
            "Family household: Couple family with no children",
            "Family household: One parent family",
            "Family household: Other family",
        ),
    ),
    DomainSpec(
        "household_composition",
        "C21_T14_SA2",
        "hhcfmcd",
        "Household composition, % of households.",
        timeseries=True,
        denominator_label="Total",
        include_labels=(
            "Family Household: Total",
            "Group household",
            "Lone person household",
            "Other households",
        ),
    ),
    DomainSpec(
        "tenure",
        "C21_T18_SA2",
        "tenlld",
        "Tenure and landlord type, % of occupied dwellings.",
        timeseries=True,
        denominator_label="Total",
        include_labels=(
            "Owned outright",
            "Owned with a mortgage",
            "Rented: Total",
            "Other tenure type",
            "Tenure type not stated",
        ),
    ),
]
