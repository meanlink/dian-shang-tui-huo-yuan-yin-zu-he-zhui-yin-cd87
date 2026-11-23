from fastapi import HTTPException

from .db import audit, lock_evidence

CASE_SELECT = '''
SELECT c.*, coalesce((SELECT array_agg(s.tag ORDER BY s.tag) FROM return_symptom s
WHERE s.ticket=c.ticket), ARRAY[]::text[]) AS symptoms FROM return_case c
'''


def catalog(db):
    return {tag['code']: tag for tag in db.execute('SELECT * FROM reason_tag ORDER BY code')}


def disposition(case, tags):
    flags = []
    if not case['batch_code']:
        flags.append('missing_batch')
    groups = [tags[tag]['mutex'] for tag in case['symptoms']]
    if len(set(groups)) != len(groups):
        flags.append('tag_conflict')
    if not case['finding']:
        flags.append('uninspected')
    return flags


def case_list(db):
    tags = catalog(db)
    rows = db.execute(CASE_SELECT + ' ORDER BY c.opened_on DESC, c.ticket').fetchall()
    return [dict(row, flags=disposition(row, tags)) for row in rows]


def verify_source(db, sku, opened_on, info, tags):
    if any(code not in tags or tags[code]['kind'] != 'symptom' for code in info.symptoms):
        raise HTTPException(422, '售后标签必须来自已登记的客诉标签词表')
    if info.batch_code:
        batch = db.execute('SELECT * FROM product_batch WHERE code=%s', (info.batch_code,)).fetchone()
        if not batch or batch['sku'] != sku:
            raise HTTPException(409, '批号与退货单 SKU 不匹配')
        if opened_on < batch['received_on']:
            raise HTTPException(409, '退货登记日期早于批次到货日')


def save_symptoms(db, ticket, symptoms):
    db.execute('DELETE FROM return_symptom WHERE ticket=%s', (ticket,))
    with db.cursor() as cursor:
        cursor.executemany('INSERT INTO return_symptom(ticket, tag) VALUES (%s, %s)',
                           [(ticket, tag) for tag in sorted(symptoms)])


def create_case(db, info, actor):
    lock_evidence(db)
    tags = catalog(db)
    verify_source(db, info.sku, info.opened_on, info, tags)
    inserted = db.execute('''INSERT INTO return_case(ticket, order_ref, sku, batch_code, opened_on, detail)
          VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING ticket''',
          (info.ticket, info.order_ref, info.sku, info.batch_code, info.opened_on, info.detail)).fetchone()
    if not inserted:
        raise HTTPException(409, '该退货单号已存在')
    save_symptoms(db, info.ticket, info.symptoms)
    audit(db, actor, 'return_registered', info.ticket, batch=info.batch_code, symptoms=sorted(info.symptoms))
    return get_case(db, info.ticket, tags)


def get_case(db, ticket, tags):
    row = db.execute(CASE_SELECT + ' WHERE c.ticket=%s', (ticket,)).fetchone()
    if not row:
        raise HTTPException(404, '退货单不存在')
    return dict(row, flags=disposition(row, tags))


def edit_case(db, ticket, info, actor, *, inspection=False):
    lock_evidence(db)
    tags = catalog(db)
    row = get_case(db, ticket, tags)
    if row['revision'] != info.revision:
        raise HTTPException(409, '退货来源已有更新，请刷新后重试')
    if inspection:
        if info.finding not in tags or tags[info.finding]['kind'] != 'finding':
            raise HTTPException(422, '质检结论必须来自检验标签词表')
        if set(row['flags']) - {'uninspected'}:
            raise HTTPException(409, '补齐批号并消除互斥标签后才可签录质检结论')
        db.execute('''UPDATE return_case SET finding=%s, inspection_ref=%s, revision=revision+1
                      WHERE ticket=%s''', (info.finding, info.inspection_ref, ticket))
        audit(db, actor, 'inspection_recorded', ticket, previous=row['finding'], finding=info.finding,
              ref=info.inspection_ref)
    else:
        verify_source(db, row['sku'], row['opened_on'], info, tags)
        if row['batch_code'] == info.batch_code and set(row['symptoms']) == info.symptoms:
            return row
        db.execute('''UPDATE return_case SET batch_code=%s, finding=NULL, inspection_ref=NULL,
                      revision=revision+1 WHERE ticket=%s''', (info.batch_code, ticket))
        save_symptoms(db, ticket, info.symptoms)
        audit(db, actor, 'return_source_corrected', ticket, old_batch=row['batch_code'],
              new_batch=info.batch_code, old_symptoms=row['symptoms'], new_symptoms=sorted(info.symptoms),
              invalidated_ref=row['inspection_ref'])
    return get_case(db, ticket, tags)


def batch_list(db, supplier=None):
    return db.execute('''SELECT b.*, count(c.ticket) AS returns, count(c.finding) AS inspected
                      FROM product_batch b LEFT JOIN return_case c ON c.batch_code=b.code
                      WHERE (%s::text IS NULL OR b.supplier=%s)
                      GROUP BY b.code ORDER BY b.received_on DESC, b.code''', (supplier, supplier)).fetchall()


def create_batch(db, info, actor):
    row = db.execute('''INSERT INTO product_batch(code, sku, product, supplier, received_on, delivered_qty)
        VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING *''',
        (info.code, info.sku, info.product, info.supplier, info.received_on, info.delivered_qty)).fetchone()
    if not row:
        raise HTTPException(409, '该批次号已存在')
    audit(db, actor, 'batch_registered', info.code, sku=info.sku, supplier=info.supplier)
    return row
