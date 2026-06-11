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

## Two tool patterns, deliberately
- **Program Monitor** reaches Elasticsearch through the official Elastic MCP
  server — generic, exploratory tools (list indices, mappings, search).
- **Proposal Generator** uses typed Python function tools that wrap the shared
  hybrid query and the deterministic calc engine. Structured retrieval and
  money math should not be improvised by the model query-by-query; the LLM's
  job there is eligibility and stacking judgment, and every dollar figure
  comes from code.

## To refactor later
The Elastic MCP toolset is inlined in `program_monitor/agent.py` for Phase 1.
When the second agent needs it, lift it into `rebateiq/tools/elastic_mcp.py`
as a `build_elastic_mcp_toolset()` helper and make the package installable
(`pip install -e .`) so all agents import it.
