from fastapi import HTTPException

from .auth import Role
from .db import audit
from .schemas import WorkAction, WorkStatus

DETAIL = '''SELECT i.*, b.sku, b.product, b.supplier, r.symptoms, r.evidence, r.review_note,
                   h.id AS hold_id, h.status AS hold_status
            FROM improvement i JOIN product_batch b ON b.code=i.batch_code
            JOIN trace_rule r ON r.id=i.rule_id
            LEFT JOIN stock_hold h ON h.improvement_id=i.id'''


def public_work(row, user):
    if user['supplier']:
        row['evidence_count'] = len(row.pop('evidence'))
    return row


def list_work(db, user):
    rows = db.execute(DETAIL + ''' WHERE (%s::text IS NULL OR b.supplier=%s)
                                     ORDER BY i.due_on, i.id''', (user['supplier'], user['supplier'])).fetchall()
    return [public_work(row, user) for row in rows]


TRANSITIONS = {
    WorkAction.ACCEPT: (Role.SUPPLIER, WorkStatus.ASSIGNED, WorkStatus.WORKING),
    WorkAction.SUBMIT: (Role.SUPPLIER, WorkStatus.WORKING, WorkStatus.VERIFICATION),
    WorkAction.RETURN: (Role.QUALITY, WorkStatus.VERIFICATION, WorkStatus.WORKING),
    WorkAction.CLOSE: (Role.QUALITY, WorkStatus.VERIFICATION, WorkStatus.CLOSED),
}


def change_work(db, work_id, info, user):
    row = db.execute(DETAIL + ' WHERE i.id=%s FOR UPDATE OF i', (work_id,)).fetchone()
    if not row or (user['supplier'] and row['supplier'] != user['supplier']):
        raise HTTPException(404, '改进工单不存在')
    role, before, after = TRANSITIONS[info.action]
    if user['role'] != role:
        raise HTTPException(403, '当前角色不能执行此工单动作')
    if row['status'] != before:
        raise HTTPException(409, '工单已变动或还未到此处理环节')
    if info.action == WorkAction.CLOSE and db.execute(
        "SELECT 1 FROM stock_hold WHERE improvement_id=%s AND status='held'", (work_id,),
    ).fetchone():
        raise HTTPException(409, '库存隔离单仍有余量，须先完成批次库存处置')
    corrective, reference, verification = row['corrective_action'], row['proof_ref'], row['verification_note']
    if info.action == WorkAction.SUBMIT:
        if not info.note or not info.proof_ref:
            raise HTTPException(422, '提交验证须写明整改行动及证据编号')
        corrective, reference, verification = info.note, info.proof_ref, None
    if info.action in {WorkAction.RETURN, WorkAction.CLOSE}:
        if not info.note:
            raise HTTPException(422, '请填写验证说明')
        verification = info.note
    db.execute('''UPDATE improvement SET status=%s, corrective_action=%s, proof_ref=%s,
                  verification_note=%s, revised_at=now() WHERE id=%s''',
               (after, corrective, reference, verification, work_id))
    audit(db, user['login'], f'improvement_{info.action}', work_id, note=info.note,
          proof=info.proof_ref, previous=before, new=after)
    return public_work(db.execute(DETAIL + ' WHERE i.id=%s', (work_id,)).fetchone(), user)
