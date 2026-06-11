"""
Smoke test 4 — the Proposal Generator agent, live.

One conversational turn that should trigger match_incentive_programs and an
eligibility judgment. Requires the seed corpus (scripts/seed_corpus.py).

    python scripts/check_proposal_agent.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from rebateiq.agents.proposal_generator.agent import root_agent  # noqa: E402

SITE_VISIT = {
    "customer_name": "Maplewood Court Apartments",
    "site_address": "38 Maplewood Crt",
    "city": "Scarborough",
    "region": "CA-ON",
    "building_type": "38-suite low-rise apartment building",
    "existing": {
        "equipment_type": "boiler", "fuel_type": "natural_gas",
        "make": "Laars", "model": "Mighty Therm 2", "serial": "MT2-9407-1182",
        "afue_pct": 72, "age_years": 21, "input_btuh": 400000,
    },
    "proposed": {
        "make": "Viessmann", "model": "Vitodens 100-W B1HE-120",
        "afue_pct": 95, "input_btuh": 370000, "quantity": 2,
    },
    "quoted_price_cad": 58000,
    "annual_gas_use_m3": 32000,
    "gas_rate_cad_per_m3": 0.48,
}

PROMPT = (
    "Here is the site visit data:\n"
    f"{json.dumps(SITE_VISIT, indent=1)}\n\n"
    "Find the candidate incentive programs and tell me which ones this job is "
    "actually eligible for, with one line of reasoning each. Don't calculate "
    "anything yet."
)


async def main() -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="rebateiq-proposal-smoke")
    session = await runner.session_service.create_session(
        app_name="rebateiq-proposal-smoke", user_id="smoke"
    )
    msg = types.Content(role="user", parts=[types.Part(text=PROMPT)])

    tool_calls, final_text = [], None
    async for event in runner.run_async(
        user_id="smoke", session_id=session.id, new_message=msg
    ):
        for call in event.get_function_calls():
            tool_calls.append(call.name)
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(p.text or "" for p in event.content.parts)

    print("Tools called:", ", ".join(tool_calls) or "(none)")
    print("\nAGENT:\n", (final_text or "(no final response)").strip())
    if "match_incentive_programs" not in tool_calls:
        sys.exit("FAIL: agent did not call match_incentive_programs.")
    print("\nPASS: proposal agent matched programs and reasoned about eligibility.")


if __name__ == "__main__":
    asyncio.run(main())
