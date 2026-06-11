"""
Retrieval helpers shared by all RebateIQ agents.

Three modes over the same index:
- keyword_search:  BM25 only (the baseline a small contractor's tooling would have)
- semantic_search: ELSER sparse-vector only, via the semantic_text field
- hybrid_search:   reciprocal-rank fusion of both — the production default

Both seed indices copy their human-readable text fields into one
`semantic_combined` semantic_text field, so these helpers work unchanged on
`rebate_programs` and `business_listings`.
"""

from elasticsearch import Elasticsearch

SEMANTIC_FIELD = "semantic_combined"

PROGRAM_TEXT_FIELDS = ["program_name", "description", "eligible_equipment"]
LISTING_TEXT_FIELDS = [
    "business_name",
    "description",
    "building_type",
    "heating_system",
    "contact_title",
]


def _bool_query(must: dict, filters: list[dict] | None) -> dict:
    if not filters:
        return must
    return {"bool": {"must": [must], "filter": filters}}


def keyword_search(
    es: Elasticsearch,
    index: str,
    query: str,
    *,
    fields: list[str],
    filters: list[dict] | None = None,
    size: int = 5,
) -> list[dict]:
    body = _bool_query({"multi_match": {"query": query, "fields": fields}}, filters)
    resp = es.search(index=index, query=body, size=size, source_excludes=[SEMANTIC_FIELD])
    return resp["hits"]["hits"]


def semantic_search(
    es: Elasticsearch,
    index: str,
    query: str,
    *,
    filters: list[dict] | None = None,
    size: int = 5,
) -> list[dict]:
    body = _bool_query({"semantic": {"field": SEMANTIC_FIELD, "query": query}}, filters)
    resp = es.search(index=index, query=body, size=size, source_excludes=[SEMANTIC_FIELD])
    return resp["hits"]["hits"]


def hybrid_search(
    es: Elasticsearch,
    index: str,
    query: str,
    *,
    fields: list[str],
    filters: list[dict] | None = None,
    size: int = 5,
) -> list[dict]:
    """BM25 + ELSER fused with reciprocal rank fusion (RRF)."""
    retriever = {
        "rrf": {
            "retrievers": [
                {
                    "standard": {
                        "query": _bool_query(
                            {"multi_match": {"query": query, "fields": fields}}, filters
                        )
                    }
                },
                {
                    "standard": {
                        "query": _bool_query(
                            {"semantic": {"field": SEMANTIC_FIELD, "query": query}},
                            filters,
                        )
                    }
                },
            ],
            "rank_window_size": 50,
        }
    }
    resp = es.search(
        index=index, retriever=retriever, size=size, source_excludes=[SEMANTIC_FIELD]
    )
    return resp["hits"]["hits"]
