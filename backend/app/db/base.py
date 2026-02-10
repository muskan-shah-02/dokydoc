# Import all SQLAlchemy models here so that Base.metadata contains them
# This is required for Alembic migrations and Base.metadata.create_all()

from app.db.base_class import Base  # noqa

# Import all models
# IMPORTANT: Import order matters for relationship resolution
# Task depends on User, Tenant, Document, CodeComponent
# So Task must be imported AFTER its dependencies

from app.models.user import User  # noqa
from app.models.tenant import Tenant  # noqa
from app.models.document import Document  # noqa
from app.models.code_component import CodeComponent  # noqa
from app.models.task import Task, TaskComment  # noqa - Sprint 2 Extended Phase 10 (must come after its dependencies)
from app.models.document_segment import DocumentSegment  # noqa
from app.models.analysis_result import AnalysisResult  # noqa
from app.models.document_code_link import DocumentCodeLink  # noqa
from app.models.mismatch import Mismatch  # noqa
from app.models.tenant_billing import TenantBilling  # noqa
from app.models.analysis_run import AnalysisRun  # noqa
from app.models.consolidated_analysis import ConsolidatedAnalysis  # noqa
from app.models.initiative import Initiative  # noqa
from app.models.initiative_asset import InitiativeAsset  # noqa
from app.models.ontology_concept import OntologyConcept  # noqa
from app.models.ontology_relationship import OntologyRelationship  # noqa
from app.models.concept_mapping import ConceptMapping  # noqa

# Keep old fake DB for backward compatibility
FAKE_USERS_DB = {}
