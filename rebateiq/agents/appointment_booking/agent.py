"""
RebateIQ — Response & Scheduling agent.

Converts interest into a booked site assessment. Classification is semantic
(ELSER over the reply_intents exemplar corpus — "Would love to hear more"
and "what would this cost us" are routed correctly with zero keyword
overlap). Availability and booking go through the typed calendar layer:
simulated busy schedule + real .ics output today; the Google Calendar
MCP/API swaps in behind the same two tools in production.

Every drafted reply is presented for contractor review before sending —
this agent never sends anything itself.
"""

import os
from datetime import datetime

from dotenv import find_dotenv, load_dotenv
from google.adk.agents import Agent

from rebateiq.shared.es import get_client

from . import scheduling

load_dotenv(find_dotenv())

MODEL = os.environ.get("REBATEIQ_MODEL", "gemini-3.5-flash")
CALENDAR_DIR = "data/output/calendar"


def classify_prospect_reply(reply_text: str) -> dict:
    """Semantically classify a prospect's reply: interested / question /
    decline / out_of_office, with a confidence score. Always classify before
    drafting anything.

    Args:
        reply_text: the prospect's email reply, verbatim.
    """
    return scheduling.classify_reply(get_client(), reply_text)


def get_available_slots(n: int = 3) -> dict:
    """The contractor's next available site-visit slots (business hours,
    excluding busy blocks). Propose these to the prospect, numbered.

    Args:
        n: how many slots to fetch (default 3).
    """
    now = datetime.now()
    slots = scheduling.next_available_slots(scheduling.sim_busy(now), now, n=n)
    return {
        "slots": [
            {"option": i, "start_iso": s.isoformat(),
             "label": s.strftime("%A %B %d, %I:%M %p")}
            for i, s in enumerate(slots, start=1)
        ]
    }


def book_appointment(slot_iso: str, business_name: str, address: str) -> dict:
    """Book the confirmed slot: writes the calendar event (.ics with a 1-day
    reminder) and returns the booking details. Call ONLY after the prospect
    has confirmed one specific slot.

    Args:
        slot_iso: the confirmed slot's start_iso value.
        business_name: the prospect's business name.
        address: the site address for the visit.
    """
    return scheduling.book_slot(
        datetime.fromisoformat(slot_iso),
        business_name=business_name,
        address=address,
        out_dir=CALENDAR_DIR,
    )


root_agent = Agent(
    model=MODEL,
    name="appointment_booking",
    description="Classifies prospect replies and books site assessments.",
    instruction=(
        "You are the RebateIQ Response & Scheduling agent for an HVAC contractor.\n"
        "For every prospect reply: 1) classify_prospect_reply first and state the "
        "intent + confidence. 2) Then act by intent:\n"
        "- interested: get_available_slots, draft a warm short reply — thank them, "
        "one line on what the visit covers (about an hour: equipment specs and "
        "consumption review, no obligation), then the numbered slots; ask them to "
        "reply with a number.\n"
        "- question: answer briefly and honestly from the program context you were "
        "given (never invent figures), then offer the slots the same way.\n"
        "- decline: draft a one-line gracious close, confirm they will receive no "
        "further messages (our policy), and mark no follow-up.\n"
        "- out_of_office: no reply now; note the return date and recommend one "
        "follow-up after it.\n"
        "3) Drafts are for the contractor to review — never claim anything was sent.\n"
        "4) book_appointment ONLY when the prospect has confirmed one specific slot; "
        "after booking, draft the confirmation email: date/time, address, what to "
        "expect, and that a reminder is included."
    ),
    tools=[classify_prospect_reply, get_available_slots, book_appointment],
)
