"""Inventory containment, stock disposition and batch-level reinspection."""
from fastapi import HTTPException

from .db import audit
from .schemas import DispositionKind, HoldStatus, ReinspectionOutcome, WorkStatus

HOLD_VIEW = '''
    SELECT h.*, b.sku, b.product, b.supplier, b.delivered_qty,
           i.finding, i.status AS work_status, i.proof_ref AS supplier_proof_ref,
           h.held_qty - COALESCE(d.processed, 0) AS remaining_qty,
           COALESCE(d.released, 0) AS released_qty,
           COALESCE(d.scrapped, 0) AS scrapped_qty,
           COALESCE(d.returned, 0) AS returned_qty
    FROM stock_hold h JOIN product_batch b ON b.code=h.batch_code
    JOIN improvement i ON i.id=h.improvement_id
    LEFT JOIN LATERAL (
        SELECT SUM(quantity) processed,
               SUM(quantity) FILTER (WHERE kind='release') released,
               SUM(quantity) FILTER (WHERE kind='scrap') scrapped,
               SUM(quantity) FILTER (WHERE kind='vendor_return') returned
        FROM stock_disposition WHERE hold_id=h.id
    ) d ON true
'''


def list_holds(db, user):
    return db.execute(HOLD_VIEW + '''
        WHERE (%s::text IS NULL OR b.supplier=%s)
        ORDER BY (h.status='cleared'), h.id DESC
    ''', (user['supplier'], user['supplier'])).fetchall()


def hold_options(db):
    return db.execute('''SELECT i.id, i.batch_code, i.finding, b.sku, b.product, b.delivered_qty
        FROM improvement i JOIN product_batch b ON b.code=i.batch_code
        WHERE i.status <> 'closed' AND NOT EXISTS (SELECT 1 FROM stock_hold h WHERE h.batch_code=i.batch_code)
        ORDER BY i.id DESC''').fetchall()


def last_submission(db, work_id, status):
    if status != WorkStatus.VERIFICATION:
        return None
    return db.execute('''SELECT id, detail->>'proof' AS proof_ref FROM audit_event
        WHERE action='improvement_submit' AND subject=%s ORDER BY id DESC LIMIT 1''', (str(work_id),)).fetchone()


def detail(db, hold_id, user):
    hold = db.execute(HOLD_VIEW + ''' WHERE h.id=%s AND (%s::text IS NULL OR b.supplier=%s)''',
                      (hold_id, user['supplier'], user['supplier'])).fetchone()
    if hold is None:
        raise HTTPException(404, '库存隔离单不存在')
    rounds = db.execute('SELECT * FROM reinspection_round WHERE hold_id=%s ORDER BY id DESC', (hold_id,)).fetchall()
    submission = last_submission(db, hold['improvement_id'], hold['work_status'])
    current_round = next((row for row in rounds if submission and row['submission_id'] == submission['id']), None)
    moves = db.execute('SELECT * FROM stock_disposition WHERE hold_id=%s ORDER BY id DESC', (hold_id,)).fetchall()
    return {**hold, 'submission': submission, 'current_round': current_round, 'rounds': rounds, 'dispositions': moves}


def create_hold(db, info, user):
    work = db.execute('''SELECT i.id, i.status, i.batch_code, b.delivered_qty
        FROM improvement i JOIN product_batch b ON b.code=i.batch_code
        WHERE i.id=%s FOR UPDATE OF i''', (info.improvement_id,)).fetchone()
    if not work:
        raise HTTPException(404, '已确认的改进工单不存在')
    if work['status'] == WorkStatus.CLOSED:
        raise HTTPException(409, '只能对未结案的改进工单登记库存隔离')
    if info.held_qty > work['delivered_qty']:
        raise HTTPException(422, '封存数量不能超过该批到货数量')
    hold = db.execute('''INSERT INTO stock_hold(improvement_id, batch_code, hold_ref, held_qty, note, recorded_by)
        VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id''',
        (work['id'], work['batch_code'], info.hold_ref.upper(), info.held_qty, info.note, user['login'])).fetchone()
    if not hold:
        raise HTTPException(409, '该批次已有库存隔离单，或封存凭证已登记')
    audit(db, user['login'], 'stock_hold_created', hold['id'], batch=work['batch_code'], qty=info.held_qty,
          reference=info.hold_ref.upper())
    return detail(db, hold['id'], user)


