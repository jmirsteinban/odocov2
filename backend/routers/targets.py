# backend/routers/targets.py
# Module: API Router for System target configuration

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db.deps import get_db
from ..db.models import SystemTarget
from ..schemas.targets import TargetOut, TargetUpdate  # ✅ corregido

router = APIRouter(prefix="/targets", tags=["targets"])


@router.get("/{key}", response_model=TargetOut)
def get_target(key: str, db: Session = Depends(get_db)):
    t = db.get(SystemTarget, key)
    if not t:
        raise HTTPException(status_code=404, detail="Target not found")
    return t


@router.put("/{key}", response_model=TargetOut)
def set_target(key: str, payload: TargetUpdate, db: Session = Depends(get_db)):
    t = db.get(SystemTarget, key)
    if not t:
        t = SystemTarget(key=key, value=payload.value)
        db.add(t)
    else:
        t.value = payload.value

    db.commit()
    db.refresh(t)
    return t

