"""
Smoke test 1 — Elasticsearch connectivity.

Run this FIRST. It bypasses Gemini and MCP entirely so that if it fails,
you know the problem is your ES_URL / ES_API_KEY, not the agent layer.

    python scripts/check_elasticsearch.py
"""

import os
import sys
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()

url = os.environ.get("ES_URL")
api_key = os.environ.get("ES_API_KEY")
if not url or not api_key:
    sys.exit("Missing ES_URL or ES_API_KEY in .env")

es = Elasticsearch(url, api_key=api_key, request_timeout=30)

try:
    if not es.ping():
        sys.exit("ping() failed — check the URL and API key.")
    print("Elasticsearch reachable.")
    try:
        info = es.info()
        print("  version:", info.get("version", {}).get("number", "n/a (serverless)"))
    except Exception:
        pass  # Serverless may not expose info(); ping is enough.

    indices = sorted(es.indices.get_alias(index="*").keys())
    if indices:
        print("  indices:", ", ".join(indices))
    else:
        print("  no indices yet — that's expected before Phase 1 indexing.")
except Exception as e:
    sys.exit(f"Connection error: {e}")
