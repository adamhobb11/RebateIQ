"""Unit tests for the Program Monitor's change-detection rules."""

from datetime import date

from rebateiq.agents.program_monitor.alerts import (
    deadline_alerts,
    format_digest,
    funding_change_alerts,
    new_program_alerts,
    scan,
)

AS_OF = date(2026, 6, 11)


def program(**overrides) -> dict:
    base = {
        "program_id": "p1",
        "program_name": "Test Program",
        "region": "CA-ON",
        "funding_status": "open",
        "description": "A test incentive for condensing boilers.",
    }
    base.update(overrides)
    return base


# --- deadlines ---------------------------------------------------------------

def test_deadline_inside_window_warns():
    alerts = deadline_alerts([program(deadline="2026-06-30")], AS_OF)
    assert len(alerts) == 1
    assert alerts[0].urgency == "warn"
    assert "19 days left" in alerts[0].headline


def test_deadline_within_a_week_is_urgent():
    alerts = deadline_alerts([program(deadline="2026-06-15")], AS_OF)
    assert alerts[0].urgency == "urgent"


def test_deadline_outside_window_or_past_is_silent():
    assert deadline_alerts([program(deadline="2026-12-31")], AS_OF) == []
    assert deadline_alerts([program(deadline="2026-06-01")], AS_OF) == []
    assert deadline_alerts([program()], AS_OF) == []  # no deadline at all


# --- funding changes -----------------------------------------------------------

def test_funding_worsening_is_urgent():
    alerts = funding_change_alerts(
        [program(funding_status="closing")], {"p1": "open"}
    )
    assert len(alerts) == 1
    assert alerts[0].urgency == "urgent"
    assert "open → closing" in alerts[0].headline


def test_funding_improving_is_info():
    alerts = funding_change_alerts(
        [program(funding_status="open")], {"p1": "fully_reserved"}
    )
    assert alerts[0].urgency == "info"


def test_funding_unchanged_or_unknown_program_is_silent():
    assert funding_change_alerts([program()], {"p1": "open"}) == []
    assert funding_change_alerts([program()], {}) == []


# --- new programs --------------------------------------------------------------

def test_new_program_fires_once_with_amount_and_deadline():
    p = program(
        program_id="new1", incentive_basis="flat", incentive_rate=1000,
        incentive_unit="per_unit", deadline="2026-12-15",
    )
    alerts = new_program_alerts([p], seen_ids={"p1"})
    assert len(alerts) == 1
    assert "$1,000 per unit" in alerts[0].headline
    assert "apply by 2026-12-15" in alerts[0].headline
    assert new_program_alerts([p], seen_ids={"new1"}) == []


# --- scan + digest ---------------------------------------------------------------

def test_scan_sorts_urgent_first_and_digest_reads_clean():
    programs = [
        program(program_id="new1", program_name="Brand New Bonus"),
        program(program_id="p1", program_name="Slipping Fund", funding_status="closing"),
        program(program_id="p2", program_name="Deadline Soon", deadline="2026-06-30"),
    ]
    alerts = scan(
        programs,
        as_of=AS_OF,
        seen_ids={"p1", "p2"},
        previous_statuses={"p1": "open", "p2": "open"},
    )
    assert [a.urgency for a in alerts] == ["urgent", "warn", "warn"]

    digest = format_digest(alerts, "Ontario", AS_OF)
    assert "RebateIQ Incentive Alerts — Ontario" in digest
    assert "[FUNDING!] Slipping Fund" in digest
    assert "[NEW] Brand New Bonus" in digest
    assert "[DEADLINE] Deadline Soon" in digest


def test_empty_scan_digest():
    assert "no incentive changes" in format_digest([], "Ontario", AS_OF)
