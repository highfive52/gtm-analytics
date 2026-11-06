from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OpportunityStage = Literal[
    "qualification",
    "discovery",
    "evaluation",
    "proposal",
    "negotiation",
    "closed_won",
    "closed_lost",
]


class OpportunitySnapshot(BaseModel):
    """Validated weekly snapshot of an opportunity's state."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    opportunity_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    snapshot_date: date
    stage: OpportunityStage
    amount: Decimal = Field(ge=0)
