"""
The Response & Scheduling storyline, deterministic where it can be (the
classification runs live against the cluster — that's the point): prospect
reply -> semantic intent -> three slots -> confirmation -> booked .ics.
The live-agent version is scripts/check_scheduling_agent.py.

    python scripts/demo_scheduling.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rebateiq.agents.appointment_booking.scheduling import (  # noqa: E402
    book_slot,
    classify_reply,
    next_available_slots,
    sim_busy,
)
from rebateiq.shared.es import get_client  # noqa: E402

CAL_DIR = Path(__file__).resolve().parents[1] / "data/output/calendar"

REPLY = "This looks interesting, can someone come take a look?"
PROSPECT = {"business_name": "Maplewood Court Apartments",
            "address": "38 Maplewood Crt, Scarborough"}


def main() -> None:
    es = get_client()

    print(f'1) PROSPECT REPLY: "{REPLY}"')
    intent = classify_reply(es, REPLY)
    print(f"   semantic classification: {intent['intent']} "
          f"(confidence {intent['confidence']:.2f}; "
          f"nearest exemplar: \"{intent['nearest_exemplar']}\")\n")

    now = datetime.now()
    slots = next_available_slots(sim_busy(now), now, n=3)
    print("2) NEXT AVAILABLE SLOTS (business hours, busy blocks skipped):")
    for i, s in enumerate(slots, start=1):
        print(f"   {i}. {s:%A %B %d, %I:%M %p}")

    print("\n3) [drafted reply with the three options goes to the contractor for review,")
    print("    then to the prospect — prospect picks option 2]\n")

    booking = book_slot(slots[1], out_dir=str(CAL_DIR), **PROSPECT)
    print("4) BOOKED:")
    print(f"   {booking['start']} at {PROSPECT['address']}")
    print(f"   calendar event: {booking['ics_path']} (reminder: {booking['reminder']})")
    print("\nProduction swap: Google Calendar MCP/API behind the same two calls.")


if __name__ == "__main__":
    main()
