# backend/routers/modes.py
# Module: ODOCO Backend — Modes API (SQLite-driven)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from backend.db.session import SessionLocal
from backend.db.models import Mode
from typing import List

router = APIRouter(prefix="/api", tags=["modes"])


# =========================
# GET /api/modes
# =========================
@router.get("/modes")
def get_modes():
    with SessionLocal() as db:
        modes = db.execute(select(Mode)).scalars().all()

        return {
            "modes": [
                {
                    "id": m.id,
                    "title": m.title
                }
                for m in modes
            ]
        }


# =========================
# GET /api/mode (modo actual)
# =========================
@router.get("/mode")
def get_current_mode():
    with SessionLocal() as db:
        mode = db.execute(
            select(Mode).where(Mode.is_active == True)
        ).scalar_one_or_none()

        if not mode:
            return {
                "current_mode_id": None,
                "current_mode_title": None,
                "features_html": "<span class='muted'>Sin modo activo</span>"
            }

        return {
            "current_mode_id": mode.id,
            "current_mode_title": mode.title,
            "features_html": mode.description_html or ""
        }


# =========================
# POST /api/mode
# =========================
class ModeUpdate(BaseModel):
    mode_id: int


@router.post("/mode")
def set_current_mode(payload: ModeUpdate):
    with SessionLocal() as db:

        # desactivar todos
        db.execute(
            update(Mode).values(is_active=False)
        )

        # activar seleccionado
        result = db.execute(
            update(Mode)
            .where(Mode.id == payload.mode_id)
            .values(is_active=True)
        )

        db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Mode not found")

        return {"ok": True}
