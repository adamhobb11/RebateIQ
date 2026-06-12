"""
Smoke test 7 — the Response & Scheduling agent, live, over two turns.

Turn 1: the brief's exact prospect reply ("This looks interesting, can
someone come take a look?") -> expect semantic classification + three
proposed slots in a drafted reply.
Turn 2: the prospect picks option 2 -> expect a real .ics booking.

    python scripts/check_scheduling_agent.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from rebateiq.agents.appointment_booking.agent import root_agent  # noqa: E402

TURN_1 = (
    "Reply received from Dragan Petrovic, Building Superintendent, Maplewood "
    "Court Apartments (38 Maplewood Crt, Scarborough) — re: the Enbridge boiler "
    "retrofit campaign:\n\n"
    '"This looks interesting, can someone come take a look?"\n\n'
    "Handle it."
)
TURN_2 = "Dragan replied: option 2 works for him. Book it."


async def run_turn(runner, session_id, text, tool_calls, tool_results):
    msg = types.Content(role="user", parts=[types.Part(text=text)])
    final = None
    async for event in runner.run_async(
        user_id="smoke", session_id=session_id, new_message=msg
    ):
        for call in event.get_function_calls():
            print(f"  [tool] {call.name}")
            tool_calls.append(call.name)
        for resp in event.get_function_responses():
            tool_results.append((resp.name, resp.response))
        if event.is_final_response() and event.content and event.content.parts:
            final = "".join(p.text or "" for p in event.content.parts)
    return final


async def main() -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="rebateiq-sched-smoke")
    session = await runner.session_service.create_session(
        app_name="rebateiq-sched-smoke", user_id="smoke"
    )
    calls, results = [], []

    print("--- turn 1: prospect reply arrives")
    final1 = await run_turn(runner, session.id, TURN_1, calls, results)
    print("\nAGENT (turn 1):\n", (final1 or "").strip()[:1600])

    if "classify_prospect_reply" not in calls:
        sys.exit("FAIL: reply was never classified.")
    if "get_available_slots" not in calls:
        sys.exit("FAIL: no availability lookup.")
    if "book_appointment" in calls:
        sys.exit("FAIL: booked before the prospect confirmed a slot.")

    print("\n--- turn 2: prospect confirms option 2")
    final2 = await run_turn(runner, session.id, TURN_2, calls, results)
    print("\nAGENT (turn 2):\n", (final2 or "").strip()[:1600])

    if "book_appointment" not in calls:
        sys.exit("FAIL: no booking after confirmation.")
    booking = next((r for name, r in results if name == "book_appointment"), None)
    ics_path = (booking or {}).get("ics_path")
    if not ics_path or not Path(ics_path).exists():
        sys.exit(f"FAIL: booking returned no .ics on disk ({ics_path}).")
    print(f"\nPASS: classified -> proposed slots -> booked on confirmation -> {ics_path}")


if __name__ == "__main__":
    asyncio.run(main())
