# SPRINT 3: Task modules registry
# Each module registers its own Celery tasks via @celery_app.task decorator
from app.tasks.ontology_tasks import extract_ontology_entities
