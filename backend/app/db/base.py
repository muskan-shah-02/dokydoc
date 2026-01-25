# Import all SQLAlchemy models here so that Base.metadata contains them
# This is required for Alembic migrations and Base.metadata.create_all()

from app.db.base_class import Base  # noqa

# Import all models
from app.models.user import User  # noqa
from app.models.document import Document  # noqa
from app.models.document_segment import DocumentSegment  # noqa
from app.models.analysis_result import AnalysisResult  # noqa
from app.models.code_component import CodeComponent  # noqa
from app.models.document_code_link import DocumentCodeLink  # noqa
from app.models.mismatch import Mismatch  # noqa
from app.models.tenant import Tenant  # noqa
from app.models.billing import Billing  # noqa

# Keep old fake DB for backward compatibility
FAKE_USERS_DB = {}
