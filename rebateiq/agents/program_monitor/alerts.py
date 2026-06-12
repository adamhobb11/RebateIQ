"""
The Program Monitor's actual monitoring: deterministic change detection over
the incentive corpus, emitting the contractor-facing push alert.

Production shape: a scheduled job (Cloud Scheduler -> Cloud Run) re-ingests
DSIRE/NRCan/utility feeds, then runs this scan against the previous snapshot
and pushes the digest. The ADK agent is the conversational layer over the
same index — it explains and answers; this module watches and alerts.
At DSIRE scale (2,500+ programs) the scan would be pre-scoped to the
contractor's equipment profile via the shared hybrid query; on the seed
corpus a region filter is enough.

Detection rules (per the brief):
- new program appears in the contractor's territory
- funding status changes (open -> closing / waitlist / fully_reserved)
- application deadline inside the warning window (default 30 days)
"""

from datetime import date
from typing import Literal, Optional

from elasticsearch import Elasticsearch
from pydantic import BaseModel

from rebateiq.shared.es import PROGRAMS_INDEX

URGENT_WINDOW_DAYS = 7

FUNDING_RANK = {"open": 0, "closing": 1, "waitlist": 2, "fully_reserved": 3}


class Alert(BaseModel):
    alert_type: Literal["new_program", "funding_change", "deadline_approaching"]
    urgency: Literal["info", "warn", "urgent"]
    program_id: str
    program_name: str
    region: str
    headline: str
    detail: str


def fetch_region_programs(es: Elasticsearch, region: str) -> list[dict]:
    country = region.split("-")[0]
    regions = [region] if region == country else [region, country]
    resp = es.search(
        index=PROGRAMS_INDEX,
        query={"terms": {"region": regions}},
        size=500,
        source_excludes=["semantic_combined"],
    )
    return [h["_source"] for h in resp["hits"]["hits"]]


def deadline_alerts(
    programs: list[dict], as_of: date, window_days: int = 30
) -> list[Alert]:
    alerts = []
    for p in programs:
        if not p.get("deadline"):
            continue
        days_left = (date.fromisoformat(p["deadline"]) - as_of).days
        if 0 <= days_left <= window_days:
            alerts.append(Alert(
                alert_type="deadline_approaching",
                urgency="urgent" if days_left <= URGENT_WINDOW_DAYS else "warn",
                program_id=p["program_id"],
                program_name=p["program_name"],
                region=p["region"],
                headline=f"{days_left} days left — deadline {p['deadline']}",
                detail=(
                    "Submit open applications before this date; program terms "
                    "may change or close after it."
                ),
            ))
    return alerts


def funding_change_alerts(
    programs: list[dict], previous_statuses: dict[str, str]
) -> list[Alert]:
    alerts = []
    for p in programs:
        before = previous_statuses.get(p["program_id"])
        now = p.get("funding_status", "open")
        if before is None or before == now:
            continue
        worsened = FUNDING_RANK.get(now, 0) > FUNDING_RANK.get(before, 0)
        alerts.append(Alert(
            alert_type="funding_change",
            urgency="urgent" if worsened else "info",
            program_id=p["program_id"],
            program_name=p["program_name"],
            region=p["region"],
            headline=f"funding status: {before} → {now}",
            detail=(
                "Get eligible customers submitted now — funding windows close "
                "fast once status slips." if worsened
                else "Funding has reopened or improved — worth re-pitching past prospects."
            ),
        ))
    return alerts


def new_program_alerts(programs: list[dict], seen_ids: set[str]) -> list[Alert]:
    alerts = []
    for p in programs:
        if p["program_id"] in seen_ids:
            continue
        bits = []
        if p.get("incentive_rate") and p.get("incentive_basis") == "flat":
            unit = p.get("incentive_unit", "").replace("_", " ")
            bits.append(f"${p['incentive_rate']:,.0f} {unit}".strip())
        if p.get("deadline"):
            bits.append(f"apply by {p['deadline']}")
        alerts.append(Alert(
            alert_type="new_program",
            urgency="warn",
            program_id=p["program_id"],
            program_name=p["program_name"],
            region=p["region"],
            headline="new program in your territory" + (f" — {'; '.join(bits)}" if bits else ""),
            detail=(p.get("description") or "")[:220],
        ))
    return alerts


def scan(
    programs: list[dict],
    *,
    as_of: date,
    seen_ids: Optional[set[str]] = None,
    previous_statuses: Optional[dict[str, str]] = None,
    window_days: int = 30,
) -> list[Alert]:
    alerts: list[Alert] = []
    if seen_ids is not None:
        alerts += new_program_alerts(programs, seen_ids)
    if previous_statuses is not None:
        alerts += funding_change_alerts(programs, previous_statuses)
    alerts += deadline_alerts(programs, as_of, window_days)
    order = {"urgent": 0, "warn": 1, "info": 2}
    return sorted(alerts, key=lambda a: order[a.urgency])


TAGS = {"new_program": "NEW", "funding_change": "FUNDING", "deadline_approaching": "DEADLINE"}


def format_digest(alerts: list[Alert], region_label: str, as_of: date) -> str:
    """The plain-language push notification the contractor actually receives."""
    if not alerts:
        return f"RebateIQ — {region_label} — {as_of:%B %d, %Y}: no incentive changes today."
    lines = [f"RebateIQ Incentive Alerts — {region_label} — {as_of:%B %d, %Y}", ""]
    for a in alerts:
        bang = "!" if a.urgency == "urgent" else ""
        lines.append(f"[{TAGS[a.alert_type]}{bang}] {a.program_name}")
        lines.append(f"    {a.headline}")
        lines.append(f"    {a.detail}")
        lines.append("")
    lines.append("Reply to any alert to start prospecting for it.")
    return "\n".join(lines)
