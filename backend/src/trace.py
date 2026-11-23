import hashlib
import json
from collections import Counter
from datetime import date

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from .cases import CASE_SELECT, catalog, disposition
from .db import audit, lock_evidence
from .fpgrowth import rank_rules
from .schemas import Decision


def snapshot(db, run):
    tags = catalog(db)
    rows = db.execute(CASE_SELECT + ''' JOIN product_batch b ON b.code=%s AND b.sku=c.sku
        WHERE (c.batch_code=b.code OR c.batch_code IS NULL) AND c.opened_on BETWEEN %s AND %s
        ORDER BY c.ticket''', (run['batch_code'], run['from_date'], run['through_date'])).fetchall()
    covered = Counter()
    eligible = []
    excluded = []
    for row in rows:
        flags = disposition(row, tags)
        covered.update(flags)
        if flags:
            excluded.append({'ticket': row['ticket'], 'flags': flags})
        else:
            eligible.append(row)
    coverage = dict(total=len(rows), eligible=len(eligible), excluded=excluded,
                    missing_batch=covered['missing_batch'], tag_conflict=covered['tag_conflict'],
                    uninspected=covered['uninspected'])
    canonical = [(row['ticket'], row['revision']) for row in rows]
    fingerprint = hashlib.sha256(json.dumps(canonical, separators=(',', ':')).encode()).hexdigest()
    return coverage, fingerprint, eligible


def enqueue(db, info, actor):
    if not db.execute('SELECT 1 FROM product_batch WHERE code=%s', (info.batch_code,)).fetchone():
        raise HTTPException(404, '商品批次不存在')
    row = db.execute('''INSERT INTO trace_run(batch_code, from_date, through_date, requested_by)
           VALUES (%s,%s,%s,%s) RETURNING *''',
           (info.batch_code, info.from_date, info.through_date, actor)).fetchone()
    audit(db, actor, 'trace_queued', row['id'], batch=info.batch_code)
    return row


def compute(db, run):
    lock_evidence(db)
    coverage, fingerprint, samples = snapshot(db, run)
    ranked = rank_rules(samples) if len(samples) >= 8 else []
    with db.cursor() as cursor:
        cursor.executemany('''INSERT INTO trace_rule(run_id,symptoms,finding,matched_count,symptom_count,
                   finding_count,eligible_count,evidence) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
                   [(run['id'], symptoms, finding, count, antecedent, consequent, len(samples), evidence)
                    for _, count, symptoms, finding, antecedent, consequent, evidence in ranked])
    message = '有效验货单少于 8 张' if len(samples) < 8 else '当前窗口没有达到同现门槛的组合'
    db.execute('UPDATE trace_run SET status=%s, coverage=%s, fingerprint=%s, message=%s WHERE id=%s',
               ('ready' if ranked else 'blocked', Jsonb(coverage), fingerprint,
                None if ranked else message, run['id']))
    audit(db, 'worker', 'trace_finished', run['id'], eligible=len(samples), rules=len(ranked))


def get_run(db, run_id):
    run = db.execute('SELECT * FROM trace_run WHERE id=%s', (run_id,)).fetchone()
    if not run:
        raise HTTPException(404, '追因记录不存在')
    rules = db.execute('''SELECT r.*, i.id AS work_id,
         matched_count::float / eligible_count AS support, matched_count::float / symptom_count AS confidence,
         matched_count::numeric * eligible_count / (symptom_count::numeric * finding_count) AS lift
         FROM trace_rule r LEFT JOIN improvement i ON i.rule_id=r.id WHERE run_id=%s
         ORDER BY lift DESC, matched_count DESC, symptoms, finding''', (run_id,)).fetchall()
    for rule in rules:
        rule['lift'] = float(rule['lift'])
    return dict(run, rules=rules)


def review_rule(db, rule_id, request, actor):
    lock_evidence(db)
    rule = db.execute('SELECT * FROM trace_rule WHERE id=%s FOR UPDATE', (rule_id,)).fetchone()
    if not rule:
        raise HTTPException(404, '待复核组合不存在')
    if rule['decision'] != 'pending':
        raise HTTPException(409, '该组合已复核')
    decision = 'dismissed'
    work = None
    if request.decision == Decision.CONFIRM:
        if rule['matched_count'] * rule['eligible_count'] <= rule['symptom_count'] * rule['finding_count']:
            raise HTTPException(409, '提升度须严格大于 1 才可确认根因')
        run = db.execute('SELECT * FROM trace_run WHERE id=%s', (rule['run_id'],)).fetchone()
        _, fingerprint, _ = snapshot(db, run)
        if fingerprint != run['fingerprint']:
            raise HTTPException(409, '源单已有变更，请对同一窗口重新追因后复核')
        if request.due_on < date.today():
            raise HTTPException(422, '整改截止日不能早于今天')
        work = db.execute('''INSERT INTO improvement(rule_id,batch_code,finding,directive,due_on)
             VALUES (%s,%s,%s,%s,%s) ON CONFLICT (batch_code,finding) DO NOTHING RETURNING *''',
             (rule_id, run['batch_code'], rule['finding'], request.directive, request.due_on)).fetchone()
        if not work:
            raise HTTPException(409, '该批次的这项质检结论已有改进工单')
        decision = 'confirmed'
        audit(db, actor, 'improvement_assigned', work['id'], rule=rule_id, batch=run['batch_code'])
    db.execute('UPDATE trace_rule SET decision=%s, reviewer=%s, review_note=%s WHERE id=%s',
               (decision, actor, request.note, rule_id))
    audit(db, actor, 'root_reviewed', rule_id, decision=decision, note=request.note)
    return {'decision': decision, 'work': work}
