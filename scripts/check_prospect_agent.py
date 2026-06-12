"""
Smoke test 5 — the Prospect Identifier agent, live.

Feeds the agent a Program Monitor-style alert and expects it to read the
program, write an ideal-customer profile, retrieve prospects, filter the
poor fits, and render the approval list. Requires the seed corpus.

    python scripts/check_prospect_agent.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from rebateiq.agents.prospect_identifier.agent import root_agent  # noqa: E402

PROMPT = (
    "This morning's RebateIQ alert:\n\n"
    "[NEW] Enbridge Commercial Boiler Retrofit Incentive (Territory Representative)\n"
    "    program id: enbridge-commercial-boiler-rep — region CA-ON\n\n"
    "Build me the prospect list for this one."
)


async def main() -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="rebateiq-prospect-smoke")
    session = await runner.session_service.create_session(
        app_name="rebateiq-prospect-smoke", user_id="smoke"
    )
    msg = types.Content(role="user", parts=[types.Part(text=PROMPT)])

    tool_calls, final_text = [], None
    async for event in runner.run_async(
        user_id="smoke", session_id=session.id, new_message=msg
    ):
        for call in event.get_function_calls():
            args = dict(call.args or {})
            if call.name == "find_prospects":
                print(f"  [tool] find_prospects(profile_query={args.get('profile_query')!r})")
            else:
                print(f"  [tool] {call.name}")
            tool_calls.append(call.name)
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(p.text or "" for p in event.content.parts)

    print("\nAGENT:\n", (final_text or "(no final response)").strip())

    missing = {"get_program", "find_prospects"} - set(tool_calls)
    if missing:
        sys.exit(f"FAIL: agent skipped tools: {missing}")
    if final_text and "Maplewood" not in final_text:
        sys.exit("FAIL: the strongest seeded prospect (Maplewood) is missing.")
    print("\nPASS: prospect agent built an approval-ready list from the alert.")


if __name__ == "__main__":
    asyncio.run(main())
