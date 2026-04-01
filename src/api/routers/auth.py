"""
Authentication endpoints.

POST /auth/register  — create new account
POST /auth/login     — get access + refresh tokens
POST /auth/refresh   — exchange refresh token for new access token
POST /auth/logout    — blacklist refresh token
GET  /auth/me        — current user profile
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from ..database import User, get_db
from ..auth import (
    hash_password, authenticate_user, get_user_by_email, get_user_by_id,
    create_access_token, create_refresh_token, decode_refresh_token,
    blacklist_token, is_token_blacklisted,
    ACCESS_TOKEN_EXPIRY_SECONDS, REFRESH_TOKEN_EXPIRY_SECONDS,
)
from ..models import (
    RegisterRequest, LoginRequest, TokenResponse, RefreshRequest,
    AccessTokenResponse, UserProfile,
)
from ..dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user and return tokens."""
    if get_user_by_email(db, body.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    try:
        hashed_pwd = hash_password(body.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    user = User(
        email=body.email,
        hashed_password=hashed_pwd,
        full_name=body.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(user.id, user.email)
    refresh_token, _jti = create_refresh_token(user.id)
    logger.info(f"New user registered: {user.email}")
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRY_SECONDS,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate and return tokens."""
    user = authenticate_user(db, body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    user.last_login = datetime.utcnow()
    db.commit()

    access_token = create_access_token(user.id, user.email)
    refresh_token, _jti = create_refresh_token(user.id)
    logger.info(f"User logged in: {user.email}")
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRY_SECONDS,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    payload = decode_refresh_token(body.refresh_token)
    jti = payload.get("jti", "")
    user_id = payload.get("user_id", "")

    if is_token_blacklisted(db, jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")

    user = get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    access_token = create_access_token(user.id, user.email)
    return AccessTokenResponse(access_token=access_token, expires_in=ACCESS_TOKEN_EXPIRY_SECONDS)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: Session = Depends(get_db)):
    """Blacklist the refresh token (invalidate session)."""
    try:
        payload = decode_refresh_token(body.refresh_token)
        jti = payload.get("jti", "")
        user_id = payload.get("user_id", "")
        exp_ts = payload.get("exp", 0)
        expires_at = datetime.utcfromtimestamp(exp_ts)
        blacklist_token(db, jti, user_id, expires_at)
    except HTTPException:
        pass  # Token already invalid — logout is idempotent


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return current_user
