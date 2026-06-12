"""Models shared across agents."""

from pydantic import BaseModel, Field


class ContractorProfile(BaseModel):
    """The contractor whose brand goes on outbound email and the proposal PDF."""

    company_name: str
    contact_name: str
    phone: str
    email: str
    brand_hex: str = Field(default="#1B5E8A", description="header colour on the PDF")
