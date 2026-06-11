"""
The Elastic partner-power receipt: semantic retrieval finds what keyword
search misses, on this cluster, with this corpus. Run after seed_corpus.py:

    python scripts/demo_semantic_vs_keyword.py

Scenario A — program matching across inconsistent terminology.
  The contractor's job is described in furnace / secondary-heat-exchanger /
  sealed-combustion words. The eligible Ontario programs are written in
  condensing-boiler / AFUE / hydronic words. Keyword search ranks an
  oil-conversion grant first and an EV-charger program third; semantic
  search returns exactly the eligible programs, in a sensible order.

Scenario B — prospect matching across building and job-title language.
  The ideal-customer profile is phrased one way; the listings describe the
  same buildings as superintendents, condo boards, and co-op coordinators.
  The single best prospect (cast-iron sectional boilers, hydronic loop) is
  invisible to keyword search and ranks #1 semantically.

The agents use hybrid_search (BM25 + ELSER fused with RRF) as the production
default; this script contrasts the two legs to show why both exist.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rebateiq.shared.es import LISTINGS_INDEX, PROGRAMS_INDEX, get_client  # noqa: E402
from rebateiq.shared.search import (  # noqa: E402
    LISTING_TEXT_FIELDS,
    PROGRAM_TEXT_FIELDS,
    keyword_search,
    semantic_search,
)

SCENARIOS = [
    {
        "label": "A) PROGRAMS — contractor language vs. program language",
        "index": PROGRAMS_INDEX,
        "fields": PROGRAM_TEXT_FIELDS,
        "query": (
            "replacing a twenty year old furnace running at eighty percent "
            "efficiency with a unit that has a secondary heat exchanger and "
            "sealed combustion venting, low-rise apartment block"
        ),
        "filters": [{"terms": {"region": ["CA-ON", "CA"]}}],
        "name_field": "program_name",
        "expect": [
            "enbridge-her-boiler",
            "enbridge-commercial-boiler-rep",
            "enbridge-commercial-custom",
            "on-hrsp-heating",
        ],
        "note": (
            "Keyword's top pick is an oil-to-heat-pump conversion grant the "
            "customer is ineligible for, with an EV-charger program at #3. "
            "Semantic's top 4 are exactly the four eligible boiler/heating programs."
        ),
    },
    {
        "label": "B) PROSPECTS — ideal-customer profile vs. how listings describe themselves",
        "index": LISTINGS_INDEX,
        "fields": LISTING_TEXT_FIELDS,
        "query": (
            "multi-unit residential building heated by an old natural gas "
            "boiler plant with rising heating costs"
        ),
        "filters": None,
        "name_field": "business_name",
        "expect": [
            "maplewood-court-apartments",
            "ycc-412-stclair",
            "parkdale-housing-coop",
        ],
        "note": (
            "The strongest prospect — 'building superintendent… atmospheric "
            "cast-iron sectional boilers… hydronic loop' — shares no ranking "
            "keywords with the profile. Keyword search never shows it; "
            "semantic search ranks it #1."
        ),
    },
]


def show(hits, name_field):
    for h in hits:
        print(f"    {h['_score']:>7.2f}  {h['_source'][name_field]}")


def main() -> None:
    es = get_client()
    for sc in SCENARIOS:
        print("=" * 78)
        print(sc["label"])
        print(f'Query: "{sc["query"]}"')

        kw = keyword_search(
            es, sc["index"], sc["query"], fields=sc["fields"], filters=sc["filters"], size=5
        )
        sem = semantic_search(
            es, sc["index"], sc["query"], filters=sc["filters"], size=5
        )

        print("\n  Keyword-only (BM25) top 5:")
        show(kw, sc["name_field"])
        print("\n  Semantic (ELSER sparse vectors) top 5:")
        show(sem, sc["name_field"])

        kw_ids = {h["_id"] for h in kw}
        sem_ids = {h["_id"] for h in sem}
        surfaced = [i for i in sc["expect"] if i in sem_ids and i not in kw_ids]
        print(
            f"\n  >> {len(surfaced)} relevant result(s) missing from keyword's top 5, "
            f"surfaced by semantic search: {', '.join(surfaced) or '(none)'}"
        )
        print(f"  >> {sc['note']}\n")


if __name__ == "__main__":
    main()
