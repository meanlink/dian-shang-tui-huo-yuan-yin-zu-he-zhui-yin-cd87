from fastapi import APIRouter, Depends

from ..auth import Role, require
from ..db import connect
from . import credits
from .schemas import Credit, CreditDecision

router = APIRouter(prefix='/vendor-credits', tags=['供方货款冲抵'])


@router.get('')
def board(user=Depends(require(Role.QUALITY, Role.SUPPLIER))):
    with connect() as db:
        return credits.board(db, user)


@router.post('/{shipment_id}', status_code=201)
def propose(shipment_id: int, data: Credit, user=Depends(require(Role.QUALITY))):
    with connect() as db:
        return credits.propose(db, shipment_id, data, user)


@router.post('/{shipment_id}/{credit_id}/decision')
def decide(shipment_id: int, credit_id: int, data: CreditDecision, user=Depends(require(Role.SUPPLIER))):
    with connect() as db:
        return credits.decide(db, shipment_id, credit_id, data, user)
