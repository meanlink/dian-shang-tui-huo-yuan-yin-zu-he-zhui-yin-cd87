from fastapi import HTTPException
from psycopg.errors import UniqueViolation

from ..db import audit

SOURCE = '''FROM stock_disposition d JOIN stock_hold h ON h.id=d.hold_id
            JOIN product_batch b ON b.code=h.batch_code'''
JOINED = f'''FROM vendor_shipment v JOIN stock_disposition d ON d.id=v.disposition_id
             JOIN stock_hold h ON h.id=d.hold_id JOIN product_batch b ON b.code=h.batch_code'''


def scoped(user, supplier):
    if user['role'] == 'supplier' and user['supplier'] != supplier:
        raise HTTPException(404, '退供记录不存在')


def lock_shipment(db, shipment_id, user):
    row = db.execute(f'SELECT v.*,b.supplier,b.code batch_code,d.disposition_ref {JOINED} WHERE v.id=%s FOR UPDATE OF v',
                     (shipment_id,)).fetchone()
    if not row:
        raise HTTPException(404, '退供记录不存在')
    scoped(user, row['supplier'])
    return row


def board(db, user):
    supplier = user['supplier'] if user['role'] == 'supplier' else None
    rows = db.execute(f'''SELECT v.*,b.supplier,b.code batch_code,d.disposition_ref {JOINED}
        WHERE (%s::text IS NULL OR b.supplier=%s) ORDER BY v.id DESC''', (supplier,supplier)).fetchall()
    awaiting = []
    if user['role'] == 'quality':
        awaiting = db.execute(f'''SELECT d.id,d.disposition_ref,d.quantity,h.batch_code,b.supplier {SOURCE}
            WHERE d.kind='vendor_return' AND NOT EXISTS (SELECT 1 FROM vendor_shipment v WHERE v.disposition_id=d.id)
            ORDER BY d.id DESC''').fetchall()
    return {'shipments': rows, 'awaiting_dispatch': awaiting}


def dispatch(db, payload, user):
    source = db.execute(f'''SELECT d.quantity,d.kind,h.batch_code,b.supplier {SOURCE} WHERE d.id=%s FOR UPDATE OF d''',
                        (payload.disposition_id,)).fetchone()
    if not source or source['kind'] != 'vendor_return':
        raise HTTPException(422, '只有已登记退供的仓库处置流水可创建运单')
    try:
        row = db.execute('''INSERT INTO vendor_shipment (disposition_id,dispatch_ref,carrier,tracking,sent_qty,dispatched_by)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING *''', (payload.disposition_id,payload.dispatch_ref,payload.carrier,
            payload.tracking,source['quantity'],user['login'])).fetchone()
    except UniqueViolation as exc:
        raise HTTPException(409, '退供流水、出库凭证或承运单号已登记') from exc
    audit(db, user['login'],'vendor_return_dispatched',row['id'],batch=source['batch_code'], quantity=row['sent_qty'])
    return row


def receive(db, shipment_id, payload, user):
    row = lock_shipment(db, shipment_id, user)
    if row['status'] != 'in_transit':
        raise HTTPException(409, '该运单已登记过签收')
    if payload.vendor_qty > row['sent_qty']:
        raise HTTPException(422, '实收件数不能超过发出件数')
    matched = payload.vendor_qty == row['sent_qty']
    next_status = 'received' if matched else 'disputed'
    updated = db.execute('''UPDATE vendor_shipment SET vendor_qty=%s,vendor_ref=%s,vendor_note=%s,
        received_by=%s,received_at=now(),status=%s,settled_qty=%s WHERE id=%s RETURNING *''',
        (payload.vendor_qty,payload.vendor_ref,payload.vendor_note,user['login'],next_status,
         payload.vendor_qty if matched else None,shipment_id)).fetchone()
    audit(db,user['login'],'vendor_return_received',shipment_id,quantity=payload.vendor_qty,status=next_status)
    return updated


def resolve(db, shipment_id, payload, user):
    row = lock_shipment(db, shipment_id, user)
    if row['status'] != 'disputed':
        raise HTTPException(409, '只有签收短件的运单可裁定')
    if not row['vendor_qty'] <= payload.settled_qty <= row['sent_qty']:
        raise HTTPException(422, '裁定件数须介于供应商已收件数和原出库数之间')
    updated = db.execute('''UPDATE vendor_shipment SET resolution_ref=%s,resolution_note=%s,
        settled_qty=%s,status='received' WHERE id=%s RETURNING *''',
        (payload.resolution_ref,payload.resolution_note,payload.settled_qty,shipment_id)).fetchone()
    audit(db,user['login'],'vendor_return_dispute_resolved',shipment_id,quantity=payload.settled_qty)
    return updated
