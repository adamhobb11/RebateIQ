"""
RebateIQ — Proposal Generator agent.

The demo hero: site-visit data in, branded PDF proposal out. The agent
orchestrates typed tools; every dollar figure comes from the deterministic
calc engine — the LLM reasons about eligibility and workflow, never invents
numbers.

Tool flow:
  match_incentive_programs -> (eligibility reasoning happens in the model)
  -> draft_rep_submission_email / get_simulated_rep_reply / parse_rep_reply_email
     (only for email-channel custom programs)
  -> calculate_proposal -> render_proposal_pdf_file
"""

import os
from typing import Optional

from dotenv import find_dotenv, load_dotenv
from google.adk.agents import Agent

from rebateiq.shared.es import get_client

from . import rep_email as rep
from .calc import build_proposal_calc
from .matching import match_programs as _match
from .pdf import render_proposal_pdf
from .schemas import ContractorProfile, SiteVisit

load_dotenv(find_dotenv())

# Reasoning-heavy stacking logic gets the pro-tier model (validated string;
# `gemini-3.1-pro` from the brief does not exist on Vertex).
MODEL = os.environ.get("REBATEIQ_PROPOSAL_MODEL", "gemini-3.1-pro-preview")

PROGRAM_FIELDS = [
    "program_id", "program_name", "description", "eligible_equipment",
    "classification", "submission_channel", "incentive_basis", "incentive_rate",
    "incentive_unit", "incentive_pct_cap", "incentive_max", "cost_basis",
    "pre_approval_required", "form_url", "region", "deadline", "funding_status",
]


def _programs_by_id(program_ids: list[str]) -> list[dict]:
    es = get_client()
    resp = es.mget(index=os.environ.get("ES_PROGRAMS_INDEX", "rebate_programs"),
                   ids=program_ids)
    return [d["_source"] for d in resp["docs"] if d.get("found")]


def match_incentive_programs(site_visit: dict) -> dict:
    """Find candidate incentive programs for a site visit via hybrid (BM25 +
    semantic) retrieval over the program corpus, filtered to the site's region
    and open funding. Returns candidates only — assess eligibility against each
    program's description and eligible_equipment before using one.

    Args:
        site_visit: the full site-visit payload (SiteVisit schema).
    """
    visit = SiteVisit(**site_visit)
    programs = _match(get_client(), visit)
    return {"candidates": [{k: p.get(k) for k in PROGRAM_FIELDS} for p in programs]}


def calculate_proposal(
    site_visit: dict,
    program_ids: list[str],
    rep_quotes: Optional[dict] = None,
) -> dict:
    """Compute the full proposal money picture deterministically: annual
    savings, each program's incentive amount with its confirmation status,
    stacked totals, net cost, and payback. Never compute these yourself.

    Args:
        site_visit: the full site-visit payload (SiteVisit schema).
        program_ids: ids of the programs you judged eligible.
        rep_quotes: {program_id: approved_amount} for figures returned by a
            program representative (flips those lines to confirmed).
    """
    visit = SiteVisit(**site_visit)
    calc = build_proposal_calc(visit, _programs_by_id(program_ids), rep_quotes)
    return calc.model_dump()


def draft_rep_submission_email(
    site_visit: dict, program_id: str, contractor: dict
) -> str:
    """Draft the territory-rep submission email for an email-channel program
    (existing + proposed equipment specs). The contractor reviews and sends it;
    nothing is sent automatically.

    Args:
        site_visit: the full site-visit payload (SiteVisit schema).
        program_id: the email-channel program to submit under.
        contractor: ContractorProfile fields (company_name, contact_name,
            phone, email).
    """
    visit = SiteVisit(**site_visit)
    (program,) = _programs_by_id([program_id])
    return rep.draft_submission_email(visit, program, ContractorProfile(**contractor))


def get_simulated_rep_reply(site_visit: dict, program_id: str) -> str:
    """DEMO ONLY: returns the territory rep's reply email that would normally
    arrive in 2-5 business days (production uses a Gmail watch instead).

    Args:
        site_visit: the full site-visit payload (SiteVisit schema).
        program_id: the email-channel program submitted under.
    """
    visit = SiteVisit(**site_visit)
    (program,) = _programs_by_id([program_id])
    return rep.simulate_rep_reply(visit, program)


def parse_rep_reply_email(email_text: str) -> dict:
    """Extract the approved rebate amount and projected annual gas savings
    from a rep's reply email. Raises if the figures are missing — in that case
    tell the contractor to read the email themselves.

    Args:
        email_text: the rep reply email body.
    """
    return rep.parse_rep_reply(email_text)


def render_proposal_pdf_file(
    site_visit: dict,
    program_ids: list[str],
    contractor: dict,
    out_path: str,
    rep_quotes: Optional[dict] = None,
) -> str:
    """Render the branded proposal PDF (recomputes the money picture
    deterministically from the same inputs) and return the file path.

    Args:
        site_visit: the full site-visit payload (SiteVisit schema).
        program_ids: ids of the eligible programs to include.
        contractor: ContractorProfile fields for branding.
        out_path: where to write the PDF (e.g. data/output/proposal.pdf).
        rep_quotes: {program_id: approved_amount} from parsed rep replies.
    """
    visit = SiteVisit(**site_visit)
    calc = build_proposal_calc(visit, _programs_by_id(program_ids), rep_quotes)
    return render_proposal_pdf(visit, calc, ContractorProfile(**contractor), out_path)


root_agent = Agent(
    model=MODEL,
    name="proposal_generator",
    description="Turns site-visit data into a branded, incentive-stacked PDF proposal.",
    instruction=(
        "You are the RebateIQ Proposal Generator for HVAC contractors.\n"
        "Workflow: 1) match_incentive_programs for the site visit. 2) Judge each "
        "candidate's eligibility yourself from its description and eligible_equipment "
        "(fuel type, equipment class, building type, region) and say in one line why "
        "each was kept or dropped. 3) For eligible email-channel custom programs, "
        "draft the rep submission with draft_rep_submission_email and wait for the "
        "contractor's go-ahead; once a rep reply is available, parse_rep_reply_email "
        "and carry the figures as rep_quotes. 4) calculate_proposal with the eligible "
        "program ids. 5) On request, render_proposal_pdf_file.\n"
        "Stacking: two programs from the same utility or administrator do not stack "
        "for the same measure — pick the better pathway and say why (federal + "
        "provincial + utility can usually stack; financing stacks with rebates).\n"
        "Hard rules: every dollar figure shown to the user must come from a tool "
        "result — never compute or estimate money yourself. Label each incentive with "
        "its status (confirmed / estimated pending approval / awaiting rep / "
        "financing). If required site-visit fields are missing, ask for them instead "
        "of guessing. The contractor enters the installed price; never invent it."
    ),
    tools=[
        match_incentive_programs,
        calculate_proposal,
        draft_rep_submission_email,
        get_simulated_rep_reply,
        parse_rep_reply_email,
        render_proposal_pdf_file,
    ],
)
