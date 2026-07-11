"""
Kavach -- User Management API Routes
CRUD endpoints for user administration (CRO / admin role only).

Endpoints:
  GET    /api/v1/users          — list all users
  POST   /api/v1/users          — create a new user
  GET    /api/v1/users/{id}     — get user by ID
  PATCH  /api/v1/users/{id}     — update name / role / password / active status
  DELETE /api/v1/users/{id}     — soft-delete (deactivate) a user
"""

from datetime import datetime
from typing import List, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User, AuditLog

router = APIRouter(prefix="/api/v1/users", tags=["User Management"])

ALLOWED_ROLES = {"risk_officer", "rm", "cro", "compliance", "admin"}


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id:         int
    username:   str
    name:       str
    role:       str
    is_active:  bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    name:     str = Field(..., min_length=1, max_length=128)
    role:     str = Field(..., description="risk_officer | rm | cro | compliance | admin")
    password: str = Field(..., min_length=6, max_length=128)


class UserUpdate(BaseModel):
    name:      Optional[str] = Field(None, min_length=1, max_length=128)
    role:      Optional[str] = None
    password:  Optional[str] = Field(None, min_length=6, max_length=128)
    is_active: Optional[bool] = None


# ─── Role Guard ───────────────────────────────────────────────────────────────

def _require_admin(current_user: dict):
    """Only CRO or admin may manage users."""
    if current_user.get("role") not in ("cro", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User management requires CRO or admin role.",
        )


def _audit(db: Session, event: str, user: str):
    db.add(AuditLog(event=event, user=user))
    db.commit()


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: dict = Depends(lambda: None),   # replaced in main.py via dependency injection
):
    """Return all users (active and inactive)."""
    return db.query(User).order_by(User.id).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(lambda: None),
):
    """Create a new user. Requires CRO or admin role."""
    _require_admin(current_user)

    if payload.role not in ALLOWED_ROLES:
        raise HTTPException(400, f"Invalid role. Must be one of: {sorted(ALLOWED_ROLES)}")

    existing = db.query(User).filter_by(username=payload.username).first()
    if existing:
        raise HTTPException(409, f"Username '{payload.username}' already exists.")

    hashed = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()
    user = User(
        username=payload.username,
        name=payload.name,
        role=payload.role,
        password_hash=hashed,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _audit(db, f"User created: {payload.username} (role={payload.role})", current_user.get("username", "system"))
    return user


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(lambda: None),
):
    """Get a single user by ID."""
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(404, f"User ID {user_id} not found.")
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(lambda: None),
):
    """Update a user's name, role, password, or active status. Requires CRO or admin."""
    _require_admin(current_user)

    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(404, f"User ID {user_id} not found.")

    if payload.role and payload.role not in ALLOWED_ROLES:
        raise HTTPException(400, f"Invalid role. Must be one of: {sorted(ALLOWED_ROLES)}")

    changes = []
    if payload.name is not None:
        user.name = payload.name
        changes.append(f"name={payload.name}")
    if payload.role is not None:
        user.role = payload.role
        changes.append(f"role={payload.role}")
    if payload.password is not None:
        user.password_hash = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()
        changes.append("password=<reset>")
    if payload.is_active is not None:
        user.is_active = payload.is_active
        changes.append(f"is_active={payload.is_active}")

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    if changes:
        _audit(db, f"User updated: {user.username} — {', '.join(changes)}", current_user.get("username", "system"))
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(lambda: None),
):
    """Soft-delete (deactivate) a user. Requires CRO or admin role."""
    _require_admin(current_user)

    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(404, f"User ID {user_id} not found.")

    # Prevent self-deletion
    if user.username == current_user.get("username"):
        raise HTTPException(400, "You cannot deactivate your own account.")

    user.is_active = False
    user.updated_at = datetime.utcnow()
    db.commit()

    _audit(db, f"User deactivated: {user.username}", current_user.get("username", "system"))
