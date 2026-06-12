"""
RebateIQ — Outreach agent.

The marketing campaign the contractor never had time to run. The LLM writes
the body copy — translating the program's value into each building's
situation, in the contractor's voice. The tools own the CASL envelope:
identification + unsubscribe are appended and validated in code, and the
queue tool is only called after the contractor explicitly approves.
"""

import os

from dotenv import find_dotenv, load_dotenv
from google.adk.agents import Agent

from rebateiq.shared.es import PROGRAMS_INDEX, get_client
from rebateiq.shared.models import ContractorProfile

from .campaign import (
    assemble_campaign,
    format_campaign_preview,
    queue_campaign,
)

load_dotenv(find_dotenv())

MODEL = os.environ.get("REBATEIQ_MODEL", "gemini-3.5-flash")
DEFAULT_OUTBOX = "data/output/outbox"


def get_program(program_id: str) -> dict:
    """Fetch the incentive program the campaign announces, for grounding the
    copy in its real terms (never promise amounts the program doesn't state).

    Args:
        program_id: the program's id.
    """
    es = get_client()
    doc = es.get(index=PROGRAMS_INDEX, id=program_id, source_excludes=["semantic_combined"])
    return doc["_source"]


def make_campaign(
    prospects: list[dict],
    emails: list[dict],
    contractor: dict,
    program_name: str,
) -> dict:
    """Assemble the campaign: your per-prospect copy + the code-appended CASL
    footer, validated deterministically. Returns the full preview for the
    contractor and any compliance problems you must fix before approval.

    Args:
        prospects: approved prospect dicts (listing_id, business_name, email).
        emails: your drafts, one per prospect: {listing_id, subject, body}.
            Do NOT write unsubscribe or signature lines — the footer is appended.
        contractor: ContractorProfile fields (company_name, contact_name,
            phone, email).
        program_name: the incentive program the campaign announces.
    """
    drafts, problems = assemble_campaign(prospects, emails, ContractorProfile(**contractor))
    return {
        "preview": format_campaign_preview(drafts, program_name),
        "problems": problems,
        "ready": not problems,
    }


def queue_approved_campaign(
    prospects: list[dict],
    emails: list[dict],
    contractor: dict,
    outbox_dir: str = DEFAULT_OUTBOX,
) -> dict:
    """Queue the approved campaign for sending (demo: writes the outbox files;
    production: SendGrid with live unsubscribe + suppression). Call ONLY after
    the contractor has explicitly approved the previewed campaign.

    Args:
        prospects: the approved prospect dicts.
        emails: the approved drafts {listing_id, subject, body} — unchanged
            from the approved preview.
        contractor: ContractorProfile fields.
        outbox_dir: where the simulated send lands.
    """
    profile = ContractorProfile(**contractor)
    drafts, problems = assemble_campaign(prospects, emails, profile)
    if problems:
        return {"queued": [], "blocked_by": problems}
    return {"queued": queue_campaign(drafts, outbox_dir), "blocked_by": {}}


root_agent = Agent(
    model=MODEL,
    name="outreach",
    description="Drafts and queues the CASL-compliant incentive announcement campaign.",
    instruction=(
        "You are the RebateIQ Outreach agent, writing in the contractor's voice for "
        "fellow building operators — plain, warm, specific, zero hype.\n"
        "Workflow: 1) get_program for the campaign's program. 2) Write one email per "
        "approved prospect: subject under 60 chars; 3 short paragraphs max; open with "
        "the prospect's actual building/equipment situation; explain why this program "
        "fits it; close with a no-obligation site assessment offer. Mention amounts "
        "only if the program record states them. Never write unsubscribe or signature "
        "lines — the compliance footer is appended in code. 3) make_campaign and show "
        "the full preview. 4) Fix anything in `problems` and re-run until ready. "
        "5) STOP and ask for approval. Call queue_approved_campaign ONLY after the "
        "contractor explicitly approves — never in the same turn you show the preview."
    ),
    tools=[get_program, make_campaign, queue_approved_campaign],
)
