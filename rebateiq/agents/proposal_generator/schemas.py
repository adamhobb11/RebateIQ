"""
Canonical site-visit payload and proposal result models.

The site-visit fields mirror the form the builder used for years running
Enbridge boiler-retrofit submissions at Enercare: existing equipment
(make / model / serial / efficiency / age) plus proposed replacement
(make / model / rated efficiency). The contractor enters the quoted
installation price — RebateIQ never invents pricing.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

Classification = Literal["prescriptive", "custom_calculated", "financing"]
IncentiveStatus = Literal[
    "confirmed",                      # fixed published amount, no approval gate
    "estimated_pending_approval",     # formula-derived, program must approve first
    "pending_rep_quote",              # awaiting a territory rep's emailed figures
    "financing",                      # loan terms, not a rebate amount
    "see_program_table",              # published per-measure table, not in corpus
]


class ExistingEquipment(BaseModel):
    equipment_type: Literal["boiler", "furnace", "unit_heater"] = "boiler"
    fuel_type: Literal["natural_gas", "oil", "propane"] = "natural_gas"
    make: str
    model: str
    serial: Optional[str] = None
    afue_pct: float = Field(gt=30, lt=100, description="current efficiency, %")
    age_years: int = Field(ge=0)
    input_btuh: Optional[int] = Field(default=None, description="rating plate input")


class ProposedEquipment(BaseModel):
    make: str
    model: str
    afue_pct: float = Field(gt=30, le=100, description="rated efficiency, %")
    input_btuh: Optional[int] = None
    quantity: int = Field(default=1, ge=1, description="units installed, for per-unit rebates")


class SiteVisit(BaseModel):
    customer_name: str
    site_address: str
    city: str
    region: str = Field(default="CA-ON", description="region keyword, e.g. CA-ON")
    building_type: str = Field(description="e.g. '38-suite low-rise apartment building'")
    existing: ExistingEquipment
    proposed: ProposedEquipment
    quoted_price_cad: float = Field(gt=0, description="contractor-entered installed price")
    # Fuel baseline: give ONE of these (annual volume preferred — it comes off
    # real bills, which is how the rep-path submissions are done in practice).
    annual_gas_use_m3: Optional[float] = Field(default=None, gt=0)
    annual_fuel_cost_cad: Optional[float] = Field(default=None, gt=0)
    gas_rate_cad_per_m3: float = Field(
        default=0.48, gt=0, description="effective delivered rate; demo default, illustrative"
    )
    notes: Optional[str] = None


# Re-exported for existing imports; canonical home is rebateiq.shared.models.
from rebateiq.shared.models import ContractorProfile  # noqa: E402,F401


class IncentiveLine(BaseModel):
    program_id: str
    program_name: str
    classification: Classification
    status: IncentiveStatus
    amount_cad: Optional[float] = Field(default=None, description="None when not yet known")
    basis_note: str = Field(description="one line explaining how the amount was derived")
    # financing-only extras
    loan_principal_cad: Optional[float] = None
    loan_rate_pct: Optional[float] = None


class ProposalCalc(BaseModel):
    """Deterministic money math for the proposal. No LLM-generated numbers."""

    annual_gas_use_m3: float
    annual_fuel_cost_cad: float
    new_annual_fuel_cost_cad: float
    annual_savings_cad: float
    annual_gas_saved_m3: float
    savings_fraction: float

    incentives: list[IncentiveLine]
    rebate_total_confirmed_cad: float
    rebate_total_estimated_cad: float
    rebate_total_cad: float
    net_cost_cad: float
    payback_years: Optional[float]
