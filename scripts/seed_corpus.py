"""
(Re)create the RebateIQ indices and load the seed corpus.

    python scripts/seed_corpus.py             # create-if-missing, then load
    python scripts/seed_corpus.py --recreate  # drop, recreate from mappings, reload

The seed corpus is PII-free and reproducible by design — wiping the cluster
(or losing a trial deployment) costs minutes, not days. ELSER embeddings are
generated at index time via the cluster's managed inference endpoint, so the
bulk load takes a little longer than plain indexing.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from elasticsearch import helpers

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rebateiq.shared.es import (  # noqa: E402
    INTENTS_INDEX,
    LISTINGS_INDEX,
    PROGRAMS_INDEX,
    get_client,
)

ROOT = Path(__file__).resolve().parents[1]

CORPORA = [
    {
        "index": PROGRAMS_INDEX,
        "mapping": ROOT / "data/mappings/rebate_programs.json",
        "seed": ROOT / "data/seed/rebate_programs.json",
        "id_field": "program_id",
    },
    {
        "index": LISTINGS_INDEX,
        "mapping": ROOT / "data/mappings/business_listings.json",
        "seed": ROOT / "data/seed/business_listings.json",
        "id_field": "listing_id",
    },
    {
        "index": INTENTS_INDEX,
        "mapping": ROOT / "data/mappings/reply_intents.json",
        "seed": ROOT / "data/seed/reply_intents.json",
        "id_field": "exemplar_id",
    },
]


def load(es, spec, recreate: bool) -> None:
    index = spec["index"]
    exists = es.indices.exists(index=index)

    if exists and recreate:
        es.indices.delete(index=index)
        print(f"[{index}] deleted")
        exists = False

    if not exists:
        mapping = json.loads(spec["mapping"].read_text())
        es.indices.create(index=index, **mapping)
        print(f"[{index}] created from {spec['mapping'].name}")

    docs = json.loads(spec["seed"].read_text())
    actions = [
        {"_index": index, "_id": doc[spec["id_field"]], "_source": doc}
        for doc in docs
    ]
    t0 = time.time()
    ok, errors = helpers.bulk(
        es, actions, chunk_size=8, request_timeout=180, raise_on_error=False
    )
    if errors:
        for err in errors[:3]:
            print(f"[{index}] ERROR: {err}")
        sys.exit(f"[{index}] bulk load had {len(errors)} errors")

    es.indices.refresh(index=index)
    count = es.count(index=index)["count"]
    print(f"[{index}] indexed {ok} docs in {time.time() - t0:.1f}s — count={count}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recreate", action="store_true", help="drop and recreate the indices first"
    )
    args = parser.parse_args()

    es = get_client()
    for spec in CORPORA:
        load(es, spec, recreate=args.recreate)
    print("Seed corpus loaded.")


if __name__ == "__main__":
    main()
