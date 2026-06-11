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

## Phase 1 setup
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # then fill in real values
```

Verify connections in order (each isolates one failure domain):
```bash
python scripts/check_elasticsearch.py    # 1. ES creds only
python scripts/check_gemini.py           # 2. Gemini creds only
```

Then run the Program Monitor agent (requires Docker for the Elastic MCP server):
```bash
adk web rebateiq/agents          # opens a local chat UI; pick "program_monitor"
# or headless:
adk run rebateiq/agents/program_monitor
```
Ask it: *"What indices exist?"* or *"Describe the rebate_programs index."*

## License
MIT
