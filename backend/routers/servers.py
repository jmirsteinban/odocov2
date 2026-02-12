# backend/routers/servers.py
# Module: API Router for Server management

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db.deps import get_db
from ..db.models import Server
from ..schemas.servers import ServerCreate, ServerUpdate, ServerOut  # ✅ aquí

router = APIRouter(prefix="/servers", tags=["servers"])


@router.get("", response_model=list[ServerOut])
def list_servers(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Server).order_by(Server.is_active.desc(), Server.id.asc())
    ).scalars().all()
    return rows


@router.post("", response_model=ServerOut)
def create_server(payload: ServerCreate, db: Session = Depends(get_db)):
    s = Server(**payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.put("/{server_id}", response_model=ServerOut)
def update_server(server_id: int, payload: ServerUpdate, db: Session = Depends(get_db)):
    s = db.get(Server, server_id)
    if not s:
        raise HTTPException(status_code=404, detail="Server not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(s, k, v)

    db.commit()
    db.refresh(s)
    return s


@router.delete("/{server_id}")
def delete_server(server_id: int, db: Session = Depends(get_db)):
    s = db.get(Server, server_id)
    if not s:
        raise HTTPException(status_code=404, detail="Server not found")
    db.delete(s)
    db.commit()
    return {"deleted": server_id}


@router.post("/{server_id}/activate", response_model=ServerOut)
def activate_server(server_id: int, db: Session = Depends(get_db)):
    s = db.get(Server, server_id)
    if not s:
        raise HTTPException(status_code=404, detail="Server not found")

    db.execute(update(Server).values(is_active=False))
    s.is_active = True
    db.commit()
    db.refresh(s)
    return s
