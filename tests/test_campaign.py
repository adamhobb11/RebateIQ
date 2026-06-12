"""Unit tests for the CASL-enforcing campaign assembly."""

from rebateiq.agents.outreach.campaign import (
    EmailDraft,
    assemble_campaign,
    compliance_footer,
    format_campaign_preview,
    queue_campaign,
    validate_draft,
)
from rebateiq.shared.models import ContractorProfile

CONTRACTOR = ContractorProfile(
    company_name="Hobb Mechanical Ltd.",
    contact_name="Adam Hobb",
    phone="416-555-0147",
    email="adam@hobbmechanical.example",
)

PROSPECT = {
    "listing_id": "maplewood-court-apartments",
    "business_name": "Maplewood Court Apartments",
    "email": "d.petrovic@example.com",
}

GOOD_BODY = (
    "Hello Dragan,\n\nEnbridge has opened a commercial boiler retrofit incentive "
    "that fits buildings like Maplewood Court — older cast-iron boiler plants on "
    "hydronic loops are exactly what the program pays to replace. Based on your "
    "building's profile, the incentive is calculated from the gas your new "
    "high-efficiency plant saves.\n\nWe'd be glad to do a no-obligation site "
    "assessment and put exact numbers on it for you."
)


def draft(**overrides) -> EmailDraft:
    base = dict(
        listing_id=PROSPECT["listing_id"],
        business_name=PROSPECT["business_name"],
        to_email=PROSPECT["email"],
        subject="A new Enbridge incentive for your boiler plant",
        body=GOOD_BODY,
        footer=compliance_footer(CONTRACTOR),
    )
    base.update(overrides)
    return EmailDraft(**base)


def test_compliant_draft_passes():
    assert validate_draft(draft(), CONTRACTOR) == []


def test_missing_unsubscribe_fails():
    issues = validate_draft(draft(footer="-- \nAdam Hobb — Hobb Mechanical Ltd.\n416-555-0147"),
                            CONTRACTOR)
    assert any("unsubscribe" in i for i in issues)


def test_missing_identification_fails():
    bad_footer = "To opt out, reply STOP or use the unsubscribe link: [x]"
    issues = validate_draft(draft(footer=bad_footer), CONTRACTOR)
    assert any("company name" in i for i in issues)


def test_shouting_subject_and_thin_body_fail():
    issues = validate_draft(
        draft(subject="HUGE REBATES NOW!!!!", body="Click here."), CONTRACTOR
    )
    assert any("all caps" in i for i in issues)
    assert any("body length" in i for i in issues)


def test_assemble_validates_and_flags():
    drafts, problems = assemble_campaign(
        [PROSPECT],
        [{"listing_id": "maplewood-court-apartments",
          "subject": "A new Enbridge incentive for your boiler plant",
          "body": GOOD_BODY},
         {"listing_id": "ghost", "subject": "x", "body": "y"}],
        CONTRACTOR,
    )
    assert len(drafts) == 1
    assert problems == {"ghost": ["no matching prospect record"]}
    preview = format_campaign_preview(drafts, "Enbridge Commercial Boiler Retrofit")
    assert "CAMPAIGN FOR APPROVAL" in preview
    assert "Nothing sends until you approve." in preview
    assert "unsubscribe" in preview.lower()


def test_queue_writes_outbox(tmp_path):
    paths = queue_campaign([draft()], str(tmp_path))
    assert len(paths) == 1
    text = (tmp_path / "maplewood-court-apartments.txt").read_text()
    assert "Subject: A new Enbridge incentive" in text
    assert "unsubscribe" in text.lower()
