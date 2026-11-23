from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

Ref = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=400)]
Units = Annotated[int, Field(ge=0, le=10_000_000)]


class Dispatch(BaseModel):
    disposition_id: int = Field(gt=0)
    dispatch_ref: Ref
    carrier: Ref
    tracking: Ref


class Receipt(BaseModel):
    vendor_qty: Units
    vendor_ref: Ref
    vendor_note: Note


class Resolution(BaseModel):
    settled_qty: Units
    resolution_ref: Ref
    resolution_note: Note


class Credit(BaseModel):
    proposal_ref: Ref
    unit_price_cents: int = Field(gt=0, le=10_000_000)
    freight_cents: int = Field(ge=0, le=100_000_000)
    note: Note


class CreditDecision(BaseModel):
    decision: Literal['accepted','rejected']
    review_note: Note
    acknowledged_ref: Ref | None = None
