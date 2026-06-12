# Architecture notes

## How agents reach Elasticsearch
Each agent uses ADK's `McpToolset` to spawn the official Elastic MCP server
(`docker.elastic.co/mcp/elasticsearch`, stdio mode) as a subprocess. ADK
discovers the server's tools (list_indices, get_mappings, search, etc.),
adapts them to native ADK tools, and proxies the LLM's tool calls to it.

The Elastic MCP npm package is deprecated; the Docker image is the supported
path as of v0.4.0+. Docker must be available wherever the agent runs (local
dev and, later, the Cloud Run container).

## Model selection
- `gemini-3.5-flash` — default for monitoring, classification, drafting
- `gemini-3.1-pro-preview` — the Proposal Generator's multi-program stacking
  logic where reasoning depth matters. (The brief's `gemini-3.1-pro` string
  does not exist on Vertex; validated against the live model list.)

## Monitoring is a scheduled scan, not a polling agent
The Program Monitor's alert logic (rebateiq/agents/program_monitor/alerts.py)
is a deterministic diff against the previous snapshot: new program ids,
funding-status transitions, deadlines entering the warning window. In
production a Cloud Scheduler job re-ingests DSIRE/NRCan/utility feeds and
runs the scan after each ingest, pushing the digest to the contractor; the
ADK agent is the conversational layer over the same index. The demo
(scripts/demo_monitor.py) simulates one overnight feed update and restores
the corpus afterwards. At DSIRE scale the scan pre-scopes candidates to the
contractor's equipment profile via the shared hybrid query.

## Two tool patterns, deliberately
- **Program Monitor** reaches Elasticsearch through the official Elastic MCP
  server — generic, exploratory tools (list indices, mappings, search).
- **Proposal Generator** uses typed Python function tools that wrap the shared
  hybrid query and the deterministic calc engine. Structured retrieval and
  money math should not be improvised by the model query-by-query; the LLM's
  job there is eligibility and stacking judgment, and every dollar figure
  comes from code.

## Multi-agent shape
A root coordinator (`rebateiq/agents/coordinator`) owns the five specialists
as ADK sub-agents and routes by request; control transfers to one specialist,
does the work with its own tools, and returns. Each specialist module exposes
`build_agent()` so the coordinator composes fresh instances while every agent
also remains runnable standalone in `adk web`. The coordinator is the single
entry point the demo UI and the Cloud Run deployment talk to.

## Calendar backend
The booking agent's calendar is a swappable backend behind one env flag:
- `REBATEIQ_CALENDAR=sim` (default): deterministic busy schedule, bookings
  written as real .ics files — demo-safe, no external account.
- `REBATEIQ_CALENDAR=mcp`: the live Google Calendar through the
  `@cocal/google-calendar-mcp` server (stdio via npx). Needs a Desktop-app
  OAuth client JSON (`GOOGLE_OAUTH_CREDENTIALS`) and a one-time browser
  consent; verify with `scripts/check_calendar_mcp.py`.

## Demo UI decision
The demo records in `adk web`: the events pane shows coordinator handoffs
and every tool call — the architecture is the show. The artifacts carry the
visual story (branded proposal PDF, .ics invites, outbox emails, the alert
digest). A custom web UI was considered and consciously skipped: it adds
build time without adding evidence.

## To refactor later
The Elastic MCP toolset is inlined in `program_monitor/agent.py` for Phase 1.
When the second agent needs it, lift it into `rebateiq/tools/elastic_mcp.py`
as a `build_elastic_mcp_toolset()` helper and make the package installable
(`pip install -e .`) so all agents import it.
