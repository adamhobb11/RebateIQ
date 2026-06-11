"""
RebateIQ — Program Monitor (Phase 1 foundation).

Phase 1 goal: prove that a Gemini agent can reach the Elasticsearch index
through the official Elastic MCP server. It can list indices, inspect
mappings, and run searches against the incentive-program corpus.

The real monitoring logic (DSIRE/NRCan polling, change detection, alerts)
is built in Phase 3 on top of this connection.
"""

import os
from dotenv import load_dotenv, find_dotenv

from google.adk.agents import Agent
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

# Load .env from the repo root regardless of where adk is launched.
load_dotenv(find_dotenv())

MODEL = os.environ.get("REBATEIQ_MODEL", "gemini-3.5-flash")

# Official Elastic MCP server, run as a Docker subprocess over stdio.
# (The npm package is deprecated; the Docker image is the supported path.)
elastic_mcp = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="docker",
            args=[
                "run", "-i", "--rm",
                "-e", "ES_URL",
                "-e", "ES_API_KEY",
                "docker.elastic.co/mcp/elasticsearch", "stdio",
            ],
            env={
                "ES_URL": os.environ["ES_URL"],
                "ES_API_KEY": os.environ["ES_API_KEY"],
            },
        ),
        timeout=60,
    ),
    # Phase 1: read-only surface is all we need.
    # tool_filter=["list_indices", "get_mappings", "search"],
)

root_agent = Agent(
    model=MODEL,
    name="program_monitor",
    description="Reads the RebateIQ incentive-program index in Elasticsearch.",
    instruction=(
        "You are the RebateIQ Program Monitor. You have Elasticsearch tools that "
        "can list indices, inspect field mappings, and run search queries against "
        "an index of HVAC government and utility incentive programs. When asked "
        "about programs, ALWAYS use the tools to retrieve real data rather than "
        "guessing. State which index and fields you used. Keep answers concise."
    ),
    tools=[elastic_mcp],
)
