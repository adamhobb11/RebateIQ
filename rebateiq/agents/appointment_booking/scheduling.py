"""
Response classification + appointment scheduling.

Classification is semantic, per the brief: a prospect's reply is matched
against a small exemplar corpus (`reply_intents`, ELSER) — "Would love to
hear more" and "What would this cost us?" share no keywords with the
exemplars they match. Votes are score-weighted across the top hits.

The calendar layer is a typed interface with a simulated backend: a fixed
busy schedule and bookings written as real .ics files (importable into any
calendar app). Production swaps in the Google Calendar MCP / API behind the
same two functions — find slots, book slot.
"""

from datetime import date, datetime, time, timedelta
from pathlib import Path
from uuid import uuid4

from elasticsearch import Elasticsearch

from rebateiq.shared.es import INTENTS_INDEX
from rebateiq.shared.search import semantic_search

BUSINESS_START = time(9, 0)
BUSINESS_END = time(17, 0)
SLOT_MINUTES = 60


# --- reply classification ------------------------------------------------------

def classify_votes(hits: list[dict]) -> tuple[str, float]:
    """Score-weighted vote over exemplar hits -> (intent, confidence)."""
    if not hits:
        return "unclassified", 0.0
    scores: dict[str, float] = {}
    for h in hits:
        intent = h["_source"]["intent"]
        scores[intent] = scores.get(intent, 0.0) + h["_score"]
    total = sum(scores.values())
    intent = max(scores, key=scores.get)
    return intent, round(scores[intent] / total, 3)


def classify_reply(es: Elasticsearch, reply_text: str, size: int = 5) -> dict:
    hits = semantic_search(es, INTENTS_INDEX, reply_text, size=size)
    intent, confidence = classify_votes(hits)
    return {
        "intent": intent,
        "confidence": confidence,
        "nearest_exemplar": hits[0]["_source"]["text"] if hits else None,
    }


# --- availability ---------------------------------------------------------------

def sim_busy(start_from: datetime) -> list[tuple[datetime, datetime]]:
    """The simulated calendar: a believably busy week for a working contractor."""
    d0 = start_from.date()
    busy = []
    for offset in range(0, 10):
        day = d0 + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        # mornings on jobs; Wednesdays fully booked
        if day.weekday() == 2:
            busy.append((datetime.combine(day, time(9)), datetime.combine(day, time(17))))
        else:
            busy.append((datetime.combine(day, time(9)), datetime.combine(day, time(12))))
            busy.append((datetime.combine(day, time(14)), datetime.combine(day, time(15))))
    return busy


def next_available_slots(
    busy: list[tuple[datetime, datetime]],
    start_from: datetime,
    n: int = 3,
    duration_min: int = SLOT_MINUTES,
    days_ahead: int = 10,
) -> list[datetime]:
    """First n free business-hours slots, skipping weekends and busy blocks."""
    slots = []
    day = start_from.date() + timedelta(days=1)  # start tomorrow
    end_day = start_from.date() + timedelta(days=days_ahead)
    while day <= end_day and len(slots) < n:
        if day.weekday() < 5:
            cursor = datetime.combine(day, BUSINESS_START)
            day_end = datetime.combine(day, BUSINESS_END)
            while cursor + timedelta(minutes=duration_min) <= day_end and len(slots) < n:
                slot_end = cursor + timedelta(minutes=duration_min)
                if not any(b_start < slot_end and cursor < b_end for b_start, b_end in busy):
                    slots.append(cursor)
                    cursor = slot_end  # at most one slot per free block start
                else:
                    cursor += timedelta(minutes=30)
        day += timedelta(days=1)
    return slots


# --- booking --------------------------------------------------------------------

def to_ics(
    start: datetime,
    duration_min: int,
    summary: str,
    location: str,
    description: str,
    uid: str,
) -> str:
    end = start + timedelta(minutes=duration_min)
    fmt = "%Y%m%dT%H%M%S"
    return "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//RebateIQ//Appointment Booking//EN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.now().strftime(fmt)}",
        f"DTSTART:{start.strftime(fmt)}",
        f"DTEND:{end.strftime(fmt)}",
        f"SUMMARY:{summary}",
        f"LOCATION:{location}",
        f"DESCRIPTION:{description}",
        "BEGIN:VALARM",
        "TRIGGER:-P1D",
        "ACTION:DISPLAY",
        "DESCRIPTION:Site assessment tomorrow",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
        "",
    ])


def book_slot(
    start: datetime,
    business_name: str,
    address: str,
    out_dir: str,
    duration_min: int = SLOT_MINUTES,
) -> dict:
    uid = f"rebateiq-{uuid4().hex[:12]}"
    ics = to_ics(
        start,
        duration_min,
        summary=f"Site assessment — {business_name}",
        location=address,
        description=(
            "No-obligation HVAC site assessment: equipment rating-plate specs, "
            "consumption review, incentive eligibility. Booked by RebateIQ."
        ),
        uid=uid,
    )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{uid}.ics"
    path.write_text(ics)
    return {
        "uid": uid,
        "start": start.isoformat(),
        "duration_min": duration_min,
        "ics_path": str(path),
        "reminder": "1 day before (in the invite)",
    }
