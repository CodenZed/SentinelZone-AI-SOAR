import hashlib
import secrets
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.db.models import BrowserSession, User, Tenant, uid, utcnow
from app.errors import ServiceError

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    id: str
    name: str
    role: str
    tenant_id: str


def hash_token(value):
    return hashlib.sha256(value.encode()).hexdigest()


def create_user(session, name, role, tenant):
    if role not in {"viewer", "analyst", "operator", "admin"}:
        raise ValueError("invalid role")
    token = secrets.token_urlsafe(32)
    if not session.get(Tenant, tenant):
        session.add(Tenant(id=tenant, name=tenant))
        session.flush()
    session.add(User(id=uid("USR"), name=name, role=role, tenant_id=tenant, token_hash=hash_token(token)))
    session.commit()
    return token


def principal(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials and request.app.state.settings.core_api_token and secrets.compare_digest(
        credentials.credentials, request.app.state.settings.core_api_token
    ):
        raise ServiceError("invalid_credentials", 401)
    with request.app.state.sessions() as session:
        if credentials:
            user = session.scalar(select(User).where(User.token_hash == hash_token(credentials.credentials),
                                                     User.active.is_(True)))
        else:
            token = request.cookies.get('sz_session', '')
            login = session.scalar(select(BrowserSession).where(BrowserSession.token_hash == hash_token(token),
                                                               BrowserSession.expires_at > utcnow())) if token else None
            if not login:
                raise ServiceError('authentication_required', 401)
            if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
                origin = request.headers.get('origin')
                if origin and origin.rstrip('/') != request.app.state.settings.public_origin.rstrip('/'):
                    raise ServiceError('origin_not_allowed', 403)
                csrf = request.headers.get('x-csrf-token', '')
                if not csrf or not secrets.compare_digest(login.csrf_hash, hash_token(csrf)):
                    raise ServiceError('csrf_required', 403)
            user = session.get(User, login.user_id)
            if user and not user.active:
                user = None
        if not user:
            raise ServiceError("invalid_credentials", 401)
        return Principal(user.id, user.name, user.role, user.tenant_id)


def require(*roles):
    def dependency(p: Principal = Depends(principal)):
        if p.role not in roles:
            raise ServiceError("role_not_permitted", 403)
        return p

    return dependency
