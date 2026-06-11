"""
Smoke test 3 — the full agent chain, end to end:

    ADK runner -> Gemini (Vertex + ADC) -> Elastic MCP server (Docker, stdio) -> Elasticsearch

Run AFTER check_elasticsearch.py and check_gemini.py are green, with Docker running:

    python scripts/check_agent_e2e.py

Success looks like the agent answering with real index names it retrieved
through MCP tool calls (not from its own imagination).
"""

import asyncio
import sys
from pathlib import Path

# Make the repo importable when run as `python scripts/check_agent_e2e.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from rebateiq.agents.program_monitor.agent import root_agent  # noqa: E402

PROMPT = (
    "List the indices that exist in the Elasticsearch cluster, then tell me "
    "how many documents the rebate_programs index holds."
)


async def main() -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="rebateiq-smoke")
    session = await runner.session_service.create_session(
        app_name="rebateiq-smoke", user_id="smoke"
    )
    message = types.Content(role="user", parts=[types.Part(text=PROMPT)])

    tool_calls: list[str] = []
    final_text: str | None = None

    async for event in runner.run_async(
        user_id="smoke", session_id=session.id, new_message=message
    ):
        for call in event.get_function_calls():
            tool_calls.append(call.name)
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(p.text or "" for p in event.content.parts)

    print("MCP tools called:", ", ".join(tool_calls) or "(none)")
    print("AGENT:", (final_text or "").strip() or "(no final response)")

    if not final_text:
        sys.exit("FAIL: agent produced no final response.")
    if not tool_calls:
        sys.exit("FAIL: agent answered without calling any MCP tool.")
    print("PASS: full ADK -> Gemini -> Elastic MCP -> ES chain is working.")


if __name__ == "__main__":
    asyncio.run(main())
