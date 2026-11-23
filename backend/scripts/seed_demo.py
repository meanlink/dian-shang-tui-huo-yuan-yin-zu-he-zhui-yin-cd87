from src.auth import password_hash
from src.db import connect, lock_evidence

TAGS = [
    ('LEAK', '沿杯口漏水', 'symptom', '表现'), ('JAM', '开合卡滞', 'symptom', '表现'),
    ('DENT', '外壳凹陷', 'symptom', '表现'), ('LOOSE', '手感松动', 'symptom', '外观触感'),
    ('TIGHT', '手感过紧', 'symptom', '外观触感'), ('CRACK', '可见裂痕', 'symptom', '外观触感'),
    ('GASKET', '密封圈压装偏位', 'finding', None), ('HINGE', '转轴装配超公差', 'finding', None),
    ('SHELL', '外壳抗压不足', 'finding', None),
]
BATCHES = [
    ('HX-261107-A', 'MUG-480', '青屿翻盖杯 480 mL', '海汐杯业', '2026-11-07', 4800),
    ('HX-261102-B', 'MUG-480', '青屿翻盖杯 480 mL', '海汐杯业', '2026-11-02', 3200),
    ('XM-261109-A', 'JAR-700', '青屿焖烧罐 700 mL', '新茂金工', '2026-11-09', 1800),
]
STAFF = [('lin', '林夏 · 售后客服', 'service', None), ('zhou', '周岁 · 品控主管', 'quality', None),
         ('haixi', '何原 · 海汐杯业', 'supplier', '海汐杯业'),
         ('xinmao', '方敏 · 新茂金工', 'supplier', '新茂金工')]


def insert_case(db, sequence, batch, sku, symptoms, finding=None):
    ticket = f'RT-{261100 + sequence}'
    recorded = db.execute('''INSERT INTO return_case(ticket,order_ref,sku,batch_code,opened_on,detail,
        finding,inspection_ref) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT DO NOTHING RETURNING ticket''',
        (ticket, f'SO-{78420 + sequence}', sku, batch, f'2026-11-{12 + sequence % 8:02d}',
         '买家提交使用视频，已记录客诉现象并等待仓库处理。', finding,
         f'QC-HX-{sequence:03d}' if finding else None)).fetchone()
    if recorded:
        for tag in symptoms:
            db.execute('INSERT INTO return_symptom(ticket,tag) VALUES (%s,%s)', (ticket, tag))


def seed():
    with connect() as db:
        lock_evidence(db)
        for login, name, role, supplier in STAFF:
            db.execute('''INSERT INTO staff(login,password_hash,display_name,role,supplier)
                          VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                       (login, password_hash('returns2026'), name, role, supplier))
        with db.cursor() as cursor:
            cursor.executemany('INSERT INTO reason_tag VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING', TAGS)
            cursor.executemany('INSERT INTO product_batch VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING', BATCHES)
        groups = [(['LEAK', 'LOOSE'], 'GASKET', 8), (['LEAK', 'CRACK'], 'SHELL', 2),
                  (['JAM', 'LOOSE'], 'HINGE', 3), (['JAM', 'TIGHT'], 'HINGE', 5),
                  (['DENT', 'CRACK'], 'SHELL', 6)]
        sequence = 1
        for tags, finding, total in groups:
            for _ in range(total):
                insert_case(db, sequence, BATCHES[0][0], BATCHES[0][1], tags, finding)
                sequence += 1
        insert_case(db, 25, None, 'MUG-480', ['LEAK', 'LOOSE'])
        insert_case(db, 26, BATCHES[0][0], 'MUG-480', ['LEAK', 'JAM'])
        insert_case(db, 27, BATCHES[0][0], 'MUG-480', ['DENT'])
        insert_case(db, 28, BATCHES[1][0], 'MUG-480', ['LEAK', 'LOOSE'], 'GASKET')
        insert_case(db, 29, BATCHES[2][0], 'JAR-700', ['JAM'])
        return {table: db.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']
                for table in ('staff', 'reason_tag', 'product_batch', 'return_case', 'return_symptom')}


if __name__ == '__main__':
    print(seed())
