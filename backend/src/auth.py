import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from enum import StrEnum

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import connect


class Role(StrEnum):
    SERVICE = 'service'
    QUALITY = 'quality'
    SUPPLIER = 'supplier'


KEY = os.getenv('JWT_SECRET', 'demo-return-reason-rules-dev-key-please-replace')
ISSUER = 'return-reason-rules'
BEARER = HTTPBearer(auto_error=False)


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 220_000)
    return f'{salt}:{digest.hex()}'


def authenticate(login, password):
    with connect() as db:
        staff = db.execute('SELECT * FROM staff WHERE login=%s', (login,)).fetchone()
    salt = staff['password_hash'].split(':')[0] if staff else '0' * 32
    candidate = password_hash(password, salt)
    if staff is None or not hmac.compare_digest(candidate, staff['password_hash']):
        raise HTTPException(401, '账号或密码不正确')
    now = datetime.now(timezone.utc)
    token = jwt.encode({'sub': login, 'iss': ISSUER, 'iat': now, 'exp': now + timedelta(hours=8)},
                       KEY, algorithm='HS256')
    del staff['password_hash']
    return {'token': token, 'staff': staff}


def require(*roles):
    def authorized(credentials: HTTPAuthorizationCredentials | None = Depends(BEARER)):
        if credentials is None:
            raise HTTPException(401, '请先登录')
        try:
            claims = jwt.decode(credentials.credentials, KEY, algorithms=['HS256'], issuer=ISSUER,
                                options={'require': ['exp', 'sub', 'iat']})
        except jwt.InvalidTokenError as exc:
            raise HTTPException(401, '登录已失效，请重新登录') from exc
        with connect() as db:
            user = db.execute('SELECT login, display_name, role, supplier FROM staff WHERE login=%s',
                              (claims['sub'],)).fetchone()
        if user is None or user['role'] not in roles:
            raise HTTPException(403, '当前角色没有此操作权限')
        return user

    return authorized
