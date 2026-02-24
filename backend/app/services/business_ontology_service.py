"""
Business Ontology Service (SPRINT 3)

The "brain" of DokyDoc. Extracts business entities from BOTH document analysis
results AND code analysis results, building a unified knowledge graph.

Dual-Source Architecture:
- DOCUMENTS (BRD/SRS): Extracts actors, processes, rules, requirements — the "what should be"
- CODE (Repositories): Extracts systems, APIs, data models, dependencies — the "what is"
- Cross-reference: When a concept appears in BOTH sources, it's promoted to source_type="both"
  with boosted confidence — these are the most reliable graph nodes.

Architecture:
- Called asynchronously AFTER document/code analysis completes (non-blocking)
- Uses Gemini AI for entity extraction and relationship inference
- Stores results in OntologyConcept + OntologyRelationship tables
- All operations are tenant-scoped
"""

import json
import time
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app import crud
from app.services.ai.gemini import gemini_service
from app.services.ai.prompt_manager import prompt_manager, PromptType
from app.services.cost_service import cost_service
from app.services.analysis_service import repair_json_response
from app.core.logging import LoggerMixin


class BusinessOntologyService(LoggerMixin):

    def __init__(self):
        super().__init__()
        self.logger.info("BusinessOntologyService initialized")

    def get_or_create_concept(
        self, db: Session, *, name: str, concept_type: str, tenant_id: int,
        description: str = None, confidence_score: float = None,
        source_type: str = "document", initiative_id: int = None
    ):
        """
        Idempotent concept creation with name normalization and cross-reference.
        Delegates to CRUD layer which handles deduplication and source_type promotion.
        If initiative_id is provided, the concept is scoped to that project.
        """
        return crud.ontology_concept.get_or_create(
            db=db, name=name, concept_type=concept_type,
            tenant_id=tenant_id, description=description,
            confidence_score=confidence_score, source_type=source_type,
            initiative_id=initiative_id
        )

    def link_concepts(
        self, db: Session, *, source_id: int, target_id: int,
        relationship_type: str, tenant_id: int,
        description: str = None, confidence_score: float = None
    ):
        """
        Idempotent relationship creation between two concepts.
        Prevents self-referencing edges.
        """
        if source_id == target_id:
            self.logger.debug(f"Skipping self-referencing edge for concept {source_id}")
            return None

        return crud.ontology_relationship.create_if_not_exists(
            db=db, source_concept_id=source_id, target_concept_id=target_id,
            relationship_type=relationship_type, tenant_id=tenant_id,
            description=description, confidence_score=confidence_score
        )

    async def extract_entities_from_analysis(
        self, db: Session, *, document_id: int, tenant_id: int
    ) -> Dict:
        """
        Core method: Extracts entities from ALL analysis results of a document.
        Sends structured_data to Gemini with the ENTITY_EXTRACTION prompt.
        Returns cost tracking data for billing.

        This is the method called by the async Celery task after Pass 3 completes.
        """
        self.logger.info(f"🧠 Starting entity extraction for document {document_id}")

        # Gather all analysis results for this document
        analysis_results = crud.analysis_result.get_multi_by_document(
            db=db, document_id=document_id, tenant_id=tenant_id
        )

        if not analysis_results:
            self.logger.warning(f"No analysis results found for document {document_id}")
            return {"entities_created": 0, "relationships_created": 0, "cost_inr": 0}

        # Combine structured_data from all segments into a single payload
        combined_data = []
        for result in analysis_results:
            if result.structured_data:
                combined_data.append({
                    "segment_id": result.segment_id,
                    "data": result.structured_data
                })

        if not combined_data:
            self.logger.warning(f"No structured data in analysis results for document {document_id}")
            return {"entities_created": 0, "relationships_created": 0, "cost_inr": 0}

        # Build the prompt
        prompt = prompt_manager.get_prompt(PromptType.ENTITY_EXTRACTION)
        full_prompt = f"{prompt}\n{json.dumps(combined_data, indent=2)}"

        # Rate limiting: respect Gemini 15 RPM limit
        time.sleep(4)

        try:
            response = await gemini_service.generate_content(full_prompt)
            cleaned = repair_json_response(response.text)
            extraction_result = json.loads(cleaned)
        except Exception as e:
            self.logger.error(f"Entity extraction AI call failed for document {document_id}: {e}")
            return {"entities_created": 0, "relationships_created": 0, "cost_inr": 0, "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "error": str(e)}

        # Calculate cost using actual API token counts (including thinking tokens)
        tokens = gemini_service.extract_token_usage(response)
        cost_data = cost_service.calculate_cost_from_actual_tokens(
            input_tokens=tokens['input_tokens'],
            output_tokens=tokens['output_tokens'],
            thinking_tokens=tokens['thinking_tokens'],
        )
        total_cost_inr = cost_data.get("cost_inr", 0)

        # Ingest the extracted entities and relationships
        entities = extraction_result.get("entities", [])
        relationships = extraction_result.get("relationships", [])

        # Look up initiative_id for this document via InitiativeAsset
        initiative_id = self._resolve_initiative_for_document(db=db, document_id=document_id, tenant_id=tenant_id)

        entities_created, relationships_created = self._ingest_extraction_result(
            db=db, entities=entities, relationships=relationships,
            document_id=document_id, tenant_id=tenant_id,
            initiative_id=initiative_id
        )

        self.logger.info(
            f"🧠 Entity extraction complete for document {document_id}: "
            f"{entities_created} concepts, {relationships_created} relationships, "
            f"initiative_id={initiative_id}, ₹{total_cost_inr:.4f}"
        )

        return {
            "entities_created": entities_created,
            "relationships_created": relationships_created,
            "cost_inr": total_cost_inr,
            "input_tokens": tokens['input_tokens'],
            "output_tokens": tokens['output_tokens'],
            "thinking_tokens": tokens['thinking_tokens'],
        }

    def _ingest_extraction_result(
        self, db: Session, *, entities: List[Dict], relationships: List[Dict],
        document_id: int = None, tenant_id: int, source_type: str = "document",
        initiative_id: int = None
    ) -> Tuple[int, int]:
        """
        Takes the AI-extracted entities and relationships and persists them
        to the ontology tables. Returns (entities_created, relationships_created).

        The source_type parameter enables cross-referencing:
        - "document" for entities extracted from BRD/SRS analysis
        - "code" for entities extracted from code analysis
        If a concept already exists from the other source, CRUD promotes it to "both".

        If initiative_id is provided, concepts are scoped to that project.
        """
        entities_created = 0
        concept_map = {}  # name -> OntologyConcept object (for relationship linking)

        # Phase 1: Create concepts
        for entity in entities:
            name = entity.get("name", "").strip()
            concept_type = entity.get("type", "UNKNOWN")
            confidence = entity.get("confidence", 0.5)
            context = entity.get("context", "")

            if not name or len(name) < 2:
                continue

            try:
                concept = self.get_or_create_concept(
                    db=db, name=name, concept_type=concept_type,
                    tenant_id=tenant_id, description=context,
                    confidence_score=confidence, source_type=source_type,
                    initiative_id=initiative_id
                )
                concept_map[name] = concept
                entities_created += 1
            except Exception as e:
                self.logger.warning(f"Failed to create concept '{name}': {e}")
                continue

        # Phase 2: Create relationships
        relationships_created = 0
        for rel in relationships:
            source_name = rel.get("source", "").strip()
            target_name = rel.get("target", "").strip()
            rel_type = rel.get("relationship_type", "related_to")
            confidence = rel.get("confidence", 0.5)

            source = concept_map.get(source_name)
            target = concept_map.get(target_name)

            if not source or not target:
                continue

            try:
                link = self.link_concepts(
                    db=db, source_id=source.id, target_id=target.id,
                    relationship_type=rel_type, tenant_id=tenant_id,
                    confidence_score=confidence
                )
                if link:
                    relationships_created += 1
            except Exception as e:
                self.logger.warning(f"Failed to create relationship {source_name} -> {target_name}: {e}")
                continue

        return entities_created, relationships_created

    async def extract_entities_from_code(
        self, db: Session, *, repo_id: int, tenant_id: int
    ) -> Dict:
        """
        Dual-source extraction: Extracts business entities from CODE analysis results.

        Reads all CodeComponent.structured_analysis for a repository and feeds them
        through the CODE_ENTITY_EXTRACTION prompt. Concepts are created with
        source_type="code", which triggers cross-reference promotion to "both" if
        the same concept already exists from document analysis.

        This is the code counterpart to extract_entities_from_analysis() (documents).
        """
        self.logger.info(f"🔧 Starting CODE entity extraction for repo {repo_id}")

        # Look up initiative_id for this repository via InitiativeAsset
        initiative_id = self._resolve_initiative_for_repository(db=db, repo_id=repo_id, tenant_id=tenant_id)

        # Get all completed code components for this repository
        components = db.query(crud.code_component.model).filter(
            crud.code_component.model.repository_id == repo_id,
            crud.code_component.model.tenant_id == tenant_id,
            crud.code_component.model.analysis_status == "completed"
        ).all()

        if not components:
            self.logger.warning(f"No completed code components for repo {repo_id}")
            return {"entities_created": 0, "relationships_created": 0, "cost_inr": 0}

        # Combine structured_analysis from all analyzed files into a payload
        combined_data = []
        for comp in components:
            if comp.structured_analysis:
                combined_data.append({
                    "file": comp.name,
                    "location": comp.location,
                    "summary": comp.summary or "",
                    "analysis": comp.structured_analysis
                })

        if not combined_data:
            self.logger.warning(f"No structured analysis data in code components for repo {repo_id}")
            return {"entities_created": 0, "relationships_created": 0, "cost_inr": 0}

        # For large repos, batch to avoid hitting token limits (max ~20 files per call)
        batch_size = 20
        total_entities = 0
        total_relationships = 0
        total_cost = 0.0
        total_input_tokens = 0
        total_output_tokens = 0
        total_thinking_tokens = 0

        for i in range(0, len(combined_data), batch_size):
            batch = combined_data[i:i + batch_size]

            prompt = prompt_manager.get_prompt(PromptType.CODE_ENTITY_EXTRACTION)
            full_prompt = f"{prompt}\n{json.dumps(batch, indent=2)}"

            # Rate limiting: respect Gemini 15 RPM limit
            time.sleep(4)

            try:
                response = await gemini_service.generate_content(full_prompt)
                cleaned = repair_json_response(response.text)
                extraction_result = json.loads(cleaned)
            except Exception as e:
                self.logger.error(f"Code entity extraction failed for repo {repo_id} batch {i}: {e}")
                continue

            # Calculate cost using actual API token counts (including thinking tokens)
            tokens = gemini_service.extract_token_usage(response)
            cost_data = cost_service.calculate_cost_from_actual_tokens(
                input_tokens=tokens['input_tokens'],
                output_tokens=tokens['output_tokens'],
                thinking_tokens=tokens['thinking_tokens'],
            )
            total_cost += cost_data.get("cost_inr", 0)
            total_input_tokens += tokens['input_tokens']
            total_output_tokens += tokens['output_tokens']
            total_thinking_tokens += tokens['thinking_tokens']

            # Ingest with source_type="code" — triggers cross-reference if concept exists from documents
            entities = extraction_result.get("entities", [])
            relationships = extraction_result.get("relationships", [])

            batch_entities, batch_rels = self._ingest_extraction_result(
                db=db, entities=entities, relationships=relationships,
                tenant_id=tenant_id, source_type="code",
                initiative_id=initiative_id
            )
            total_entities += batch_entities
            total_relationships += batch_rels

        self.logger.info(
            f"🔧 Code entity extraction complete for repo {repo_id}: "
            f"{total_entities} concepts, {total_relationships} relationships, "
            f"₹{total_cost:.4f}. Reconciliation pass will create bridge relationships."
        )

        return {
            "entities_created": total_entities,
            "relationships_created": total_relationships,
            "cost_inr": total_cost,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "thinking_tokens": total_thinking_tokens,
        }

    async def reconcile_document_code_concepts(
        self, db: Session, *, tenant_id: int
    ) -> Dict:
        """
        RECONCILIATION PASS: The critical step that connects the two layers.

        Takes all document-layer concepts and all code-layer concepts for a tenant,
        sends them to Gemini to determine:
        1. Which code concepts implement which document concepts (bridge relationships)
        2. Which document concepts have NO code counterpart (unimplemented requirements)
        3. Which code concepts have NO document counterpart (undocumented features)
        4. Where code CONTRADICTS what documents say (mismatches)

        This is what makes the dual-source graph actually useful — without it, you just
        have two disconnected subgraphs.
        """
        self.logger.info(f"🔗 Starting source reconciliation for tenant {tenant_id}")

        # Get concepts from each layer
        doc_concepts = crud.ontology_concept.get_by_source_type(
            db=db, source_type="document", tenant_id=tenant_id, limit=500
        )
        code_concepts = crud.ontology_concept.get_by_source_type(
            db=db, source_type="code", tenant_id=tenant_id, limit=500
        )

        if not doc_concepts or not code_concepts:
            self.logger.info(
                f"Reconciliation skipped: {len(doc_concepts or [])} document concepts, "
                f"{len(code_concepts or [])} code concepts — need both."
            )
            return {"bridges_created": 0, "contradictions_found": 0}

        # Build the payload for AI
        doc_payload = [
            {"name": c.name, "type": c.concept_type, "description": c.description or ""}
            for c in doc_concepts
        ]
        code_payload = [
            {"name": c.name, "type": c.concept_type, "description": c.description or ""}
            for c in code_concepts
        ]

        reconciliation_data = {
            "document_concepts": doc_payload,
            "code_concepts": code_payload
        }

        prompt = prompt_manager.get_prompt(PromptType.SOURCE_RECONCILIATION)
        full_prompt = f"{prompt}\n{json.dumps(reconciliation_data, indent=2)}"

        time.sleep(4)  # Rate limiting

        try:
            response = await gemini_service.generate_content(full_prompt)
            cleaned = repair_json_response(response.text)
            result = json.loads(cleaned)
        except Exception as e:
            self.logger.error(f"Reconciliation AI call failed for tenant {tenant_id}: {e}")
            return {"bridges_created": 0, "contradictions_found": 0, "error": str(e)}

        # Calculate cost using actual API token counts (including thinking tokens)
        tokens = gemini_service.extract_token_usage(response)
        cost_data = cost_service.calculate_cost_from_actual_tokens(
            input_tokens=tokens['input_tokens'],
            output_tokens=tokens['output_tokens'],
            thinking_tokens=tokens['thinking_tokens'],
        )
        total_cost = cost_data.get("cost_inr", 0)

        # Build name->concept lookups for each layer
        doc_lookup = {c.name.lower(): c for c in doc_concepts}
        code_lookup = {c.name.lower(): c for c in code_concepts}

        # Process bridge relationships
        bridges_created = 0
        for bridge in result.get("bridges", []):
            doc_name = bridge.get("document_concept", "").strip().lower()
            code_name = bridge.get("code_concept", "").strip().lower()
            rel_type = bridge.get("relationship", "implements")
            confidence = bridge.get("confidence", 0.5)
            reasoning = bridge.get("reasoning", "")

            doc_concept = doc_lookup.get(doc_name)
            code_concept = code_lookup.get(code_name)

            if not doc_concept or not code_concept:
                continue

            try:
                link = self.link_concepts(
                    db=db,
                    source_id=code_concept.id,  # code → implements → document
                    target_id=doc_concept.id,
                    relationship_type=rel_type,
                    tenant_id=tenant_id,
                    description=reasoning,
                    confidence_score=confidence
                )
                if link:
                    bridges_created += 1

                    # If it's a strong "implements" match, promote BOTH concepts to "both"
                    if rel_type == "implements" and confidence >= 0.8:
                        crud.ontology_concept.promote_to_both(
                            db=db, concept_id=doc_concept.id, tenant_id=tenant_id
                        )
                        crud.ontology_concept.promote_to_both(
                            db=db, concept_id=code_concept.id, tenant_id=tenant_id
                        )
            except Exception as e:
                self.logger.warning(f"Failed to create bridge {code_name} → {doc_name}: {e}")

        # Process contradictions — create "contradicts" relationships
        contradictions_found = 0
        for contradiction in result.get("contradictions", []):
            doc_name = contradiction.get("document_concept", "").strip().lower()
            code_name = contradiction.get("code_concept", "").strip().lower()
            severity = contradiction.get("severity", "medium")

            doc_concept = doc_lookup.get(doc_name)
            code_concept = code_lookup.get(code_name)

            if not doc_concept or not code_concept:
                continue

            try:
                detail = (
                    f"MISMATCH [{severity.upper()}]: "
                    f"Document says: {contradiction.get('document_says', '?')}. "
                    f"Code does: {contradiction.get('code_does', '?')}. "
                    f"Action: {contradiction.get('recommended_action', '?')}"
                )
                self.link_concepts(
                    db=db,
                    source_id=code_concept.id,
                    target_id=doc_concept.id,
                    relationship_type="contradicts",
                    tenant_id=tenant_id,
                    description=detail,
                    confidence_score=0.9
                )
                contradictions_found += 1
            except Exception as e:
                self.logger.warning(f"Failed to create contradiction link: {e}")

        # Log unimplemented/undocumented for visibility (these don't create relationships)
        unimplemented = result.get("unimplemented", [])
        undocumented = result.get("undocumented", [])

        self.logger.info(
            f"🔗 Reconciliation complete for tenant {tenant_id}: "
            f"{bridges_created} bridges, {contradictions_found} contradictions, "
            f"{len(unimplemented)} unimplemented requirements, "
            f"{len(undocumented)} undocumented code features, "
            f"₹{total_cost:.4f}"
        )

        return {
            "bridges_created": bridges_created,
            "contradictions_found": contradictions_found,
            "unimplemented_requirements": unimplemented,
            "undocumented_features": undocumented,
            "cost_inr": total_cost
        }

    async def detect_synonyms(
        self, db: Session, *, tenant_id: int
    ) -> Dict:
        """
        Scans all concepts for a tenant and detects synonym pairs using AI.
        Creates 'is_synonym_of' relationships between detected synonyms.
        """
        self.logger.info(f"🔍 Starting synonym detection for tenant {tenant_id}")

        concepts = crud.ontology_concept.get_all_active(db=db, tenant_id=tenant_id)
        if len(concepts) < 2:
            return {"synonym_pairs_found": 0}

        concept_names = [c.name for c in concepts]

        prompt = prompt_manager.get_prompt(PromptType.SYNONYM_DETECTION)
        full_prompt = f"{prompt}\n{json.dumps(concept_names, indent=2)}"

        time.sleep(4)

        try:
            response = await gemini_service.generate_content(full_prompt)
            cleaned = repair_json_response(response.text)
            result = json.loads(cleaned)
        except Exception as e:
            self.logger.error(f"Synonym detection failed for tenant {tenant_id}: {e}")
            return {"synonym_pairs_found": 0, "cost_inr": 0, "error": str(e)}

        # Calculate cost using actual API token counts (including thinking tokens)
        tokens = gemini_service.extract_token_usage(response)
        cost_data = cost_service.calculate_cost_from_actual_tokens(
            input_tokens=tokens['input_tokens'],
            output_tokens=tokens['output_tokens'],
            thinking_tokens=tokens['thinking_tokens'],
        )

        synonym_pairs = result.get("synonym_pairs", [])
        pairs_created = 0

        # Build a name -> concept lookup
        name_lookup = {c.name.lower(): c for c in concepts}

        for pair in synonym_pairs:
            confidence = pair.get("confidence", 0.5)
            if confidence < 0.8:
                continue  # Only high-confidence synonyms

            term_a = pair.get("term_a", "").strip().lower()
            term_b = pair.get("term_b", "").strip().lower()

            concept_a = name_lookup.get(term_a)
            concept_b = name_lookup.get(term_b)

            if not concept_a or not concept_b:
                continue

            try:
                self.link_concepts(
                    db=db, source_id=concept_a.id, target_id=concept_b.id,
                    relationship_type="is_synonym_of", tenant_id=tenant_id,
                    description=pair.get("reasoning", ""),
                    confidence_score=confidence
                )
                # Create the reverse synonym link too
                self.link_concepts(
                    db=db, source_id=concept_b.id, target_id=concept_a.id,
                    relationship_type="is_synonym_of", tenant_id=tenant_id,
                    confidence_score=confidence
                )
                pairs_created += 1
            except Exception as e:
                self.logger.warning(f"Failed to create synonym pair: {e}")

        self.logger.info(
            f"🔍 Synonym detection complete: {pairs_created} pairs found, "
            f"₹{cost_data.get('cost_inr', 0):.4f}"
        )
        return {
            "synonym_pairs_found": pairs_created,
            "cost_inr": cost_data.get("cost_inr", 0),
            "input_tokens": tokens['input_tokens'],
            "output_tokens": tokens['output_tokens'],
            "thinking_tokens": tokens['thinking_tokens'],
        }

    def _resolve_initiative_for_document(
        self, db: Session, *, document_id: int, tenant_id: int
    ) -> Optional[int]:
        """Look up which initiative/project a document belongs to via InitiativeAsset."""
        try:
            from app.models.initiative_asset import InitiativeAsset
            asset = db.query(InitiativeAsset).filter(
                InitiativeAsset.tenant_id == tenant_id,
                InitiativeAsset.asset_type == "DOCUMENT",
                InitiativeAsset.asset_id == document_id,
                InitiativeAsset.is_active == True
            ).first()
            return asset.initiative_id if asset else None
        except Exception:
            return None

    def _resolve_initiative_for_repository(
        self, db: Session, *, repo_id: int, tenant_id: int
    ) -> Optional[int]:
        """Look up which initiative/project a repository belongs to via InitiativeAsset."""
        try:
            from app.models.initiative_asset import InitiativeAsset
            asset = db.query(InitiativeAsset).filter(
                InitiativeAsset.tenant_id == tenant_id,
                InitiativeAsset.asset_type == "REPOSITORY",
                InitiativeAsset.asset_id == repo_id,
                InitiativeAsset.is_active == True
            ).first()
            return asset.initiative_id if asset else None
        except Exception:
            return None

    def get_domain_vocabulary(
        self, db: Session, *, tenant_id: int
    ) -> List[Dict]:
        """Get all concepts grouped by type for a tenant (domain vocabulary)."""
        concepts = crud.ontology_concept.get_all_active(db=db, tenant_id=tenant_id)
        vocabulary = {}
        for c in concepts:
            if c.concept_type not in vocabulary:
                vocabulary[c.concept_type] = []
            vocabulary[c.concept_type].append({
                "id": c.id,
                "name": c.name,
                "confidence": c.confidence_score
            })
        return vocabulary


# Global instance
business_ontology_service = BusinessOntologyService()
