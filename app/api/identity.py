"""First-admin bootstrap, per-person browser sessions, tenant-local user administration."""

from datetime import timedelta
import secrets
from typing import Literal
from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from app.contracts import Contract, Identifier
from app.db.models import BootstrapState, BrowserSession, LoginThrottle, Tenant, User, uid, utcnow
from app.db.session import get_db
from app.errors import ServiceError
from app.security.auth import Principal, hash_token, principal, require
from app.security.passwords import hash_password, verify_password
from app.soar.proposals.service import audit

router = APIRouter(prefix="/v1", tags=["Identity"])
Role = Literal["viewer", "analyst", "operator", "admin"]


class LoginIn(Contract):
    tenant_id: Identifier
    name: Identifier
    password: str = Field(min_length=1, max_length=256, repr=False)


class BootstrapIn(LoginIn):
    bootstrap_token: str = Field(min_length=32, max_length=200, repr=False)


class UserIn(Contract):
    name: Identifier
    role: Role
    password: str = Field(min_length=14, max_length=256, repr=False)


class UserUpdate(Contract):
    role: Role
    active: bool


def user_view(user):
    return {k: getattr(user, k) for k in ("id", "name", "tenant_id", "role", "active")}


def throttle(db, key, limit):
    """Shared database counter survives workers/restarts. Denials do not extend the window."""
    now = utcnow()
    key = hash_token(key)
    db.execute(
        update(LoginThrottle)
        .where(LoginThrottle.key == key, LoginThrottle.reset_at <= now)
        .values(count=0, reset_at=now + timedelta(minutes=15))
    )
    changed = db.execute(update(LoginThrottle).where(LoginThrottle.key == key).values(count=LoginThrottle.count + 1))
    if not changed.rowcount:
        try:
            with db.begin_nested():
                db.add(LoginThrottle(key=key, count=1, reset_at=now + timedelta(minutes=15)))
                db.flush()
        except IntegrityError:
            db.execute(update(LoginThrottle).where(LoginThrottle.key == key).values(count=LoginThrottle.count + 1))
    db.commit()
    if db.get(LoginThrottle, key).count > limit:
        raise ServiceError("login_rate_limited", 429)


def browser_origin(request):
    # JSON-only typed routes plus strict origin for browser mutations, including login CSRF.
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != request.app.state.settings.public_origin.rstrip("/"):
        raise ServiceError("origin_not_allowed", 403)


def issue_session(db, user, response, settings):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.execute(delete(BrowserSession).where(BrowserSession.expires_at <= utcnow()))
    db.add(
        BrowserSession(
            token_hash=hash_token(token),
            user_id=user.id,
            csrf_hash=hash_token(csrf),
            expires_at=utcnow() + timedelta(hours=settings.session_hours),
        )
    )
    db.commit()
    response.set_cookie(
        "sz_session",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
        max_age=settings.session_hours * 3600,
    )
    response.set_cookie(
        "sz_csrf",
        csrf,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
        max_age=settings.session_hours * 3600,
    )
    return {"user": user_view(user)}


@router.get("/auth/bootstrap-status")
def bootstrap_status(request: Request, db=Depends(get_db)):
    state = db.get(BootstrapState, 1)
    return {"available": bool(state and not state.completed and request.app.state.settings.bootstrap_token)}


@router.post("/auth/bootstrap", status_code=201)
def bootstrap(body: BootstrapIn, request: Request, db=Depends(get_db)):
    browser_origin(request)
    throttle(db, "bootstrap", 10)
    configured = request.app.state.settings.bootstrap_token
    if not configured or not secrets.compare_digest(configured, body.bootstrap_token):
        raise ServiceError("bootstrap_unavailable", 403)
    password = hash_password(body.password) if len(body.password) >= 14 else None
    if not password:
        raise ServiceError("password_too_short", 422)
    claim = db.execute(
        update(BootstrapState).where(BootstrapState.id == 1, BootstrapState.completed.is_(False)).values(completed=True)
    )
    if claim.rowcount != 1 or db.scalar(select(User.id).limit(1)):
        db.rollback()
        raise ServiceError("bootstrap_unavailable", 409)
    tenant = Tenant(id=body.tenant_id, name=body.tenant_id)
    db.add(tenant)
    db.flush()
    user = User(
        id=uid("USR"),
        tenant_id=body.tenant_id,
        name=body.name,
        role="admin",
        active=True,
        password_hash=password,
        token_hash=hash_token(secrets.token_urlsafe(32)),
    )
    db.add(user)
    audit(db, Principal(user.id, user.name, user.role, user.tenant_id), "ADMIN_BOOTSTRAPPED")
    db.commit()
    return {"user": user_view(user)}


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response, db=Depends(get_db)):
    browser_origin(request)
    address = request.client.host if request.client else "unknown"
    throttle(db, "address:" + address, 100)
    throttle(db, "account:" + body.tenant_id + ":" + body.name, 10)
    user = db.scalar(select(User).where(User.tenant_id == body.tenant_id, User.name == body.name))
    # Equal work for unknown names; do not disclose user or tenant existence.
    dummy = "pbkdf2_sha256$600000$" + "00" * 16 + "$" + "00" * 32
    valid = verify_password(body.password, user.password_hash if user and user.password_hash else dummy)
    if not valid or not user or not user.active:
        if user:
            audit(db, Principal(user.id, user.name, user.role, user.tenant_id), "LOGIN_FAILED")
            db.commit()
        raise ServiceError("invalid_credentials", 401)
    audit(db, Principal(user.id, user.name, user.role, user.tenant_id), "LOGIN")
    return issue_session(db, user, response, request.app.state.settings)


@router.get("/auth/me")
def me(db=Depends(get_db), p=Depends(principal)):
    return {"user": user_view(db.get(User, p.id))}


@router.post("/auth/logout")
def logout(request: Request, response: Response, db=Depends(get_db), p=Depends(principal)):
    browser_origin(request)
    db.execute(
        delete(BrowserSession).where(BrowserSession.token_hash == hash_token(request.cookies.get("sz_session", "")))
    )
    audit(db, p, "LOGOUT")
    db.commit()
    response.delete_cookie("sz_session", path="/")
    response.delete_cookie("sz_csrf", path="/")
    return {"status": "signed_out"}


@router.get("/users")
def users(db=Depends(get_db), p=Depends(require("admin"))):
    return {
        "items": [
            user_view(u)
            for u in db.scalars(select(User).where(User.tenant_id == p.tenant_id).order_by(User.name).limit(200))
        ]
    }


@router.post("/users", status_code=201)
def add_user(body: UserIn, db=Depends(get_db), p=Depends(require("admin"))):
    user = User(
        id=uid("USR"),
        tenant_id=p.tenant_id,
        name=body.name,
        role=body.role,
        active=True,
        password_hash=hash_password(body.password),
        token_hash=hash_token(secrets.token_urlsafe(32)),
    )
    db.add(user)
    audit(db, p, "USER_CREATED", user_id=user.id, role=body.role)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ServiceError("user_exists", 409) from None
    return user_view(user)


@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UserUpdate, db=Depends(get_db), p=Depends(require("admin"))):
    user = db.scalar(select(User).where(User.id == user_id, User.tenant_id == p.tenant_id))
    if not user:
        raise ServiceError("user_not_found", 404)
    if user.id == p.id:
        raise ServiceError("self_role_change_forbidden", 403)
    user.role, user.active = body.role, body.active
    db.execute(delete(BrowserSession).where(BrowserSession.user_id == user.id))
    audit(db, p, "USER_UPDATED", user_id=user.id, role=body.role, active=body.active)
    db.commit()
    return user_view(user)
