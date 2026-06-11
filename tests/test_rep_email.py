"""Round-trip tests for the rep-email path: draft -> simulated reply -> parse."""

import pytest

from rebateiq.agents.proposal_generator.rep_email import (
    SIMULATED_REP_RATE_CAD_PER_M3,
    draft_submission_email,
    parse_rep_reply,
    simulate_rep_reply,
)
from rebateiq.agents.proposal_generator.schemas import ContractorProfile
from tests.test_calc import visit

PROGRAM = {
    "program_id": "enbridge-commercial-boiler-rep",
    "program_name": "Enbridge Commercial Boiler Retrofit Incentive (Territory Representative)",
}

CONTRACTOR = ContractorProfile(
    company_name="Hobb Mechanical Ltd.",
    contact_name="Adam Hobb",
    phone="416-555-0147",
    email="adam@hobbmechanical.example",
)


def test_draft_contains_the_rep_form_fields():
    draft = draft_submission_email(visit(), PROGRAM, CONTRACTOR)
    for needle in [
        "Laars Mighty Therm 2", "MT2-9407-1182", "72% AFUE", "21 years",
        "Viessmann Vitodens 100-W B1HE-120", "95% AFUE", "x2",
        "38 Maplewood Crt", "32,000", "Hobb Mechanical Ltd.",
    ]:
        assert needle in draft, f"missing from draft: {needle}"


def test_simulated_reply_round_trips_through_parser():
    v = visit()
    parsed = parse_rep_reply(simulate_rep_reply(v, PROGRAM))
    expected_m3 = 32_000 * (1 - 72 / 95)
    assert parsed["projected_annual_savings_m3"] == pytest.approx(expected_m3, abs=1)
    assert parsed["approved_rebate_cad"] == pytest.approx(
        expected_m3 * SIMULATED_REP_RATE_CAD_PER_M3, abs=2
    )


def test_parser_handles_format_variants():
    text = "the Rebate Amount: $12,345.67 ... projected savings 9,876 m3"
    parsed = parse_rep_reply(text)
    assert parsed["approved_rebate_cad"] == 12345.67
    assert parsed["projected_annual_savings_m3"] == 9876


def test_parser_refuses_incomplete_replies():
    with pytest.raises(ValueError):
        parse_rep_reply("Thanks, we'll get back to you next week.")
