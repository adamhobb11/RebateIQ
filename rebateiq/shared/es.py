"""Shared Elasticsearch client + index names. One place for env handling."""

import os
from functools import lru_cache

from dotenv import find_dotenv, load_dotenv
from elasticsearch import Elasticsearch

load_dotenv(find_dotenv())

PROGRAMS_INDEX = os.environ.get("ES_PROGRAMS_INDEX", "rebate_programs")
LISTINGS_INDEX = os.environ.get("ES_LISTINGS_INDEX", "business_listings")


@lru_cache(maxsize=1)
def get_client() -> Elasticsearch:
    url = os.environ.get("ES_URL")
    api_key = os.environ.get("ES_API_KEY")
    if not url or not api_key:
        raise RuntimeError("ES_URL / ES_API_KEY missing — copy .env.example to .env")
    return Elasticsearch(url, api_key=api_key, request_timeout=60)
