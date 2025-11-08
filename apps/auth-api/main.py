from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Header
from pydantic import BaseModel, EmailStr, Field
import jwt
from passlib.hash import pbkdf2_sha256

from libs.core_domain.db import init_db, get_session, User, RefreshToken


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _env_str(name: str, default: str) -> str:
    val = os.getenv(name)
    return val if isinstance(val, str) and val else default


def _env_int(name: str, default: int) -> int:
    try:
        raw = os.getenv(name)
        return int(raw) if raw is not None else default
    except Exception:
        return default


JWT_SECRET = _env_str("JWT_SECRET", "dev_secret")
JWT_REFRESH_SECRET = _env_str("JWT_REFRESH_SECRET", "dev_refresh_secret")
JWT_EXPIRES_MINUTES = _env_int("JWT_EXPIRES_MINUTES", 60)
JWT_REFRESH_EXPIRES_DAYS = _env_int("JWT_REFRESH_EXPIRES_DAYS", 14)


app = FastAPI(title="Auth API", version="0.1.0")


@app.on_event("startup")
async def _startup() -> None:
    init_db()


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    display_name: Optional[str] = None
    gender: Optional[str] = None  # 男性/女性/male/female


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = Field(..., description="access token seconds to expire")


class MeResponse(BaseModel):
    user_id: str
    email: EmailStr
    display_name: Optional[str] = None
    gender: Optional[str] = None


def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _gen_tokens(user_id: str) -> TokenResponse:
    now = _now_utc()
    access_payload = {
        "sub": user_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRES_MINUTES)).timestamp()),
    }
    access_token = jwt.encode(access_payload, JWT_SECRET, algorithm="HS256")

    refresh_payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=JWT_REFRESH_EXPIRES_DAYS)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    refresh_token = jwt.encode(refresh_payload, JWT_REFRESH_SECRET, algorithm="HS256")

    # persist hashed refresh
    with get_session() as s:
        row = RefreshToken(
            user_id=user_id,
            token_hash=_hash_refresh(refresh_token),
            expires_at=now + timedelta(days=JWT_REFRESH_EXPIRES_DAYS),
            revoked=0,
        )
        s.add(row)
        s.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=JWT_EXPIRES_MINUTES * 60,
    )


def _verify_access(auth_header: Optional[str]) -> str:
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="invalid token type")
        return str(payload.get("sub"))
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")


@app.post("/auth/signup", response_model=TokenResponse)
async def signup(req: SignupRequest) -> TokenResponse:
    # check unique email
    with get_session() as s:
        exists = s.query(User).filter(User.email == req.email).first()
        if exists:
            raise HTTPException(status_code=409, detail="email already registered")
        user_id = str(uuid.uuid4())
        row = User(
            user_id=user_id,
            email=req.email,
            password_hash=pbkdf2_sha256.hash(req.password),
            display_name=req.display_name,
            gender=req.gender,
            auth_provider="local",
        )
        s.add(row)
        s.commit()
    return _gen_tokens(user_id)


@app.post("/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest) -> TokenResponse:
    with get_session() as s:
        user = s.query(User).filter(User.email == req.email).first()
        if not user or not pbkdf2_sha256.verify(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="invalid credentials")
        user_id = str(user.user_id)
    return _gen_tokens(user_id)


class RefreshRequest(BaseModel):
    refresh_token: str


@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest) -> TokenResponse:
    try:
        payload = jwt.decode(req.refresh_token, JWT_REFRESH_SECRET, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="invalid token type")
        user_id = str(payload.get("sub"))
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="refresh token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="invalid refresh token")

    token_hash = _hash_refresh(req.refresh_token)
    with get_session() as s:
        row = (
            s.query(RefreshToken)
            .filter(RefreshToken.user_id == user_id)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )
        if not row or row.revoked:
            raise HTTPException(status_code=401, detail="refresh token revoked")
        if row.expires_at.replace(tzinfo=timezone.utc) < _now_utc():
            raise HTTPException(status_code=401, detail="refresh token expired")
    # issue new access token only
    now = _now_utc()
    access_payload = {
        "sub": user_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRES_MINUTES)).timestamp()),
    }
    access_token = jwt.encode(access_payload, JWT_SECRET, algorithm="HS256")
    return TokenResponse(access_token=access_token, expires_in=JWT_EXPIRES_MINUTES * 60)


@app.get("/me", response_model=MeResponse)
async def me(authorization: Optional[str] = Header(default=None)) -> MeResponse:
    user_id = _verify_access(authorization)
    with get_session() as s:
        user = s.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="user not found")
        return MeResponse(
            user_id=user.user_id,
            email=user.email,
            display_name=user.display_name,
            gender=user.gender,
        )


# Health endpoint
@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok"}

