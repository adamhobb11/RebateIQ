"""
Smoke test 9 — the LIVE Google Calendar MCP backend.

Run AFTER creating the OAuth client (see README "Live calendar" section):
the first run opens a browser for the one-time Google consent, then the
agent must list real calendars through the MCP server.

    GOOGLE_OAUTH_CREDENTIALS=...  python scripts/check_calendar_mcp.py

Forces REBATEIQ_CALENDAR=mcp regardless of .env, so the default sim
config stays untouched.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["REBATEIQ_CALENDAR"] = "mcp"  # must be set before the agent module loads

from dotenv import find_dotenv, load_dotenv  # noqa: E402

load_dotenv(find_dotenv())

if not os.environ.get("GOOGLE_OAUTH_CREDENTIALS"):
    sys.exit(
        "GOOGLE_OAUTH_CREDENTIALS is not set.\n"
        "Point it at the Desktop-app OAuth client JSON (see README), e.g.\n"
        "  credentials/gcal-oauth-client.json"
    )

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from rebateiq.agents.appointment_booking import agent as booking_agent  # noqa: E402

PROMPT = (
    "List my calendars and tell me how many events are on the primary calendar "
    "in the next 7 days. Just the facts, no booking."
)


async def main() -> None:
    agent = booking_agent.build_agent()
    runner = InMemoryRunner(agent=agent, app_name="rebateiq-gcal-smoke")
    session = await runner.session_service.create_session(
        app_name="rebateiq-gcal-smoke", user_id="smoke"
    )
    msg = types.Content(role="user", parts=[types.Part(text=PROMPT)])

    tool_calls, final_text = [], None
    async for event in runner.run_async(
        user_id="smoke", session_id=session.id, new_message=msg
    ):
        for call in event.get_function_calls():
            print(f"  [tool] {call.name}")
            tool_calls.append(call.name)
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(p.text or "" for p in event.content.parts)

    print("\nAGENT:\n", (final_text or "(no final response)").strip()[:1200])
    calendar_tools = [t for t in tool_calls if t != "classify_prospect_reply"]
    if not calendar_tools:
        sys.exit("FAIL: no calendar MCP tools were called.")
    print(f"\nPASS: live Google Calendar reached via MCP ({', '.join(calendar_tools)}).")


if __name__ == "__main__":
    asyncio.run(main())
