import logging
import os
import sys
import time
from pathlib import Path

from psycopg.types.json import Jsonb

from .db import CACHE, connect
from .trace import compute

HEARTBEAT = Path(os.getenv('HEARTBEAT_PATH', '/tmp/returns-worker.heartbeat'))


def process_one():
    with connect() as db:
        run = db.execute('''SELECT * FROM trace_run WHERE status='queued' ORDER BY id
                         LIMIT 1 FOR UPDATE SKIP LOCKED''').fetchone()
        if not run:
            return False
        try:
            with db.transaction():
                compute(db, run)
        except Exception:
            logging.exception('Trace computation failed for run %s', run['id'])
            db.execute('UPDATE trace_run SET status=%s, message=%s, coverage=%s WHERE id=%s',
                       ('failed', '计算失败，可按同口径重新发起', Jsonb({}), run['id']))
        return True


def main():
    while True:
        try:
            CACHE.ping()
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
