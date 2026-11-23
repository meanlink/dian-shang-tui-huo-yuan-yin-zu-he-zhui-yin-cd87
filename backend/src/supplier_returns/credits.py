from fastapi import HTTPException
from psycopg.errors import UniqueViolation

from ..db import audit
from .shipments import JOINED, lock_shipment


def board(db, user):
    supplier = user['supplier'] if user['role'] == 'supplier' else None
    rows = db.execute(f'''SELECT c.*,v.dispatch_ref,b.supplier,b.code batch_code
        {JOINED} JOIN vendor_credit c ON c.shipment_id=v.id
        WHERE (%s::text IS NULL OR b.supplier=%s) ORDER BY c.id DESC''', (supplier,supplier)).fetchall()
    eligible = []
    if user['role'] == 'quality':
        eligible = db.execute(f'''SELECT v.id,v.dispatch_ref,v.settled_qty,b.supplier {JOINED}
            WHERE v.status='received' AND v.settled_qty>0
            AND NOT EXISTS (SELECT 1 FROM vendor_credit c WHERE c.shipment_id=v.id AND c.status<>'rejected')
            ORDER BY v.id DESC''').fetchall()
    return {'credits': rows, 'eligible_shipments': eligible}


def propose(db, shipment_id, payload, user):
    shipment = lock_shipment(db, shipment_id, user)
    units = shipment['settled_qty']
    if shipment['status'] != 'received' or not units:
        raise HTTPException(409, '运单尚无可冲抵的结算数量')
    if payload.freight_cents >= units * payload.unit_price_cents:
        raise HTTPException(422, '约定扣减运费须小于货款金额')
    try:
        row = db.execute('''INSERT INTO vendor_credit (shipment_id,proposal_ref,units,unit_price_cents,freight_cents,note,submitted_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *''', (shipment_id,payload.proposal_ref,units,
            payload.unit_price_cents,payload.freight_cents,payload.note,user['login'])).fetchone()
    except UniqueViolation as exc:
        raise HTTPException(409, '有生效冲抵单或冲抵编号曾使用') from exc
    audit(db,user['login'],'vendor_credit_proposed',row['id'],amount_cents=row['net_cents'],quantity=units)
    return row


def decide(db, shipment_id, credit_id, payload, user):
    lock_shipment(db, shipment_id, user)
    if (payload.decision == 'accepted') != (payload.acknowledged_ref is not None):
        raise HTTPException(422, '确认冲抵须填供应商凭证，驳回时不填凭证')
    try:
        row = db.execute('''UPDATE vendor_credit SET status=%s,review_note=%s,acknowledged_ref=%s,
            reviewed_by=%s,reviewed_at=now() WHERE id=%s AND shipment_id=%s AND status='pending' RETURNING *''',
            (payload.decision,payload.review_note,payload.acknowledged_ref,user['login'],credit_id,shipment_id)).fetchone()
    except UniqueViolation as exc:
        raise HTTPException(409, '该供应商确认凭证已使用') from exc
    if not row:
        raise HTTPException(409, '冲抵单已裁定或不属于该运单')
    audit(db,user['login'],'vendor_credit_reviewed',credit_id,status=payload.decision,amount_cents=row['net_cents'])
    return row
