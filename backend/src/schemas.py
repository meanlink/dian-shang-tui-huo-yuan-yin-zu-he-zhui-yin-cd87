from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Code = Annotated[str, StringConstraints(pattern=r'^[A-Z0-9][A-Z0-9-]{1,31}$')]
Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=6, max_length=1000)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Login(Input):
    login: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
    password: Annotated[str, StringConstraints(max_length=150)]


class BatchInput(Input):
    code: Code
    sku: Code
    product: Line
    supplier: Line
    received_on: date
    delivered_qty: int = Field(gt=0, le=1_000_000)


class SourceInput(Input):
    batch_code: Code | None = None
    symptoms: set[Code] = Field(min_length=1, max_length=8)


class CaseInput(SourceInput):
    ticket: Code
    order_ref: Code
    sku: Code
    opened_on: date
    detail: Note


class CaseCorrection(SourceInput):
    revision: int = Field(ge=1)


class Inspection(Input):
    revision: int = Field(ge=1)
    finding: Code
    inspection_ref: Line


class RunInput(Input):
    batch_code: Code
    from_date: date
    through_date: date

    @model_validator(mode='after')
    def valid_window(self):
        if not 0 <= (self.through_date - self.from_date).days <= 89:
            raise ValueError('追因窗口必须在 1 至 90 天之间')
        return self


class Decision(StrEnum):
    CONFIRM = 'confirm'
    DISMISS = 'dismiss'


class Review(Input):
    decision: Decision
    note: Note
    directive: Note | None = None
    due_on: date | None = None

    @model_validator(mode='after')
    def complete_assignment(self):
        if self.decision == Decision.CONFIRM and (self.directive is None or self.due_on is None):
            raise ValueError('确认根因时请填写整改要求和期限')
        return self


class WorkStatus(StrEnum):
    ASSIGNED = 'assigned'
    WORKING = 'working'
    VERIFICATION = 'verification'
    CLOSED = 'closed'


class WorkAction(StrEnum):
    ACCEPT = 'accept'
    SUBMIT = 'submit'
    RETURN = 'return'
    CLOSE = 'close'


class WorkUpdate(Input):
    action: WorkAction
    note: Note | None = None
    proof_ref: Line | None = None


WarehouseRef = Annotated[str, StringConstraints(pattern=r'^[A-Za-z0-9][A-Za-z0-9-]{2,39}$')]
Quantity = Annotated[int, Field(gt=0, le=1_000_000)]


class HoldStatus(StrEnum):
    HELD = 'held'
    CLEARED = 'cleared'


class DispositionKind(StrEnum):
    RELEASE = 'release'
    SCRAP = 'scrap'
    VENDOR_RETURN = 'vendor_return'


class ReinspectionOutcome(StrEnum):
    PASS = 'pass'
    FAIL = 'fail'


class HoldInput(Input):
    improvement_id: Annotated[int, Field(gt=0)]
    hold_ref: WarehouseRef
    held_qty: Quantity
    note: Note


class DispositionInput(Input):
    kind: DispositionKind
    quantity: Quantity
    disposition_ref: WarehouseRef
    note: Note


class ReinspectionInput(Input):
    submission_id: Annotated[int, Field(gt=0)]
    inspection_ref: WarehouseRef
    sample_qty: Quantity
    defect_qty: Annotated[int, Field(ge=0, le=1_000_000)]
    note: Note
