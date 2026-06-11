# RebateIQ data

## Layout
- `mappings/` — index mappings, the source of truth for both indices.
  `semantic_text` is pinned to the managed EIS ELSER endpoint
  (`.elser-2-elastic`); human-readable text fields `copy_to` one
  `semantic_combined` field so BM25 and semantic retrieval share an index.
- `seed/` — the committed seed corpus (see below).

## The seed corpus

`seed/rebate_programs.json` (19 programs) and `seed/business_listings.json`
(20 prospects) are **demo data, deliberately engineered**, not live program
feeds:

- **Figures are illustrative snapshots.** Program structures (classification,
  submission channel, pre-approval gates, incentive formulas) follow real
  Ontario/US program research; dollar amounts and rates are plausible
  placeholders and must not be quoted to customers. Production ingestion
  from DSIRE/NRCan is a later phase.
- **Terminology variation is intentional.** The same equipment and the same
  decision-maker are described in different vocabularies across documents
  ("condensing boiler / minimum 90% AFUE" vs. "furnace with secondary heat
  exchanger"; "property manager, 40-unit residential complex" vs. "building
  superintendent, multi-family dwelling"). This is the test bed proving that
  semantic retrieval surfaces matches keyword search misses — run
  `python scripts/demo_semantic_vs_keyword.py` for the receipts.
- **PII-free by design.** Every listing, contact, and email address is
  fictional (`example.com`). Distractor listings (a data centre, a new-build
  tower on heat pumps, an EV fleet depot) are included so ranking quality is
  measurable, not assumed.

## Reload from scratch

```bash
python scripts/seed_corpus.py --recreate
```

Rebuilds both indices from `mappings/` and reloads the corpus in seconds —
losing the cluster (e.g. a lapsed trial) costs minutes, not days.
