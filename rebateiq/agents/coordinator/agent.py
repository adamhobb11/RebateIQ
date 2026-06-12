"""
RebateIQ — root coordinator.

One entry point over the whole sales loop. The coordinator routes each
request to the right specialist (ADK sub-agent transfer); specialists hand
control back when their piece is done. This is also the single agent the
demo UI and the Cloud Run deployment talk to.

    detect (program_monitor) -> prospect (prospect_identifier)
    -> outreach (outreach) -> book (appointment_booking)
    -> close (proposal_generator)
"""

import os

from dotenv import find_dotenv, load_dotenv
from google.adk.agents import Agent

from rebateiq.agents.appointment_booking.agent import build_agent as build_booking
from rebateiq.agents.outreach.agent import build_agent as build_outreach
from rebateiq.agents.program_monitor.agent import build_agent as build_monitor
from rebateiq.agents.proposal_generator.agent import build_agent as build_proposal
from rebateiq.agents.prospect_identifier.agent import build_agent as build_prospects

load_dotenv(find_dotenv())

MODEL = os.environ.get("REBATEIQ_MODEL", "gemini-3.5-flash")


def build_agent() -> Agent:
    return Agent(
        model=MODEL,
        name="rebateiq_coordinator",
        description="Routes the contractor's request to the right RebateIQ specialist.",
        instruction=(
            "You are RebateIQ, an HVAC contractor's incentive-intelligence team in "
            "one place. Route each request to the right specialist:\n"
            "- program questions, 'what changed', deadlines, eligibility language "
            "-> program_monitor\n"
            "- 'who should I pitch this to', prospect lists -> prospect_identifier\n"
            "- campaign drafting / sending after a list is approved -> outreach\n"
            "- a prospect REPLIED (interest, questions, decline, OOO), scheduling, "
            "booking -> appointment_booking\n"
            "- site-visit data, savings math, rebate stacking, the proposal PDF "
            "-> proposal_generator\n"
            "Transfer to exactly one specialist per request. When a specialist "
            "finishes and control returns, summarize the outcome in one or two "
            "lines and suggest the natural next step in the loop (detect -> "
            "prospect -> outreach -> book -> propose). If the request spans two "
            "phases, do them in order, not in parallel."
        ),
        sub_agents=[
            build_monitor(),
            build_prospects(),
            build_outreach(),
            build_booking(),
            build_proposal(),
        ],
    )


root_agent = build_agent()
