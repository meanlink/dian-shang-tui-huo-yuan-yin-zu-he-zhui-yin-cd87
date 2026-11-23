import logging
import os
import sys
import time
from pathlib import Path

from .db import CACHE, audit, connect
from .trace import StaleResult, compute

HEARTBEAT = Path(os.getenv('HEARTBEAT_PATH', '/tmp/returns-worker.heartbeat'))
CLAIM_TIMEOUT = float(os.getenv('TRACE_CLAIM_TIMEOUT', '60'))
SWEEP_INTERVAL = 5


def claim(db):
    return db.execute('''UPDATE trace_run SET status='running', attempt=attempt+1, claimed_at=now()
        WHERE id = (SELECT id FROM trace_run WHERE status='queued' ORDER BY id
                    LIMIT 1 FOR UPDATE SKIP LOCKED)
        RETURNING *''').fetchone()


def recover_stuck(db):
    rows = db.execute('''UPDATE trace_run SET status='queued', claimed_at=NULL
        WHERE status='running' AND claimed_at < now() - make_interval(secs => %s)
        RETURNING id, attempt''', (CLAIM_TIMEOUT,)).fetchall()
    for row in rows:
        audit(db, 'worker', 'trace_recovered', row['id'], attempt=row['attempt'])
    return len(rows)


def process_one():
    with connect() as db:
        run = claim(db)
    if not run:
        return False
    try:
        with connect() as db:
            compute(db, run)
    except StaleResult as exc:
        logging.info('Discarded superseded trace result: %s', exc)
    except Exception:
        logging.exception('Trace computation failed for run %s', run['id'])
        try:
            with connect() as db:
                db.execute('''UPDATE trace_run SET status='failed', message=%s, claimed_at=NULL
                              WHERE id=%s AND attempt=%s AND status='running' ''',
                           ('计算失败，可按原受理票据重试', run['id'], run['attempt']))
        except Exception:
            logging.exception('Could not mark run %s as failed', run['id'])
    return True


def main():
    swept = 0.0
    while True:
        try:
            CACHE.ping()
            if time.monotonic() - swept >= SWEEP_INTERVAL:
                with connect() as db:
                    recover_stuck(db)
                swept = time.monotonic()
            active = process_one()
            HEARTBEAT.touch()
            time.sleep(0.1 if active else 0.75)
        except Exception:
            logging.exception('Worker unavailable')
            time.sleep(2)


if __name__ == '__main__':
    if '--health' in sys.argv:
        sys.exit(0 if HEARTBEAT.exists() and time.time() - HEARTBEAT.stat().st_mtime < 12 else 1)
    main()
