"""
RebateIQ — Prospect Identifier agent.

Incentive program in, approval-ready prospect list out. The LLM's job is the
translation step — turning a program's eligibility language into an
ideal-customer profile in plain words — and the typed tool runs the proven
hybrid retrieval over the listings corpus. No scraping, no CRM: public-data
prospecting that asks nothing of the contractor.
"""

import os

from dotenv import find_dotenv, load_dotenv
from google.adk.agents import Agent

from rebateiq.shared.es import PROGRAMS_INDEX, get_client

from .prospecting import Prospect, format_approval_list, rank_prospects

load_dotenv(find_dotenv())

MODEL = os.environ.get("REBATEIQ_MODEL", "gemini-3.5-flash")


def get_program(program_id: str) -> dict:
    """Fetch one incentive program document by id, to ground the
    ideal-customer profile in its actual eligibility language.

    Args:
        program_id: the program's id (e.g. from a Program Monitor alert).
    """
    es = get_client()
    doc = es.get(index=PROGRAMS_INDEX, id=program_id, source_excludes=["semantic_combined"])
    return doc["_source"]


def find_prospects(profile_query: str, region: str = "CA-ON", size: int = 10) -> dict:
    """Rank businesses in the territory against an ideal-customer profile,
    using hybrid (keyword + semantic) retrieval — listings describe themselves
    in different words than the profile, and semantic matching bridges that.

    Args:
        profile_query: the ideal customer in plain language — building type,
            equipment situation, decision-maker (e.g. "multi-unit residential
            building heated by an old natural gas boiler plant").
        region: territory keyword, e.g. CA-ON.
        size: how many prospects to return.
    """
    prospects = rank_prospects(get_client(), profile_query, region=region, size=size)
    return {"prospects": [p.model_dump() for p in prospects]}


def render_approval_list(prospects: list[dict], program_name: str, region_label: str) -> str:
    """Format the final approval-ready list exactly as the contractor sees it
    (includes the CASL compliance footer). Use the prospects you decided to keep.

    Args:
        prospects: the prospect dicts you kept, in rank order.
        program_name: the incentive program the list targets.
        region_label: human label for the territory, e.g. "Ontario".
    """
    return format_approval_list(
        [Prospect(**p) for p in prospects], program_name, region_label
    )


def build_agent() -> Agent:
    """Fresh agent instance (factory so the coordinator can own its own copy)."""
    return Agent(
    model=MODEL,
    name="prospect_identifier",
    description="Builds an approval-ready prospect list for a detected incentive program.",
    instruction=(
        "You are the RebateIQ Prospect Identifier for HVAC contractors.\n"
        "Given an incentive program (or an alert naming one): 1) get_program to read "
        "its eligibility language. 2) Write the ideal-customer profile in plain words "
        "— building type, equipment situation, decision-maker role — NOT by copying "
        "program text verbatim. 3) find_prospects with that profile. 4) Drop any "
        "result that is clearly a poor fit (wrong equipment, brand-new systems, "
        "heating not under the tenant's control) and say why in one line each. "
        "5) render_approval_list with the keepers and show it.\n"
        "Hard rules: prospects come only from find_prospects results — never invent "
        "businesses, contacts, or emails. Nothing is contacted until the contractor "
        "approves the list; say so. Keep the CASL footer intact."
    ),
    tools=[get_program, find_prospects, render_approval_list],
    )


root_agent = build_agent()
