"""
The Outreach storyline, deterministic (no LLM): approved prospects in,
CASL-validated campaign out, queued to the outbox after the (scripted)
approval. The live-agent version with Gemini writing the copy is
scripts/check_outreach_agent.py.

    python scripts/demo_outreach.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rebateiq.agents.outreach.campaign import (  # noqa: E402
    assemble_campaign,
    format_campaign_preview,
    queue_campaign,
)
from rebateiq.shared.models import ContractorProfile  # noqa: E402

PROGRAM_NAME = "Enbridge Commercial Boiler Retrofit Incentive (Territory Representative)"
OUTBOX = Path(__file__).resolve().parents[1] / "data/output/outbox"

CONTRACTOR = ContractorProfile(
    company_name="Hobb Mechanical Ltd.",
    contact_name="Adam Hobb",
    phone="416-555-0147",
    email="adam@hobbmechanical.example",
)

PROSPECTS = [
    {"listing_id": "maplewood-court-apartments",
     "business_name": "Maplewood Court Apartments",
     "email": "d.petrovic@example.com", "contact_name": "Dragan Petrovic",
     "equipment_hook": "two atmospheric cast-iron boilers from 2004 on a hydronic loop"},
    {"listing_id": "ycc-412-stclair",
     "business_name": "YCC 412 — St. Clair Mid-Rise",
     "email": "treasurer.ycc412@example.com", "contact_name": "Priya Raman",
     "equipment_hook": "a central heating plant original to the 2003 build"},
    {"listing_id": "lakeshore-property-mgmt",
     "business_name": "Lakeshore Property Management",
     "email": "a.whitfield@example.com", "contact_name": "Alana Whitfield",
     "equipment_hook": "a forty-unit complex with its central gas heating plant nearing end of life"},
]

BODY = """Hi {first},

Enbridge has an active incentive for buildings exactly like yours — {hook}.
Their commercial boiler retrofit program pays based on the gas a
high-efficiency replacement saves, and the figures are confirmed by an
Enbridge territory representative before any work begins, so you know the
number up front.

We handle the entire submission with your equipment details. If useful, I'd
be glad to do a no-obligation site assessment and put exact numbers on it —
it takes about an hour and you'll have the incentive picture within a week.

Either way, worth knowing the program exists while funding is open."""


def main() -> None:
    emails = [
        {"listing_id": p["listing_id"],
         "subject": f"An Enbridge incentive that fits {p['business_name'].split(' —')[0]}",
         "body": BODY.format(first=p["contact_name"].split()[0], hook=p["equipment_hook"])}
        for p in PROSPECTS
    ]

    drafts, problems = assemble_campaign(PROSPECTS, emails, CONTRACTOR)
    assert not problems, f"compliance problems: {problems}"

    print(format_campaign_preview(drafts, PROGRAM_NAME))
    print("=" * 78)
    print("[contractor reviews the preview above and approves]")
    print("=" * 78)

    paths = queue_campaign(drafts, str(OUTBOX))
    print(f"\nQueued {len(paths)} messages to the outbox (simulated send):")
    for p in paths:
        print(f"  {p}")
    print("\nProduction swap: SendGrid sender-auth + live unsubscribe + suppression list.")


if __name__ == "__main__":
    main()
