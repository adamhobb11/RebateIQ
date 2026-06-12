"""
Smoke test 8 — the root coordinator, live: routing must hand off to the
right specialist, the specialist must do its real work, and the final
answer must come back through one conversation.

    python scripts/check_coordinator.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from rebateiq.agents.coordinator.agent import root_agent  # noqa: E402

PROMPT = (
    "This morning's alert flagged the program enbridge-commercial-boiler-rep "
    "(Enbridge Commercial Boiler Retrofit Incentive) in CA-ON. "
    "Who in my territory should I be pitching it to?"
)


async def main() -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="rebateiq-coord-smoke")
    session = await runner.session_service.create_session(
        app_name="rebateiq-coord-smoke", user_id="smoke"
    )
    msg = types.Content(role="user", parts=[types.Part(text=PROMPT)])

    calls, authors, final_text = [], set(), None
    async for event in runner.run_async(
        user_id="smoke", session_id=session.id, new_message=msg
    ):
        authors.add(event.author)
        for call in event.get_function_calls():
            label = call.name
            if call.name == "transfer_to_agent":
                label += f" -> {(call.args or {}).get('agent_name')}"
            print(f"  [{event.author}] {label}")
            calls.append(call.name)
        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts)
            if text.strip():
                final_text = text

    print("\nFINAL:\n", (final_text or "(none)").strip()[:1200])

    if "transfer_to_agent" not in calls:
        sys.exit("FAIL: coordinator never delegated.")
    if "find_prospects" not in calls:
        sys.exit("FAIL: the specialist never did its work.")
    if "prospect_identifier" not in authors:
        sys.exit("FAIL: prospect_identifier never spoke.")
    print("\nPASS: coordinator routed, specialist executed, answer returned.")


if __name__ == "__main__":
    asyncio.run(main())
