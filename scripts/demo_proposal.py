"""
The Proposal Generator storyline, end to end and deterministic (no LLM calls,
free to re-run): site visit -> program matching -> rep-email path -> money
math -> branded PDF. The live-agent version of the same flow (Gemini doing
the eligibility reasoning) is scripts/check_proposal_agent.py.

    python scripts/demo_proposal.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rebateiq.agents.proposal_generator import rep_email as rep  # noqa: E402
from rebateiq.agents.proposal_generator.calc import build_proposal_calc  # noqa: E402
from rebateiq.agents.proposal_generator.matching import match_programs  # noqa: E402
from rebateiq.agents.proposal_generator.pdf import render_proposal_pdf  # noqa: E402
from rebateiq.agents.proposal_generator.schemas import (  # noqa: E402
    ContractorProfile,
    ExistingEquipment,
    ProposedEquipment,
    SiteVisit,
)
from rebateiq.shared.es import get_client  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data/output/maplewood_proposal.pdf"

CONTRACTOR = ContractorProfile(
    company_name="Hobb Mechanical Ltd.",
    contact_name="Adam Hobb",
    phone="416-555-0147",
    email="adam@hobbmechanical.example",
)

VISIT = SiteVisit(
    customer_name="Maplewood Court Apartments",
    site_address="38 Maplewood Crt",
    city="Scarborough",
    region="CA-ON",
    building_type="38-suite low-rise apartment building",
    existing=ExistingEquipment(
        make="Laars", model="Mighty Therm 2", serial="MT2-9407-1182",
        afue_pct=72, age_years=21, input_btuh=400_000,
    ),
    proposed=ProposedEquipment(
        make="Viessmann", model="Vitodens 100-W B1HE-120",
        afue_pct=95, input_btuh=370_000, quantity=2,
    ),
    quoted_price_cad=58_000,
    annual_gas_use_m3=32_000,
    gas_rate_cad_per_m3=0.48,
)

# The agent makes this judgment live (see check_proposal_agent.py). Encoded
# here so the storyline is reproducible: the two Enbridge programs cover the
# same measure and don't stack — the territory-rep path wins (confirmed
# figures, no pre-install gate). The municipal loan is financing and stacks.
SELECTED = ["enbridge-commercial-boiler-rep", "toronto-energy-retrofit-loan"]


def banner(text: str) -> None:
    print("\n" + "=" * 78 + f"\n{text}\n" + "=" * 78)


def main() -> None:
    es = get_client()

    banner("1) SITE VISIT (contractor-entered)")
    print(f"  {VISIT.customer_name} — {VISIT.building_type}")
    print(f"  Existing: {VISIT.existing.make} {VISIT.existing.model}, "
          f"{VISIT.existing.afue_pct:.0f}% AFUE, {VISIT.existing.age_years} yrs")
    print(f"  Proposed: {VISIT.proposed.make} {VISIT.proposed.model} x{VISIT.proposed.quantity}, "
          f"{VISIT.proposed.afue_pct:.0f}% AFUE")
    print(f"  Quoted price: ${VISIT.quoted_price_cad:,.0f}  |  "
          f"Annual gas: {VISIT.annual_gas_use_m3:,.0f} m3")

    banner("2) PROGRAM MATCHING (hybrid retrieval over the live corpus)")
    candidates = match_programs(es, VISIT)
    for p in candidates:
        marker = "KEEP " if p["program_id"] in SELECTED else "  -  "
        print(f"  {marker} {p['program_id']:<32} {p['classification']:<18} "
              f"{p['submission_channel']}")
    print("  (eligibility + stacking judgment is the agent's job — the two Enbridge")
    print("   programs don't stack; the territory-rep path wins on confirmed figures)")

    rep_program = next(p for p in candidates
                       if p["program_id"] == "enbridge-commercial-boiler-rep")

    banner("3) REP SUBMISSION EMAIL (drafted for contractor review)")
    print(rep.draft_submission_email(VISIT, rep_program, CONTRACTOR))

    banner("4) REP REPLY (simulated — production waits 2-5 days on a Gmail watch)")
    reply = rep.simulate_rep_reply(VISIT, rep_program)
    print(reply)

    parsed = rep.parse_rep_reply(reply)
    print(f"  Parsed: rebate=${parsed['approved_rebate_cad']:,.2f}  "
          f"savings={parsed['projected_annual_savings_m3']:,.0f} m3/yr")

    banner("5) THE MONEY PICTURE (deterministic)")
    selected_docs = [p for p in candidates if p["program_id"] in SELECTED]
    calc = build_proposal_calc(
        VISIT, selected_docs,
        rep_quotes={"enbridge-commercial-boiler-rep": parsed["approved_rebate_cad"]},
    )
    print(f"  Heating cost today: ${calc.annual_fuel_cost_cad:,.0f}/yr  ->  "
          f"after: ${calc.new_annual_fuel_cost_cad:,.0f}/yr")
    print(f"  Savings: ${calc.annual_savings_cad:,.0f}/yr "
          f"({calc.annual_gas_saved_m3:,.0f} m3)")
    for line in calc.incentives:
        amount = f"${line.amount_cad:,.0f}" if line.amount_cad else \
            (f"${line.loan_principal_cad:,.0f} @ {line.loan_rate_pct:.1f}%"
             if line.status == "financing" else "—")
        print(f"  [{line.status}] {line.program_name}: {amount}")
    print(f"  Net investment: ${calc.net_cost_cad:,.0f}  |  "
          f"Payback: {calc.payback_years} yrs")

    banner("6) BRANDED PDF")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    path = render_proposal_pdf(VISIT, calc, CONTRACTOR, str(OUT))
    print(f"  {path}")
    print("\nDone — this is the document that closes the deal.")


if __name__ == "__main__":
    main()
