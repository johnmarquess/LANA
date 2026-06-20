"""Attribution & compliance text — structural checks (no network)."""

from lana.attribution import ATTRIBUTION, DISCLAIMER, SOURCES, attribution_text, render_markdown


def test_every_data_family_is_attributed():
    blob = " ".join(t for _, t, _ in SOURCES)
    for needle in ["Census", "SEIFA", "Standard Population", "ASGS"]:
        assert needle in blob, f"missing source: {needle}"
    # the PHN concordance is Dept of Health, not ABS — attributed separately
    assert any("Department of Health" in pub for pub, _, _ in SOURCES)
    assert any("Bureau of Statistics" in pub for pub, _, _ in SOURCES)


def test_attribution_statement_and_disclaimer():
    assert "CC BY 4.0" in ATTRIBUTION
    assert "2033.0.55.001" in ATTRIBUTION  # SEIFA catalogue number
    assert "NOT endorsed" in DISCLAIMER
    assert "Australian Bureau of Statistics" in DISCLAIMER
    # the embedded notice carries both
    text = attribution_text()
    assert ATTRIBUTION in text and DISCLAIMER in text


def test_markdown_renders_all_sources():
    md = render_markdown()
    assert md.count("| CC BY 4.0 |") == len(SOURCES)
