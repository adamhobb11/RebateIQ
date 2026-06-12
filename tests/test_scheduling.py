"""Unit tests for slot finding, .ics generation, and classification voting."""

from datetime import datetime

from rebateiq.agents.appointment_booking.scheduling import (
    book_slot,
    classify_votes,
    next_available_slots,
    sim_busy,
    to_ics,
)

# Thursday June 11 2026 16:00 — slots must start Friday morning.
NOW = datetime(2026, 6, 11, 16, 0)


def test_slots_skip_busy_weekends_and_hours():
    busy = sim_busy(NOW)
    slots = next_available_slots(busy, NOW, n=3)
    assert len(slots) == 3
    for s in slots:
        assert s.weekday() < 5
        assert 9 <= s.hour < 17
        assert not any(b0 <= s < b1 for b0, b1 in busy)
    # Friday June 12: busy 9-12 and 14-15 -> first free hour starts 12:00
    assert slots[0] == datetime(2026, 6, 12, 12, 0)
    assert slots[0] < slots[1] < slots[2]


def test_fully_booked_days_are_skipped():
    # one solid 9-17 block every weekday for two weeks
    busy = []
    from datetime import time, timedelta
    d = NOW.date()
    for off in range(14):
        day = d + timedelta(days=off)
        busy.append((datetime.combine(day, time(9)), datetime.combine(day, time(17))))
    assert next_available_slots(busy, NOW, n=3, days_ahead=10) == []


def test_ics_contains_event_fields():
    ics = to_ics(
        datetime(2026, 6, 16, 10, 0), 60,
        summary="Site assessment — Maplewood Court Apartments",
        location="38 Maplewood Crt, Scarborough",
        description="Assessment.",
        uid="rebateiq-test123",
    )
    for needle in [
        "BEGIN:VCALENDAR", "BEGIN:VEVENT", "UID:rebateiq-test123",
        "DTSTART:20260616T100000", "DTEND:20260616T110000",
        "SUMMARY:Site assessment — Maplewood Court Apartments",
        "LOCATION:38 Maplewood Crt, Scarborough", "BEGIN:VALARM",
    ]:
        assert needle in ics


def test_book_slot_writes_ics(tmp_path):
    result = book_slot(
        datetime(2026, 6, 16, 10, 0),
        business_name="Maplewood Court Apartments",
        address="38 Maplewood Crt, Scarborough",
        out_dir=str(tmp_path),
    )
    assert result["start"] == "2026-06-16T10:00:00"
    text = (tmp_path / f"{result['uid']}.ics").read_text()
    assert "Maplewood Court Apartments" in text


def test_classification_votes_are_score_weighted():
    hits = [
        {"_score": 10.0, "_source": {"intent": "interested", "text": "a"}},
        {"_score": 6.0, "_source": {"intent": "question", "text": "b"}},
        {"_score": 5.0, "_source": {"intent": "interested", "text": "c"}},
        {"_score": 4.0, "_source": {"intent": "decline", "text": "d"}},
    ]
    intent, confidence = classify_votes(hits)
    assert intent == "interested"
    assert confidence == 0.6  # 15 / 25


def test_classification_empty_is_unclassified():
    assert classify_votes([]) == ("unclassified", 0.0)
