from pydantic import BaseModel, Field
from typing import Optional
from .common import Edition

class ServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=19132, ge=1, le=65535)
    edition: Edition = "bedrock"
    notes: Optional[str] = None

class ServerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    host: Optional[str] = Field(default=None, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    edition: Optional[Edition] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

class ServerOut(BaseModel):
    id: int
    name: str
    host: str
    port: int
    edition: Edition
    is_active: bool
    notes: Optional[str] = None

    class Config:
        from_attributes = True
