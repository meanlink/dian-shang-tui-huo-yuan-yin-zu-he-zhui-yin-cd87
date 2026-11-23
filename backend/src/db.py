import logging
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from redis import Redis

ROOT = Path(__file__).resolve().parents[1]
CACHE = Redis.from_url(os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0'), socket_timeout=2)


def connect():
    return psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row, connect_timeout=3)


def lock_evidence(db):
    # Serialize evidence edits with snapshot acquisition and root-cause approval.
    db.execute('SELECT pg_advisory_xact_lock(1053001)')


def audit(db, actor, action, subject, **detail):
    db.execute('INSERT INTO audit_event(actor, action, subject, detail) VALUES (%s,%s,%s,%s)',
               (actor, action, str(subject), Jsonb(detail)))


def migrate():
    with connect() as db:
        lock_evidence(db)
        for migration in sorted((ROOT / 'migrations').glob('*.sql')):
            db.execute(migration.read_text())


if __name__ == '__main__':
    migrate()
    if os.getenv('SEED_DEMO', '').lower() == 'true':
        from scripts.seed_demo import seed

        try:
            print(seed())
        except Exception:
            logging.exception('Demo seed failed')
