"""
Deterministic energy-savings and incentive math.

Every customer-facing dollar figure in a RebateIQ proposal comes from this
module — never from the LLM. Formulas follow the project brief:

    annual savings = current annual fuel cost x (1 - AFUE_old / AFUE_new)
    payback (yrs)  = net cost after rebates / annual savings

Incentive amounts are derived from the structured fields indexed with each
program (incentive_basis / rate / unit / pct_cap / max / cost_basis) and are
labelled confirmed vs. estimated-pending-approval vs. pending-rep-quote per
the Entry 008 program-structure research.
"""

from typing import Optional

from .schemas import IncentiveLine, ProposalCalc, SiteVisit

# First-order market reference for financing comparisons (illustrative).
MARKET_LOAN_RATE_PCT = 7.0


def annual_gas_use_m3(visit: SiteVisit) -> float:
    """Baseline consumption: explicit volume beats cost-derived volume."""
    if visit.annual_gas_use_m3:
        return visit.annual_gas_use_m3
    if visit.annual_fuel_cost_cad:
        return visit.annual_fuel_cost_cad / visit.gas_rate_cad_per_m3
    raise ValueError(
        "Site visit needs annual_gas_use_m3 or annual_fuel_cost_cad "
        "(read it off the customer's gas bills)."
    )


def savings_fraction(old_afue_pct: float, new_afue_pct: float) -> float:
    if new_afue_pct <= old_afue_pct:
        return 0.0
    return 1.0 - (old_afue_pct / new_afue_pct)


def incentive_for(program: dict, visit: SiteVisit, gas_saved_m3: float) -> IncentiveLine:
    """Apply one program's structured incentive formula to this job."""
    classification = program["classification"]
    basis = program.get("incentive_basis")
    rate = program.get("incentive_rate")
    pct_cap = program.get("incentive_pct_cap")
    max_amt = program.get("incentive_max")
    pre_approval = bool(program.get("pre_approval_required"))
    price = visit.quoted_price_cad

    common = {
        "program_id": program["program_id"],
        "program_name": program["program_name"],
        "classification": classification,
    }

    if classification == "financing":
        principal = min(price, max_amt) if max_amt else price
        loan_rate = rate if rate is not None else 0.0
        saving_vs_market = principal * (MARKET_LOAN_RATE_PCT - loan_rate) / 100.0
        return IncentiveLine(
            **common,
            status="financing",
            amount_cad=None,
            loan_principal_cad=round(principal, 2),
            loan_rate_pct=loan_rate,
            basis_note=(
                f"Financing, not a rebate: up to ${principal:,.0f} at {loan_rate:.1f}% "
                f"≈ ${saving_vs_market:,.0f}/yr less interest than a "
                f"{MARKET_LOAN_RATE_PCT:.0f}% market loan (first-order, average balance)."
            ),
        )

    if classification == "prescriptive":
        if rate is None:
            return IncentiveLine(
                **common,
                status="see_program_table",
                amount_cad=None,
                basis_note="Published per-measure table; look up the exact measure amount.",
            )
        unit = program.get("incentive_unit", "per_installation")
        qty = visit.proposed.quantity if unit == "per_unit" else 1
        amount = rate * qty
        if max_amt:
            amount = min(amount, max_amt)
        status = "estimated_pending_approval" if pre_approval else "confirmed"
        note = f"Fixed published amount: ${rate:,.0f} x {qty}" if qty > 1 else \
            f"Fixed published amount: ${rate:,.0f}"
        if basis == "pct_of_cost":
            amount = price * rate / 100.0
            if pct_cap:
                amount = min(amount, price * pct_cap / 100.0)
            if max_amt:
                amount = min(amount, max_amt)
            note = f"{rate:.0f}% of ${price:,.0f}" + (f", capped at ${max_amt:,.0f}" if max_amt else "")
        return IncentiveLine(
            **common, status=status, amount_cad=round(amount, 2), basis_note=note
        )

    # custom_calculated
    if rate is None:
        return IncentiveLine(
            **common,
            status="pending_rep_quote",
            amount_cad=None,
            basis_note=(
                "Program representative returns the approved amount from submitted "
                "equipment specs (typically 2-5 business days)."
            ),
        )
    amount = rate * gas_saved_m3
    caps = []
    if pct_cap:
        cost_base = price  # incremental cost basis would need the like-for-like quote
        capped = cost_base * pct_cap / 100.0
        if amount > capped:
            amount = capped
            caps.append(f"{pct_cap:.0f}% of cost")
    if max_amt and amount > max_amt:
        amount = max_amt
        caps.append(f"${max_amt:,.0f} program max")
    note = f"${rate:.2f} x {gas_saved_m3:,.0f} {program.get('incentive_unit', 'units')}"
    if caps:
        note += f" (capped: {', '.join(caps)})"
    return IncentiveLine(
        **common,
        status="estimated_pending_approval",
        amount_cad=round(amount, 2),
        basis_note=note + "; subject to program approval.",
    )


def build_proposal_calc(
    visit: SiteVisit,
    programs: list[dict],
    rep_quotes: Optional[dict[str, float]] = None,
) -> ProposalCalc:
    """
    The full money picture for one job.

    rep_quotes: {program_id: approved_amount} for email-channel programs whose
    figures have come back from the territory rep — those lines become confirmed.
    """
    rep_quotes = rep_quotes or {}

    use_m3 = annual_gas_use_m3(visit)
    cost_now = use_m3 * visit.gas_rate_cad_per_m3
    frac = savings_fraction(visit.existing.afue_pct, visit.proposed.afue_pct)
    saved_cad = cost_now * frac
    saved_m3 = use_m3 * frac

    lines: list[IncentiveLine] = []
    for program in programs:
        line = incentive_for(program, visit, saved_m3)
        quote = rep_quotes.get(line.program_id)
        if quote is not None and line.status == "pending_rep_quote":
            line = line.model_copy(
                update={
                    "status": "confirmed",
                    "amount_cad": round(quote, 2),
                    "basis_note": "Approved amount returned by the program representative.",
                }
            )
        lines.append(line)

    confirmed = sum(l.amount_cad or 0 for l in lines if l.status == "confirmed")
    estimated = sum(
        l.amount_cad or 0 for l in lines if l.status == "estimated_pending_approval"
    )
    total = confirmed + estimated
    net = visit.quoted_price_cad - total
    payback = round(net / saved_cad, 1) if saved_cad > 0 else None

    return ProposalCalc(
        annual_gas_use_m3=round(use_m3, 1),
        annual_fuel_cost_cad=round(cost_now, 2),
        new_annual_fuel_cost_cad=round(cost_now - saved_cad, 2),
        annual_savings_cad=round(saved_cad, 2),
        annual_gas_saved_m3=round(saved_m3, 1),
        savings_fraction=round(frac, 4),
        incentives=lines,
        rebate_total_confirmed_cad=round(confirmed, 2),
        rebate_total_estimated_cad=round(estimated, 2),
        rebate_total_cad=round(total, 2),
        net_cost_cad=round(net, 2),
        payback_years=payback,
    )
