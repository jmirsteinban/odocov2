from pydantic import BaseModel, Field

class TargetOut(BaseModel):
    key: str
    value: str

    class Config:
        from_attributes = True

class TargetUpdate(BaseModel):
    value: str = Field(min_length=1, max_length=255)
