"""Generic fact builder: marginalise-by-Total, leaf selection, proportions."""

import polars as pl

from lana.facts import build_fact
from lana.registry import DomainSpec


def _frame():
    # category 'cat' x sex 'sexp', with a Total in EACH dimension (as ABS tables have).
    rows = []
    for sex, mult in [("Persons", 1.0), ("Males", 0.5)]:
        for cat, val in [("A", 30), ("B", 70), ("Total", 100)]:
            rows.append(
                {
                    "sa2_code": "999",
                    "year": 2021,
                    "sexp_label": sex,
                    "cat_label": cat,
                    "value": val * mult,
                }
            )
    return pl.DataFrame(rows)


def test_marginalises_to_persons_and_excludes_total():
    spec = DomainSpec("x", "F", "cat", "d", exclude_labels=("Total",), denominator_label="Total")
    out = build_fact(_frame(), spec)
    # Males rows ignored (filtered to Persons); Total excluded as a category.
    assert set(out["category"].to_list()) == {"A", "B"}
    rec = {r["category"]: r for r in out.to_dicts()}
    assert (
        rec["A"]["count"] == 30
        and rec["A"]["denominator"] == 100
        and rec["A"]["proportion"] == 30.0
    )
    assert rec["B"]["proportion"] == 70.0


def test_include_labels_and_zero_denominator_null():
    df = pl.DataFrame(
        {
            "sa2_code": ["0", "0", "0"],
            "year": [2021, 2021, 2021],
            "cat_label": ["Leaf1", "Leaf2", "Total"],
            "value": [0.0, 0.0, 0.0],
        }
    )
    spec = DomainSpec(
        "x", "F", "cat", "d", include_labels=("Leaf1", "Leaf2"), denominator_label="Total"
    )
    out = build_fact(df, spec)
    assert set(out["category"].to_list()) == {"Leaf1", "Leaf2"}
    assert out["proportion"].to_list() == [None, None]  # zero denom -> null, never NaN
