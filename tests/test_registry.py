"""Registry integrity — structural checks that don't hit the network."""

from lana.registry import REGISTRY


def test_specs_well_formed():
    names = [s.name for s in REGISTRY]
    assert len(names) == len(set(names)), "duplicate fact names"
    for s in REGISTRY:
        assert s.dataflow.startswith("C21_")
        assert s.category_dim and s.category_dim.islower()
        # exactly one selection strategy is meaningful
        assert (s.include_labels is not None) or (s.exclude_labels != ())
        # a declared denominator label must not also be a kept category
        if s.denominator_label and s.include_labels:
            assert s.denominator_label not in s.include_labels
