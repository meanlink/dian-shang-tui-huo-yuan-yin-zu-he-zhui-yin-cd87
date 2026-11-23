from fastapi import APIRouter, Depends

from . import stock
from .auth import Role, require
from .db import connect
from .schemas import DispositionInput, HoldInput, ReinspectionInput

router = APIRouter(prefix='/stock-holds', tags=['inventory containment'])
reader = Depends(require(*Role))
quality = Depends(require(Role.QUALITY))


@router.get('')
def list_holds(user=reader):
    with connect() as db:
        return stock.list_holds(db, user)


@router.get('/options')
def options(user=quality):
    with connect() as db:
        return stock.hold_options(db)


@router.post('', status_code=201)
def create(info: HoldInput, user=quality):
    with connect() as db:
        return stock.create_hold(db, info, user)


@router.get('/{hold_id}')
def detail(hold_id: int, user=reader):
    with connect() as db:
        return stock.detail(db, hold_id, user)


@router.post('/{hold_id}/reinspections', status_code=201)
def reinspection(hold_id: int, info: ReinspectionInput, user=quality):
    with connect() as db:
        return stock.next_sample(db, hold_id, info, user)


@router.post('/{hold_id}/dispositions', status_code=201)
def disposition(hold_id: int, info: DispositionInput, user=quality):
    with connect() as db:
        return stock.dispose(db, hold_id, info, user)
