"""
Prospect identification over the seeded business-listings corpus.

Input is an ideal-customer profile in plain language (the agent writes it
from the incentive program; see scripts/demo_semantic_vs_keyword.py for why
hybrid retrieval is what makes this work) plus a territory. Output is an
approval-ready list — the contractor reviews and approves before any
outreach happens.

v1 deliberately has NO live scraping (Build Log Entry 010): the production
data path is the Google Places API / licensed B2B data, not LinkedIn or Maps
scraping. Every listing here is fictional and PII-free.
"""

from elasticsearch import Elasticsearch
from pydantic import BaseModel

from rebateiq.shared.es import LISTINGS_INDEX
from rebateiq.shared.search import LISTING_TEXT_FIELDS, hybrid_search


class Prospect(BaseModel):
    rank: int
    listing_id: str
    business_name: str
    building_type: str
    contact_name: str
    contact_title: str
    email: str
    address: str
    city: str
    why_match: str
    score: float


def rank_prospects(
    es: Elasticsearch,
    profile_query: str,
    region: str = "CA-ON",
    size: int = 10,
) -> list[Prospect]:
    hits = hybrid_search(
        es,
        LISTINGS_INDEX,
        profile_query,
        fields=LISTING_TEXT_FIELDS,
        filters=[{"term": {"region": region}}],
        size=size,
    )
    prospects = []
    for i, h in enumerate(hits, start=1):
        s = h["_source"]
        why = s.get("heating_system", "")
        if s.get("units"):
            why += f"; {s['units']} units"
        prospects.append(Prospect(
            rank=i,
            listing_id=s["listing_id"],
            business_name=s["business_name"],
            building_type=s["building_type"],
            contact_name=s["contact_name"],
            contact_title=s["contact_title"],
            email=s["email"],
            address=s["address"],
            city=s["city"],
            why_match=why,
            score=round(h["_score"], 4),
        ))
    return prospects


def format_approval_list(
    prospects: list[Prospect], program_name: str, region_label: str
) -> str:
    """The human-in-the-loop artifact: nothing is contacted until approved."""
    lines = [
        f"PROSPECT LIST FOR APPROVAL — {program_name} — {region_label}",
        f"{len(prospects)} prospects, ranked by fit. Remove any line before approving.",
        "",
    ]
    for i, p in enumerate(prospects, start=1):  # renumber: callers may have dropped fits
        lines.append(f"{i:>2}. {p.business_name} — {p.building_type}")
        lines.append(f"     {p.contact_name}, {p.contact_title} <{p.email}>")
        lines.append(f"     {p.address}, {p.city}  |  {p.why_match}")
        lines.append("")
    lines += [
        "Compliance: contacts are publicly listed business addresses (CASL implied",
        "consent basis). Every outreach email will carry sender identification and",
        "a working unsubscribe link, with at most one follow-up to non-responders.",
        "",
        "Approve all, or reply with the numbers to drop.",
    ]
    return "\n".join(lines)
