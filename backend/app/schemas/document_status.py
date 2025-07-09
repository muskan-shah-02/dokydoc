# In backend/app/schemas/document_status.py
from pydantic import BaseModel

class DocumentStatus(BaseModel):
    status: str
    progress: int