from .user import User
from .document import Document  # Make sure this line exists
from .document_code_link import DocumentCodeLink  # And this one
from .code_component import CodeComponent  # And this one if you have it
from .mismatch import Mismatch
from .analysis_result import AnalysisResult, AnalysisResultStatus
from .document_segment import DocumentSegment, SegmentStatus
from .consolidated_analysis import ConsolidatedAnalysis
from .analysis_run import AnalysisRun, AnalysisRunStatus
from .ontology_concept import OntologyConcept
from .ontology_relationship import OntologyRelationship
from .initiative import Initiative
from .initiative_asset import InitiativeAsset
from .tenant_billing import TenantBilling
from .tenant import Tenant
from .task import Task, TaskComment, TaskStatus, TaskPriority
from .usage_log import UsageLog, FeatureType, OperationType
from .repository import Repository  # SPRINT 3: Code Analysis Engine
from .cross_project_mapping import CrossProjectMapping  # SPRINT 4: Cross-Project Mapping
from .knowledge_graph_version import KnowledgeGraphVersion  # Graph versioning
from .requirement_trace import RequirementTrace  # BRD-to-Code traceability
from .requirement_atom import RequirementAtom  # Atomic BRD requirements for 9-pass validation
from .audit_log import AuditLog  # Sprint 5: Audit Trail
from .notification import Notification  # Sprint 5: Notifications
from .approval import Approval  # Sprint 6: Approval Workflow
from .conversation import Conversation, ChatMessage  # Sprint 7: RAG/Chat Assistant
from .document_version import DocumentVersion  # Sprint 8: Version Comparison
from .notification_preference import NotificationPreference  # Sprint 8: Notification Preferences
from .api_key import ApiKey  # Sprint 8: API Key Authentication
from .generated_doc import GeneratedDoc  # Sprint 8: Auto Docs
from .integration_config import IntegrationConfig  # Sprint 8: Integrations
from .training_example import TrainingExample, FeedbackSource  # Phase 1: Data Flywheel
from .brd_sign_off import BRDSignOff  # Phase 5B: BA Sign-Off Workflow
from .compliance_framework import ComplianceFramework, TenantComplianceSelection  # Phase 6: Compliance Library
from .file_suggestion import FileSuggestion  # P5C-01: Smart File Suggestion Engine
from .mismatch_clarification import MismatchClarification  # P5C-03: Clarification Workflow
from .uat_checklist_item import UATChecklistItem  # P5C-04: UAT Checklist
from .ci_webhook_config import CIWebhookConfig  # P5C-06: CI Webhook
from .compliance_score_snapshot import ComplianceScoreSnapshot  # P5C-08: Compliance Trend
from .code_data_flow_edge import CodeDataFlowEdge  # Phase 3: Request Data Flow Graph
