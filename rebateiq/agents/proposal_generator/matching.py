"""
Site visit -> candidate incentive programs, via hybrid retrieval.

The query is built from the job's own vocabulary (equipment, building type);
the corpus is written in each program's vocabulary. Hybrid BM25 + ELSER
retrieval bridges the terminology gap — see scripts/demo_semantic_vs_keyword.py
for the receipts. Region and funding-status guards are deterministic filters;
final eligibility reasoning (thresholds, fuel, building class) is the agent's
job, with the program description in front of it.
"""

from elasticsearch import Elasticsearch

from rebateiq.shared.es import PROGRAMS_INDEX
from rebateiq.shared.search import PROGRAM_TEXT_FIELDS, hybrid_search

from .schemas import SiteVisit


def build_query_text(visit: SiteVisit) -> str:
    ex, new = visit.existing, visit.proposed
    return (
        f"replacing a {ex.age_years} year old {ex.fuel_type.replace('_', ' ')} "
        f"{ex.equipment_type} at {ex.afue_pct:.0f}% efficiency with a "
        f"{new.make} {new.model} rated {new.afue_pct:.0f}% AFUE, "
        f"{visit.building_type}"
    )


def region_filters(region: str) -> list[dict]:
    # A site in CA-ON can use provincial (CA-ON) and federal (CA) programs.
    country = region.split("-")[0]
    regions = [region] if region == country else [region, country]
    return [
        {"terms": {"region": regions}},
        {"bool": {"must_not": [{"term": {"funding_status": "fully_reserved"}}]}},
    ]


def match_programs(es: Elasticsearch, visit: SiteVisit, size: int = 8) -> list[dict]:
    hits = hybrid_search(
        es,
        PROGRAMS_INDEX,
        build_query_text(visit),
        fields=PROGRAM_TEXT_FIELDS,
        filters=region_filters(visit.region),
        size=size,
    )
    return [h["_source"] for h in hits]
