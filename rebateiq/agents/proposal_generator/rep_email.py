"""
The territory-rep email path — the workflow the builder ran for years.

For email-channel custom programs (e.g. the Enbridge commercial boiler
retrofit), the contractor emails a completed equipment form to a named
territory representative, who returns the projected gas savings and the
approved incentive within 2-5 business days. The proposal waits on those
figures.

Demo vs. production:
- draft_submission_email() is real — it is the artifact the contractor
  reviews and sends.
- simulate_rep_reply() stands in for the 2-5 day wait so the demo runs in
  seconds. Production replaces it with a Gmail API watch + Pub/Sub push, and
  the reply parsing is done by the LLM with the deterministic validator below
  as a guard. The figures themselves are computed with the same physics the
  rep uses (consumption x efficiency delta), so the demo numbers are honest.
"""

import re

from .calc import savings_fraction
from .schemas import ContractorProfile, SiteVisit

# Demo stand-in for the rep's internal incentive rate.
SIMULATED_REP_RATE_CAD_PER_M3 = 0.35


def draft_submission_email(
    visit: SiteVisit, program: dict, contractor: ContractorProfile
) -> str:
    ex, new = visit.existing, visit.proposed
    return f"""To: Enbridge Territory Representative
From: {contractor.contact_name} <{contractor.email}>
Subject: Boiler Retrofit Incentive Submission — {visit.site_address}, {visit.city}

Hello,

Please find the completed equipment details for an incentive review under the
{program['program_name']}.

SITE
  Customer:            {visit.customer_name}
  Address:             {visit.site_address}, {visit.city}
  Building type:       {visit.building_type}
  Annual consumption:  {f'{visit.annual_gas_use_m3:,.0f}' if visit.annual_gas_use_m3 else 'see attached bills'} m3 (12-month billing)

EXISTING EQUIPMENT
  Make / model:        {ex.make} {ex.model}
  Serial:              {ex.serial or 'n/a'}
  Rated input:         {f'{ex.input_btuh:,} BTU/h' if ex.input_btuh else 'n/a'}
  Efficiency:          {ex.afue_pct:.0f}% AFUE
  Age:                 {ex.age_years} years

PROPOSED REPLACEMENT
  Make / model:        {new.make} {new.model} (x{new.quantity})
  Rated input:         {f'{new.input_btuh:,} BTU/h' if new.input_btuh else 'n/a'}
  Efficiency:          {new.afue_pct:.0f}% AFUE

Please confirm the projected annual gas savings and the approved incentive
amount for this retrofit at your earliest convenience.

Best regards,
{contractor.contact_name}
{contractor.company_name} | {contractor.phone}
"""


def simulate_rep_reply(visit: SiteVisit, program: dict) -> str:
    """DEMO ONLY — stands in for the rep's 2-5 business-day email reply."""
    use_m3 = visit.annual_gas_use_m3 or 0
    saved_m3 = use_m3 * savings_fraction(visit.existing.afue_pct, visit.proposed.afue_pct)
    rebate = saved_m3 * SIMULATED_REP_RATE_CAD_PER_M3
    return f"""Subject: RE: Boiler Retrofit Incentive Submission — {visit.site_address}, {visit.city}

Hello,

Thank you for the submission. We have completed the review of the proposed
retrofit at {visit.site_address} under the {program['program_name']}.

Based on the equipment details and consumption provided:

  Projected annual natural gas savings: {saved_m3:,.0f} m3
  Approved incentive amount: ${rebate:,.2f}

The incentive is confirmed for this project as scoped. Please retain this
email for your records and include the reference above with the post-install
documentation.

Regards,
Territory Representative, Commercial Programs
"""


REBATE_RE = re.compile(
    r"(?:incentive|rebate)\s+amount:?\s*\$\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE
)
SAVINGS_RE = re.compile(
    r"savings:?\s*([\d,]+(?:\.\d+)?)\s*m3", re.IGNORECASE
)


def parse_rep_reply(text: str) -> dict:
    """
    Deterministic extraction of the two figures the proposal needs.
    Raises ValueError when either is missing — a human gets the email instead.
    """
    rebate = REBATE_RE.search(text)
    savings = SAVINGS_RE.search(text)
    if not rebate or not savings:
        raise ValueError("Could not parse rebate/savings from rep reply — route to contractor.")
    return {
        "approved_rebate_cad": float(rebate.group(1).replace(",", "")),
        "projected_annual_savings_m3": float(savings.group(1).replace(",", "")),
    }
