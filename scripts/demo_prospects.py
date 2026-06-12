"""
The Prospect Identifier storyline, deterministic (no LLM, free to re-run):
incentive program -> ideal-customer profile -> ranked, approval-ready
prospect list. The live-agent version (Gemini writes the profile and filters
fits itself) is scripts/check_prospect_agent.py.

    python scripts/demo_prospects.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rebateiq.agents.prospect_identifier.prospecting import (  # noqa: E402
    format_approval_list,
    rank_prospects,
)
from rebateiq.shared.es import get_client  # noqa: E402

PROGRAM_NAME = "Enbridge Commercial Boiler Retrofit Incentive (Territory Representative)"

# The agent writes this live from the program's eligibility language
# (see check_prospect_agent.py); pinned here so the storyline is reproducible.
PROFILE = (
    "multi-unit residential building heated by an old natural gas boiler "
    "plant with rising heating costs"
)


def main() -> None:
    es = get_client()
    print(f"Program: {PROGRAM_NAME}")
    print(f'Ideal-customer profile: "{PROFILE}"\n')

    prospects = rank_prospects(es, PROFILE, region="CA-ON", size=8)
    print(format_approval_list(prospects, PROGRAM_NAME, "Ontario"))

    distractors = {"northshore-colocation", "glasshouse-residences", "velocity-courier-depot"}
    leaked = [p.listing_id for p in prospects if p.listing_id in distractors]
    print(f"\nDistractor check (data centre / new-build VRF tower / EV depot): "
          f"{'LEAKED: ' + ', '.join(leaked) if leaked else 'none surfaced — ranking holds.'}")


if __name__ == "__main__":
    main()
