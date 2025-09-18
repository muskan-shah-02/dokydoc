from typing import Optional
from pydantic import BaseModel


class DocumentSegmentBase(BaseModel):
    segment_type: str
    start_char_index: int
    end_char_index: int
    document_id: int
    analysis_run_id: Optional[int] = None


class DocumentSegmentCreate(DocumentSegmentBase):
    pass


class DocumentSegmentUpdate(BaseModel):
    segment_type: Optional[str] = None
    start_char_index: Optional[int] = None
    end_char_index: Optional[int] = None


from datetime import datetime

class DocumentSegmentInDBBase(DocumentSegmentBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentSegment(DocumentSegmentInDBBase):
    pass


class DocumentSegmentInDB(DocumentSegmentInDBBase):
    pass
