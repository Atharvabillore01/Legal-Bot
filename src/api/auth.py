"""
JWT authentication utilities.

Handles token creation, verification, password hashing, and token blacklisting.
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .database import User, TokenBlacklist

# ─── Config ───────────────────────────────────────────────────────────────────

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production-min-32-chars!!")
JWT_REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET_KEY", "refresh-change-me-in-production!!")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRY_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRY", str(24 * 3600)))   # 24 h
REFRESH_TOKEN_EXPIRY_SECONDS = int(os.getenv("REFRESH_TOKEN_EXPIRY", str(7 * 24 * 3600)))  # 7 d

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── Password helpers ─────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash password using bcrypt (max 72 bytes)."""
    if len(plain.encode('utf-8')) > 72:
        raise ValueError('Password exceeds 72 bytes (bcrypt limit)')
    try:
        return pwd_context.hash(plain)
    except ValueError as e:
        # Handle bcrypt errors
        if "password cannot be longer than 72 bytes" in str(e):
            raise ValueError('Password exceeds 72 bytes (bcrypt limit)')
        raise


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against hash (handles bcrypt limit)."""
    try:
        if len(plain.encode('utf-8')) > 72:
            return False  # Can't match bcrypt since plain exceeds limit
        return pwd_context.verify(plain, hashed)
    except ValueError as e:
        # Handle bcrypt errors
        if "password cannot be longer than 72 bytes" in str(e):
            return False
        raise


# ─── Token creation ───────────────────────────────────────────────────────────

def create_access_token(user_id: str, email: str) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(seconds=ACCESS_TOKEN_EXPIRY_SECONDS),
        "token_type": "access",
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Returns (encoded_token, jti)."""
    now = datetime.utcnow()
    jti = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "iat": now,
        "exp": now + timedelta(seconds=REFRESH_TOKEN_EXPIRY_SECONDS),
        "token_type": "refresh",
        "jti": jti,
    }
    return jwt.encode(payload, JWT_REFRESH_SECRET_KEY, algorithm=JWT_ALGORITHM), jti


# ─── Token verification ───────────────────────────────────────────────────────

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("token_type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def decode_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_REFRESH_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("token_type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")


# ─── User lookup helpers ──────────────────────────────────────────────────────

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


# ─── Token blacklist ──────────────────────────────────────────────────────────

def blacklist_token(db: Session, jti: str, user_id: str, expires_at: datetime) -> None:
    entry = TokenBlacklist(jti=jti, user_id=user_id, expires_at=expires_at)
    db.add(entry)
    db.commit()


def is_token_blacklisted(db: Session, jti: str) -> bool:
    return db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first() is not None
