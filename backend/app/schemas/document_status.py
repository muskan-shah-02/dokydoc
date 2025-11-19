from typing import Optional  # <--- You were missing this import
from pydantic import BaseModel

class DocumentStatus(BaseModel):
    status: str
    progress: int
    # We must explicitly add this field so the API returns it
    error_message: Optional[str] = None