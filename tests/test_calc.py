"""Unit tests for the deterministic proposal math — the no-hallucinated-numbers guarantee."""

import pytest

from rebateiq.agents.proposal_generator.calc import (
    annual_gas_use_m3,
    build_proposal_calc,
    incentive_for,
    savings_fraction,
)
from rebateiq.agents.proposal_generator.schemas import (
    ExistingEquipment,
    ProposedEquipment,
    SiteVisit,
)


def visit(**overrides) -> SiteVisit:
    base = dict(
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
            make="Viessmann", model="Vitodens 100-W B1HE-120", afue_pct=95,
            input_btuh=370_000, quantity=2,
        ),
        quoted_price_cad=58_000,
        annual_gas_use_m3=32_000,
        gas_rate_cad_per_m3=0.48,
    )
    base.update(overrides)
    return SiteVisit(**base)


# --- baseline + savings ------------------------------------------------------

def test_explicit_volume_wins():
    assert annual_gas_use_m3(visit()) == 32_000


def test_cost_derived_volume():
    v = visit(annual_gas_use_m3=None, annual_fuel_cost_cad=15_360)
    assert annual_gas_use_m3(v) == pytest.approx(32_000)


def test_missing_baseline_raises():
    with pytest.raises(ValueError):
        annual_gas_use_m3(visit(annual_gas_use_m3=None))


def test_savings_fraction():
    assert savings_fraction(72, 95) == pytest.approx(1 - 72 / 95)
    assert savings_fraction(95, 95) == 0.0
    assert savings_fraction(96, 90) == 0.0  # downgrade never shows negative savings


# --- per-classification incentive rules -------------------------------------

def test_prescriptive_flat_confirmed():
    program = {
        "program_id": "p1", "program_name": "Flat $500", "classification": "prescriptive",
        "incentive_basis": "flat", "incentive_rate": 500,
    }
    line = incentive_for(program, visit(), gas_saved_m3=1000)
    assert line.status == "confirmed"
    assert line.amount_cad == 500


def test_prescriptive_pre_approval_is_estimated():
    program = {
        "program_id": "p2", "program_name": "Gated", "classification": "prescriptive",
        "incentive_basis": "flat", "incentive_rate": 8000, "pre_approval_required": True,
    }
    assert incentive_for(program, visit(), 0).status == "estimated_pending_approval"


def test_prescriptive_per_unit_quantity():
    program = {
        "program_id": "p3", "program_name": "Per boiler", "classification": "prescriptive",
        "incentive_basis": "flat", "incentive_rate": 6000, "incentive_unit": "per_unit",
    }
    line = incentive_for(program, visit(), 0)  # proposed quantity = 2
    assert line.amount_cad == 12_000


def test_prescriptive_pct_of_cost_with_max():
    program = {
        "program_id": "p4", "program_name": "25C-style", "classification": "prescriptive",
        "incentive_basis": "pct_of_cost", "incentive_rate": 30, "incentive_max": 2000,
    }
    line = incentive_for(program, visit(), 0)
    assert line.amount_cad == 2000  # 30% of 58k blows through the cap


def test_prescriptive_no_rate_points_at_table():
    program = {
        "program_id": "p5", "program_name": "Tabled", "classification": "prescriptive",
        "incentive_basis": "flat",
    }
    line = incentive_for(program, visit(), 0)
    assert line.status == "see_program_table"
    assert line.amount_cad is None


def test_custom_rate_formula_and_caps():
    program = {
        "program_id": "c1", "program_name": "Custom $/m3", "classification": "custom_calculated",
        "incentive_basis": "per_unit_energy", "incentive_rate": 0.30,
        "incentive_unit": "m3_natural_gas_saved_annual",
        "incentive_pct_cap": 75, "incentive_max": 100_000, "pre_approval_required": True,
    }
    line = incentive_for(program, visit(), gas_saved_m3=7747.4)
    assert line.status == "estimated_pending_approval"
    assert line.amount_cad == pytest.approx(2324.22, abs=0.01)


def test_custom_max_cap_applies():
    program = {
        "program_id": "c2", "program_name": "Capped", "classification": "custom_calculated",
        "incentive_basis": "per_unit_energy", "incentive_rate": 10.0, "incentive_max": 5000,
    }
    assert incentive_for(program, visit(), 7747.4).amount_cad == 5000


def test_custom_without_rate_is_pending_rep_quote():
    program = {
        "program_id": "rep1", "program_name": "Rep path", "classification": "custom_calculated",
        "incentive_basis": "per_unit_energy",
    }
    line = incentive_for(program, visit(), 7747.4)
    assert line.status == "pending_rep_quote"
    assert line.amount_cad is None


def test_financing_line_has_terms_not_amount():
    program = {
        "program_id": "f1", "program_name": "Loan", "classification": "financing",
        "incentive_basis": "loan", "incentive_rate": 0, "incentive_max": 40_000,
    }
    line = incentive_for(program, visit(), 0)
    assert line.status == "financing"
    assert line.amount_cad is None
    assert line.loan_principal_cad == 40_000
    assert line.loan_rate_pct == 0


# --- full stack --------------------------------------------------------------

def stack_programs():
    return [
        {"program_id": "rep1", "program_name": "Rep path", "classification": "custom_calculated",
         "incentive_basis": "per_unit_energy"},
        {"program_id": "c1", "program_name": "Custom", "classification": "custom_calculated",
         "incentive_basis": "per_unit_energy", "incentive_rate": 0.30,
         "incentive_pct_cap": 75, "incentive_max": 100_000, "pre_approval_required": True},
        {"program_id": "f1", "program_name": "Loan", "classification": "financing",
         "incentive_basis": "loan", "incentive_rate": 4.5, "incentive_max": 125_000},
    ]


def test_full_calc_before_rep_reply():
    calc = build_proposal_calc(visit(), stack_programs())
    assert calc.annual_fuel_cost_cad == pytest.approx(15_360)
    assert calc.annual_savings_cad == pytest.approx(15_360 * (1 - 72 / 95), abs=0.01)
    assert calc.rebate_total_confirmed_cad == 0
    assert calc.rebate_total_estimated_cad == pytest.approx(2324.22, abs=0.01)
    # financing principal capped by quoted price, not program max
    loan = next(l for l in calc.incentives if l.status == "financing")
    assert loan.loan_principal_cad == 58_000
    # payback uses net of estimated rebates
    expected_net = 58_000 - calc.rebate_total_cad
    assert calc.net_cost_cad == pytest.approx(expected_net)
    assert calc.payback_years == pytest.approx(expected_net / calc.annual_savings_cad, abs=0.05)


def test_rep_quote_confirms_the_line():
    calc = build_proposal_calc(visit(), stack_programs(), rep_quotes={"rep1": 2711.58})
    rep = next(l for l in calc.incentives if l.program_id == "rep1")
    assert rep.status == "confirmed"
    assert rep.amount_cad == 2711.58
    assert calc.rebate_total_confirmed_cad == 2711.58
    assert calc.net_cost_cad == pytest.approx(58_000 - 2711.58 - calc.rebate_total_estimated_cad)


def test_no_savings_means_no_payback():
    v = visit(proposed=ProposedEquipment(make="X", model="Y", afue_pct=72))
    calc = build_proposal_calc(v, [])
    assert calc.annual_savings_cad == 0
    assert calc.payback_years is None
