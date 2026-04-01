"""
Audit log endpoint.

GET /audit-log  — paginated activity history for the current user.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import AuditLog, get_db
from ..dependencies import get_current_user
from ..models import AuditLogListResponse, AuditLogEntry
from ..database import User

router = APIRouter(prefix="/audit-log", tags=["Audit"])


@router.get("", response_model=AuditLogListResponse)
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return paginated audit log entries for the authenticated user."""
    q = db.query(AuditLog).filter(AuditLog.user_id == current_user.id)
    if action:
        q = q.filter(AuditLog.action == action)
    total = q.count()
    logs = (
        q.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AuditLogListResponse(
        logs=[AuditLogEntry.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )
