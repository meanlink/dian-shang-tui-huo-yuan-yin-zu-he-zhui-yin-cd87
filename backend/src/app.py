import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError

from . import cases, trace, work
from .auth import Role, authenticate, require
from .db import CACHE, connect
from .stock_routes import router as stock_router
from .supplier_returns import credit_routes, shipment_routes
from .schemas import (BatchInput, CaseCorrection, CaseInput, Inspection, Login, Review, RunInput, WorkUpdate)

log = logging.getLogger('uvicorn.error')
ALL_STAFF = require(*Role)
INTERNAL = require(Role.SERVICE, Role.QUALITY)
QUALITY = require(Role.QUALITY)
SERVICE = require(Role.SERVICE)


@asynccontextmanager
async def lifespan(app):
    app.state.limits = Redis.from_url(CACHE_URL, socket_timeout=2)
    try:
        yield
    finally:
        await app.state.limits.aclose()


CACHE_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
app = FastAPI(title='青屿退货追因', lifespan=lifespan)
app.include_router(stock_router)
app.include_router(shipment_routes.router)
app.include_router(credit_routes.router)


@app.middleware('http')
async def rate_limit(request: Request, call_next):
    if request.url.path != '/health':
        login = request.url.path == '/sessions'
        peer = request.client.host if request.client else 'unknown'
        key = f'quota:{"session" if login else "api"}:{peer}:{int(time.time()) // 60}'
        try:
            async with request.app.state.limits.pipeline() as pipe:
                count, _ = await pipe.incr(key).expire(key, 65, nx=True).execute()
            if count > (40 if login else 420):
                return JSONResponse({'detail': '请求太频繁，稍后再试'}, status_code=429)
        except RedisError:
            return JSONResponse({'detail': '请求配额服务暂不可用'}, status_code=503)
    return await call_next(request)


@app.middleware('http')
async def request_log(request: Request, call_next):
    request_id = uuid.uuid4().hex[:12]
    start = time.monotonic()
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    response.headers['Cache-Control'] = 'no-store'
    log.info('rid=%s %s %s -> %s %.0fms', request_id, request.method, request.url.path,
             response.status_code, (time.monotonic() - start) * 1000)
    return response


@app.exception_handler(RequestValidationError)
async def invalid_input(request: Request, exc: RequestValidationError):
    error = exc.errors()[0]
    field = '.'.join(str(part) for part in error['loc'][1:])
    message = error['msg'].removeprefix('Value error, ')
    return JSONResponse({'detail': f'{field} · {message}' if field else message}, status_code=422)


@app.get('/health')
def health():
    with connect() as db:
        db.execute('SELECT 1 FROM trace_run LIMIT 1')
    CACHE.ping()
    return {'status': 'ok'}


@app.post('/sessions')
def login(info: Login):
    return authenticate(info.login, info.password)


@app.get('/session')
def current(user=Depends(ALL_STAFF)):
    return user


@app.get('/tags')
def tags(user=Depends(ALL_STAFF)):
    with connect() as db:
        return list(cases.catalog(db).values())


@app.get('/batches')
def batches(user=Depends(ALL_STAFF)):
    with connect() as db:
        return cases.batch_list(db, user['supplier'])


@app.post('/batches', status_code=201)
def register_batch(info: BatchInput, user=Depends(QUALITY)):
    with connect() as db:
        return cases.create_batch(db, info, user['login'])


@app.get('/returns')
def returns(user=Depends(INTERNAL)):
    with connect() as db:
        return cases.case_list(db)


@app.post('/returns', status_code=201)
def register_return(info: CaseInput, user=Depends(SERVICE)):
    with connect() as db:
        return cases.create_case(db, info, user['login'])


@app.patch('/returns/{ticket}/source')
def correct_source(ticket: str, info: CaseCorrection, user=Depends(SERVICE)):
    with connect() as db:
        return cases.edit_case(db, ticket, info, user['login'])


@app.put('/returns/{ticket}/inspection')
def inspect_return(ticket: str, info: Inspection, user=Depends(QUALITY)):
    with connect() as db:
        return cases.edit_case(db, ticket, info, user['login'], inspection=True)


@app.get('/traces')
def runs(user=Depends(INTERNAL)):
    with connect() as db:
        return db.execute(f'SELECT {trace.LIST_COLUMNS} FROM trace_run ORDER BY id DESC LIMIT 40').fetchall()


@app.post('/traces', status_code=202)
def run_trace(info: RunInput, user=Depends(QUALITY)):
    with connect() as db:
        return trace.enqueue(db, info, user['login'])


@app.post('/traces/{run_id}/retry')
def retry_trace(run_id: int, user=Depends(QUALITY)):
    with connect() as db:
        return trace.retry(db, run_id, user['login'])


@app.get('/traces/{run_id}')
def result(run_id: int, user=Depends(INTERNAL)):
    with connect() as db:
        return trace.get_run(db, run_id)


@app.post('/rules/{rule_id}/review')
def review(rule_id: int, info: Review, user=Depends(QUALITY)):
    with connect() as db:
        return trace.review_rule(db, rule_id, info, user['login'])


@app.get('/improvements')
def works(user=Depends(ALL_STAFF)):
    with connect() as db:
        return work.list_work(db, user)


@app.post('/improvements/{work_id}/actions')
def update_work(work_id: int, info: WorkUpdate, user=Depends(ALL_STAFF)):
    with connect() as db:
        return work.change_work(db, work_id, info, user)
