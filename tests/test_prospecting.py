"""Unit tests for the prospect list formatting (pure parts; retrieval is covered live)."""

from rebateiq.agents.prospect_identifier.prospecting import (
    Prospect,
    format_approval_list,
)


def prospect(rank: int, **overrides) -> Prospect:
    base = dict(
        rank=rank,
        listing_id=f"l{rank}",
        business_name=f"Business {rank}",
        building_type="multi-family dwelling",
        contact_name="Pat Doe",
        contact_title="Building Superintendent",
        email="pat@example.com",
        address="1 Main St",
        city="Toronto",
        why_match="Atmospheric boilers, 21 years old; 38 units",
        score=0.03,
    )
    base.update(overrides)
    return Prospect(**base)


def test_approval_list_contains_everything_the_contractor_needs():
    text = format_approval_list(
        [prospect(1), prospect(2, business_name="Second Spot")],
        "Enbridge Commercial Boiler Retrofit Incentive",
        "Ontario",
    )
    for needle in [
        "PROSPECT LIST FOR APPROVAL",
        "2 prospects",
        "1. Business 1 — multi-family dwelling",
        "Pat Doe, Building Superintendent <pat@example.com>",
        "Atmospheric boilers, 21 years old; 38 units",
        "2. Second Spot",
        "unsubscribe",            # CASL defaults are stated up front
        "one follow-up",
        "Approve all",
    ]:
        assert needle in text, f"missing: {needle}"


def test_empty_list_still_renders_header():
    text = format_approval_list([], "Some Program", "Ontario")
    assert "0 prospects" in text