def lock_hold(db, hold_id, user):
    # Lock the improvement first to serialize against supplier updates and legacy work closure.
    work = db.execute('''SELECT i.id, i.status FROM improvement i JOIN stock_hold h ON h.improvement_id=i.id
        WHERE h.id=%s FOR UPDATE OF i''', (hold_id,)).fetchone()
    if not work:
        raise HTTPException(404, '库存隔离单不存在')
    hold = detail(db, hold_id, user)
    if hold['status'] != HoldStatus.HELD:
        raise HTTPException(409, '库存已清账')
    return hold


def next_sample(db, hold_id, info, user):
    hold = lock_hold(db, hold_id, user)
    submission = hold['submission']
    if not submission:
        raise HTTPException(409, '供应商提交整改后才能登记抽检')
    if submission['id'] != info.submission_id:
        raise HTTPException(409, '整改版本已变动，请重新加载抽检单')
    if hold['current_round']:
        raise HTTPException(409, '当前整改版本已有抽检结论。需要复工时，请在改进工单退回并等待重提')
    remaining = hold['remaining_qty']
    if not min(12, remaining) <= info.sample_qty <= remaining:
        raise HTTPException(422, f'本轮须抽检 {min(12, remaining)} 至 {remaining} 件隔离库存')
    if info.defect_qty > info.sample_qty:
        raise HTTPException(422, '不合格件数不能超过样本件数')
    sample = db.execute('''INSERT INTO reinspection_round(hold_id, submission_id, supplier_proof_ref, inspection_ref,
        inventory_qty, sample_qty, defect_qty, note, recorded_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT DO NOTHING RETURNING id, outcome''', (hold_id, submission['id'], submission['proof_ref'],
        info.inspection_ref.upper(), remaining, info.sample_qty, info.defect_qty, info.note, user['login'])).fetchone()
    if not sample:
        raise HTTPException(409, '抽检凭证已登记，或此整改版本已有抽检结论')
    audit(db, user['login'], 'stock_reinspection_recorded', hold_id, round_id=sample['id'],
          submission_id=submission['id'], sample_qty=info.sample_qty, defects=info.defect_qty, outcome=sample['outcome'])
    return detail(db, hold_id, user)


def dispose(db, hold_id, info, user):
    hold = lock_hold(db, hold_id, user)
    if info.quantity > hold['remaining_qty']:
        raise HTTPException(422, '处置数量不能超过剩余隔离数量')
    round_id = None
    if info.kind == DispositionKind.RELEASE:
        current = hold['current_round']
        if not current or current['outcome'] != ReinspectionOutcome.PASS:
            raise HTTPException(409, '当前整改版本须通过抽检方可放行')
        round_id = current['id']
    move = db.execute('''INSERT INTO stock_disposition(hold_id, disposition_ref, kind, quantity, round_id, note, recorded_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id''',
        (hold_id, info.disposition_ref.upper(), info.kind, info.quantity, round_id, info.note, user['login'])).fetchone()
    if not move:
        raise HTTPException(409, '处置凭证已登记')
    if info.quantity == hold['remaining_qty']:
        db.execute("UPDATE stock_hold SET status='cleared' WHERE id=%s", (hold_id,))
    audit(db, user['login'], 'stock_disposition_recorded', hold_id, movement_id=move['id'],
          round_id=round_id, kind=info.kind, qty=info.quantity, reference=info.disposition_ref.upper())
    return detail(db, hold_id, user)
