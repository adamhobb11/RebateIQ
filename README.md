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

Run the Program Monitor's alert scan — a simulated overnight feed update
fires new-program / funding-change / deadline alerts, then restores the corpus:
```bash
python scripts/demo_monitor.py
```

Run the Prospect Identifier — incentive program in, approval-ready list out:
```bash
python scripts/demo_prospects.py         # deterministic (no LLM)
python scripts/check_prospect_agent.py   # live agent: Gemini writes the customer profile
```

Run the Outreach agent — approved prospects in, CASL-validated campaign out:
```bash
python scripts/demo_outreach.py          # deterministic; queues the simulated send
python scripts/check_outreach_agent.py   # live agent: drafts copy, holds for approval
```

Run Response & Scheduling — prospect reply in, booked .ics out:
```bash
python scripts/demo_scheduling.py        # semantic classification runs live
python scripts/check_scheduling_agent.py # live agent, two turns: propose then book
```

Run the Proposal Generator — site visit in, branded PDF out:
```bash
python scripts/demo_proposal.py          # deterministic end-to-end storyline (no LLM)
python scripts/check_proposal_agent.py   # live agent: Gemini does the eligibility reasoning
```

Run the whole team — the root coordinator hands off across all five agents:
```bash
python scripts/check_coordinator.py      # live routing smoke
adk web rebateiq/agents                  # chat UI; pick "coordinator" (Docker needed
                                         # for the Elastic MCP in program_monitor)
```
Ask it: *"What changed in Ontario programs?"*, *"Who should I pitch the Enbridge
boiler incentive to?"*, or paste site-visit data and ask for the proposal.

### Live calendar (optional)
The booking agent defaults to a simulated calendar that writes real `.ics`
files. To book on a real Google Calendar via MCP:
1. Google Cloud console → enable the **Google Calendar API**; configure the
   OAuth consent screen (External, add yourself as a test user).
2. Credentials → **Create OAuth client ID → Desktop app** → download the JSON
   to `credentials/gcal-oauth-client.json` (gitignored).
3. Set in `.env`: `REBATEIQ_CALENDAR=mcp` and
   `GOOGLE_OAUTH_CREDENTIALS=<absolute path to that JSON>`.
4. `python scripts/check_calendar_mcp.py` — the first run opens the browser
   for the one-time consent, then must list your real calendars.

## License
MIT
