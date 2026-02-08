# SPRINT 3: Task modules registry
# Each module registers its own Celery tasks via @celery_app.task decorator
# Re-export for backwards compatibility with existing imports
from app.tasks.document_pipeline import process_document_pipeline
from app.tasks.ontology_tasks import extract_ontology_entities
