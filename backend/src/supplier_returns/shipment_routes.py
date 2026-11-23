from fastapi import APIRouter, Depends

from ..auth import Role, require
from ..db import connect
from . import shipments
from .schemas import Dispatch, Receipt, Resolution

router = APIRouter(prefix='/vendor-shipments', tags=['实物退供'])
quality = Depends(require(Role.QUALITY))
supplier = Depends(require(Role.SUPPLIER))


@router.get('')
def board(user=Depends(require(*Role))):
    with connect() as db:
        return shipments.board(db, user)


@router.post('', status_code=201)
def dispatch(data: Dispatch, user=quality):
    with connect() as db:
        return shipments.dispatch(db, data, user)


@router.post('/{shipment_id}/receipt')
def receive(shipment_id: int, data: Receipt, user=supplier):
    with connect() as db:
        return shipments.receive(db, shipment_id, data, user)


@router.post('/{shipment_id}/resolution')
def resolve(shipment_id: int, data: Resolution, user=quality):
    with connect() as db:
        return shipments.resolve(db, shipment_id, data, user)
