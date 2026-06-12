"""
The Program Monitor storyline: the contractor finds out FIRST.

Simulates what the scheduled production job does overnight — re-ingest the
program feeds, diff against yesterday's snapshot, push the digest:

  1. snapshot what the contractor has already seen (ids + funding statuses)
  2. simulated feed update: a brand-new Enbridge program appears, and the
     HRSP funding status slips from open -> closing
  3. scan: new-program + funding-change + deadline-window detection
  4. print the push notification
  5. restore the corpus exactly as it was (idempotent — safe to re-run)

    python scripts/demo_monitor.py
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rebateiq.agents.program_monitor.alerts import (  # noqa: E402
    fetch_region_programs,
    format_digest,
    scan,
)
from rebateiq.shared.es import PROGRAMS_INDEX, get_client  # noqa: E402

REGION = "CA-ON"

INJECTED = {
    "program_id": "enbridge-boiler-accelerator-2026",
    "program_name": "Enbridge Commercial Boiler Accelerator — Fall 2026",
    "description": (
        "Limited-time bonus incentive for commercial condensing boiler "
        "retrofits completed before year end in the Enbridge service "
        "territory. Fixed amount per qualifying boiler, stacking with the "
        "standard retrofit pathways."
    ),
    "eligible_equipment": "Commercial condensing boilers, minimum 90% thermal efficiency",
    "classification": "prescriptive",
    "submission_channel": "web_form",
    "incentive_basis": "flat",
    "incentive_rate": 1500,
    "incentive_unit": "per_unit",
    "cost_basis": "total",
    "pre_approval_required": False,
    "auth_required": False,
    "form_type": "web_form",
    "source": "demo_simulated_feed",
    "source_urls": ["https://www.enbridgegas.com/business-industrial"],
    "region": "CA-ON",
    "deadline": "2026-12-15",
    "funding_status": "open",
}

FLIP_ID = "on-hrsp-heating"


def banner(text: str) -> None:
    print("\n" + "=" * 78 + f"\n{text}\n" + "=" * 78)


def main() -> None:
    es = get_client()
    today = date.today()

    banner("1) YESTERDAY'S SNAPSHOT (what the contractor already knows)")
    before = fetch_region_programs(es, REGION)
    seen_ids = {p["program_id"] for p in before}
    statuses = {p["program_id"]: p.get("funding_status", "open") for p in before}
    initial_count = es.count(index=PROGRAMS_INDEX)["count"]
    print(f"  {len(before)} programs known in {REGION}; corpus total {initial_count}")

    try:
        banner("2) OVERNIGHT FEED UPDATE (simulated DSIRE/NRCan/utility poll)")
        es.index(index=PROGRAMS_INDEX, id=INJECTED["program_id"], document=INJECTED)
        es.update(index=PROGRAMS_INDEX, id=FLIP_ID, doc={"funding_status": "closing"})
        es.indices.refresh(index=PROGRAMS_INDEX)
        print(f"  + new program indexed: {INJECTED['program_name']}")
        print(f"  ~ {FLIP_ID}: funding open -> closing")

        banner("3) CHANGE-DETECTION SCAN")
        after = fetch_region_programs(es, REGION)
        alerts = scan(after, as_of=today, seen_ids=seen_ids, previous_statuses=statuses)
        for a in alerts:
            print(f"  [{a.urgency:<6}] {a.alert_type:<20} {a.program_id}")

        banner("4) THE PUSH NOTIFICATION")
        print(format_digest(alerts, "Ontario", today))

    finally:
        es.options(ignore_status=404).delete(
            index=PROGRAMS_INDEX, id=INJECTED["program_id"]
        )
        es.update(index=PROGRAMS_INDEX, id=FLIP_ID,
                  doc={"funding_status": statuses.get(FLIP_ID, "open")})
        es.indices.refresh(index=PROGRAMS_INDEX)

    banner("5) CORPUS RESTORED")
    final_count = es.count(index=PROGRAMS_INDEX)["count"]
    final_status = es.get(index=PROGRAMS_INDEX, id=FLIP_ID)["_source"]["funding_status"]
    print(f"  doc count {final_count} (was {initial_count}); "
          f"{FLIP_ID} funding_status={final_status}")
    assert final_count == initial_count and final_status == statuses.get(FLIP_ID)
    print("  clean — safe to re-run any time.")


if __name__ == "__main__":
    main()
