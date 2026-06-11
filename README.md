# RebateIQ

HVAC incentive intelligence & sales automation — a five-agent system built on
Google Cloud Agent Builder (ADK), Gemini, and the Elastic MCP server.

## Agents
1. **Program Monitor** — indexes DSIRE/NRCan, alerts on new/changing programs
2. **Prospect Identifier** — builds a targeted B2B prospect list
3. **Outreach** — drafts and sends a compliant cold email campaign
4. **Appointment Booking** — handles replies, books site visits via Calendar MCP
5. **Proposal Generator** — calculates rebates/savings, generates the branded PDF

## Stack
Python · Google ADK + Gemini (`gemini-3.5-flash` default) · Elasticsearch
(Elastic Cloud Serverless) via the Elastic MCP server · Cloud Run · SendGrid
· Google Calendar MCP.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # then fill in real values

# Gemini auth is Vertex AI via gcloud ADC (no API key):
gcloud auth login && gcloud auth application-default login
```

Verify connections in order (each isolates one failure domain):
```bash
python scripts/check_elasticsearch.py    # 1. ES creds only
python scripts/check_gemini.py           # 2. Gemini auth only
python scripts/check_agent_e2e.py        # 3. full chain: ADK → Gemini → Elastic MCP (Docker) → ES
```

Load the seed corpus and see the semantic-vs-keyword receipts:
```bash
python scripts/seed_corpus.py --recreate
python scripts/demo_semantic_vs_keyword.py
```

Run the Program Monitor agent interactively (requires Docker for the Elastic MCP server):
```bash
adk web rebateiq/agents          # opens a local chat UI; pick "program_monitor"
# or headless:
adk run rebateiq/agents/program_monitor
```
Ask it: *"What indices exist?"* or *"Which Ontario programs apply to a condensing boiler retrofit?"*

## License
MIT
