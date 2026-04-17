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
from app.models.audit_log import AuditLog  # noqa
from app.models.notification import Notification  # noqa
from app.models.brd_sign_off import BRDSignOff  # noqa  Phase 5B: BA Sign-Off
from app.models.compliance_framework import ComplianceFramework, TenantComplianceSelection  # noqa  Phase 6
from app.models.file_suggestion import FileSuggestion  # noqa  P5C-01
from app.models.mismatch_clarification import MismatchClarification  # noqa  P5C-03
from app.models.uat_checklist_item import UATChecklistItem  # noqa  P5C-04
from app.models.ci_webhook_config import CIWebhookConfig  # noqa  P5C-06
from app.models.compliance_score_snapshot import ComplianceScoreSnapshot  # noqa  P5C-08

# Keep old fake DB for backward compatibility
FAKE_USERS_DB = {}
