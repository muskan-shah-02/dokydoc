import json
import time
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app import crud, schemas
from app.services.document_parser import MultiModalDocumentParser
from app.services.ai.gemini import gemini_service
from app.services.ai.prompt_manager import prompt_manager, PromptType
from app.services.analysis_run_service import AnalysisRunService
from app.services.cost_service import cost_service  # ✅ SPRINT 1 PHASE 2 FIX
from app.services.billing_enforcement_service import billing_enforcement_service, InsufficientBalanceException, MonthlyLimitExceededException  # ✅ SPRINT 2 BILLING FIX
from app.core.logging import LoggerMixin
from app.core.exceptions import AIAnalysisException, DocumentProcessingException
from app.models import SegmentStatus, AnalysisResultStatus

# Configuration: Context window for segment analysis (characters)
# Provides surrounding text to AI for better understanding
SEGMENT_CONTEXT_SIZE = 1500  # Tunable: increase for more context, decrease for cost savings

def repair_json_response(response_text: str) -> str:
    """
    Attempt to repair common JSON formatting issues from AI responses.
    """
    if not response_text:
        return "{}"
    
    cleaned = response_text.strip()
    
    # Remove markdown code blocks
    if cleaned.startswith('```json'):
        cleaned = cleaned[7:]
    elif cleaned.startswith('```'):
        cleaned = cleaned[3:]
    
    if cleaned.endswith('```'):
        cleaned = cleaned[:-3]
    
    cleaned = cleaned.strip()
    
    # Basic heuristics to fix common issues
    if not cleaned.startswith('{') and not cleaned.startswith('['):
        json_start = max(cleaned.find('{'), cleaned.find('['))
        if json_start != -1:
            cleaned = cleaned[json_start:]
    
    # Regex-based repairs (from your original code)
    import re
    
    # For objects starting with {
    if cleaned.startswith('{'):
        brace_count = 0
        json_end = -1
        in_string = False
        escape_next = False
        
        for i, char in enumerate(cleaned):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break
        if json_end != -1:
            cleaned = cleaned[:json_end]
    
    # For arrays starting with [
    elif cleaned.startswith('['):
        bracket_count = 0
        json_end = -1
        in_string = False
        escape_next = False
        
        for i, char in enumerate(cleaned):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if not in_string:
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        json_end = i + 1
                        break
        if json_end != -1:
            cleaned = cleaned[:json_end]
    
    # Fix missing commas
    cleaned = re.sub(r'}\s*{', '},{', cleaned)
    cleaned = re.sub(r']\s*{', '},{', cleaned)
    cleaned = re.sub(r'}\s*\[', '},[', cleaned)
    cleaned = re.sub(r']\s*\[', '],[', cleaned)
    
    # Add missing closing braces
    if cleaned.startswith('{'):
        open_braces = cleaned.count('{') - cleaned.count('}')
        if open_braces > 0:
            cleaned += '}' * open_braces
    elif cleaned.startswith('['):
        open_brackets = cleaned.count('[') - cleaned.count(']')
        if open_brackets > 0:
            cleaned += ']' * open_brackets
    
    return cleaned

class DocumentAnalysisEngine(LoggerMixin):
    """
    Multi-pass Document Analysis Engine (DAE) that transforms documents into structured, 
    analyzable data through intelligent composition analysis and segmentation.
    """
    
    def __init__(self):
        super().__init__()
        self._running_documents = set()  # Track documents currently being analyzed
        self._api_call_counter = {}  # Track API calls per document
        self._cost_tracker = {}  # ✅ Track real costs per document: {doc_id: {pass_name: {cost_inr, tokens}}}
        self.logger.info("DocumentAnalysisEngine initialized")
    
    def _increment_api_calls(self, document_id: int):
        """Helper method to increment API call counter for a document."""
        if document_id in self._api_call_counter:
            self._api_call_counter[document_id] += 1

    # --- NEW: Helper to check for stop signal ---
    def _check_stop_signal(self, db: Session, document_id: int, tenant_id: int) -> bool:
        """Checks if the user has requested to stop the analysis."""
        # We must re-fetch the document from DB to see the latest status
        doc = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
        if doc and doc.status == "stopping":
            self.logger.info(f"🛑 Analysis STOPPED by user for document {document_id}")
            # Set final stopped state
            crud.document.update(
                db=db,
                db_obj=doc,
                obj_in={"status": "stopped", "error_message": "Analysis manually halted by user."}
            )
            return True
        return False

    async def analyze_document(self, db: Session, document_id: int, tenant_id: int = None, learning_mode: bool = False, analysis_run_id: int = None) -> bool:
        """
        Performs the complete multi-pass analysis on a document.

        Args:
            db: Database session
            document_id: ID of the document to analyze
            tenant_id: Tenant ID for multi-tenancy filtering
            learning_mode: Whether to use learning mode
            analysis_run_id: Optional analysis run ID for tracking
        """
        # Check if document is already being analyzed
        if document_id in self._running_documents:
            self.logger.warning(f"Analysis already running for document {document_id}")
            raise DocumentProcessingException(
                message="Analysis already in progress for this document",
                document_id=document_id,
                details={"status": "already_running"}
            )

        # Add document to running set and initialize API call counter + cost tracker
        self._running_documents.add(document_id)
        self._api_call_counter[document_id] = 0
        self._cost_tracker[document_id] = {}  # ✅ Initialize cost tracking
        self.logger.info(f"📊 Starting multi-pass analysis for document_id: {document_id}")

        try:
            # Get the document - use tenant_id if provided, otherwise query without it
            if tenant_id:
                document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
            else:
                # Fallback: query without tenant_id filter for backwards compatibility
                document = db.query(models.Document).filter(models.Document.id == document_id).first()
            if not document:
                self.logger.error(f"Document {document_id} not found")
                return False

            if not document.raw_text:
                self.logger.error(f"Document {document_id} has no raw_text to analyze")
                return False

            # ✅ BILLING CHECK: Check if tenant can afford this analysis BEFORE calling Gemini
            self.logger.info(f"💰 Checking billing: tenant {document.tenant_id} for document {document_id}")
            try:
                billing_check = billing_enforcement_service.check_can_afford_analysis(
                    db=db,
                    tenant_id=document.tenant_id,
                    estimated_cost_inr=15.0  # Estimated cost for full 3-pass document analysis
                )

                if not billing_check["can_proceed"]:
                    error_msg = f"Insufficient funds: {billing_check['reason']}"
                    self.logger.error(f"❌ {error_msg}")
                    crud.document.update(
                        db=db,
                        db_obj=document,
                        obj_in={"status": "failed", "error_message": error_msg}
                    )
                    return False

                self.logger.info(f"✅ Billing check passed for tenant {document.tenant_id}")

            except (InsufficientBalanceException, MonthlyLimitExceededException) as e:
                error_msg = str(e)
                self.logger.error(f"❌ Billing enforcement failed: {error_msg}")
                crud.document.update(
                    db=db,
                    db_obj=document,
                    obj_in={"status": "failed", "error_message": error_msg}
                )
                return False

            try:
                # --- CHECK 1: Before Pass 1 ---
                if self._check_stop_signal(db, document_id, document.tenant_id): return False

                # Pass 1: Composition & Classification
                self.logger.info(f"Document {document_id}: Starting Pass 1 - Composition & Classification")
                composition_analysis = await self._pass_1_composition_classification(document.raw_text, document_id)
                
                # Save composition analysis to document
                document.composition_analysis = composition_analysis
                db.commit()
                
                # --- CHECK 2: Before Pass 2 ---
                if self._check_stop_signal(db, document_id, document.tenant_id): return False

                # Pass 2: Deep Content Segmentation
                self.logger.info(f"Document {document_id}: Starting Pass 2 - Deep Content Segmentation")
                segments_created = await self._pass_2_content_segmentation(
                    db, document_id, document.raw_text, composition_analysis, analysis_run_id
                )
                
                # --- CHECK 3: Before Pass 3 ---
                if self._check_stop_signal(db, document_id, document.tenant_id): return False

                # Pass 3: Profile-Based Structured Extraction
                self.logger.info(f"Document {document_id}: Starting Pass 3 - Profile-Based Structured Extraction")
                await self._pass_3_structured_extraction(db, document_id, analysis_run_id)
                
                # --- CHECK 4: Before Learning Mode ---
                if self._check_stop_signal(db, document_id, document.tenant_id): return False

                # Learning Mode: Feed to Business Ontology Engine
                if learning_mode:
                    self.logger.info(f"Document {document_id}: Learning mode enabled - feeding to BOE")
                    await self._feed_to_business_ontology(db, document_id)

                # ✅ SPRINT 1 PHASE 2: Calculate REAL costs from tracked token usage
                cost_breakdown = self._cost_tracker.get(document_id, {})
                total_cost_inr = sum(pass_data.get('cost_inr', 0) for pass_data in cost_breakdown.values())
                total_input_tokens = sum(pass_data.get('input_tokens', 0) for pass_data in cost_breakdown.values())
                total_output_tokens = sum(pass_data.get('output_tokens', 0) for pass_data in cost_breakdown.values())
                total_tokens = total_input_tokens + total_output_tokens
                total_calls = self._api_call_counter.get(document_id, 0)

                self.logger.info(f"📊 ANALYSIS COMPLETE for document {document_id}")
                self.logger.info(f"💰 TOTAL GEMINI API CALLS: {total_calls}")
                self.logger.info(f"📊 TOTAL TOKENS: {total_tokens:,} ({total_input_tokens:,} input + {total_output_tokens:,} output)")
                self.logger.info(f"💵 ACTUAL COST: ₹{total_cost_inr:.4f} INR (~${total_cost_inr/84:.4f} USD)")
                self.logger.info(f"📋 Cost Breakdown by Pass:")
                for pass_name, pass_data in cost_breakdown.items():
                    self.logger.info(
                        f"   - {pass_name}: ₹{pass_data.get('cost_inr', 0):.4f} "
                        f"({pass_data.get('input_tokens', 0):,} in + {pass_data.get('output_tokens', 0):,} out)"
                    )

                # Final Success State (only update if we haven't stopped)
                final_check = crud.document.get(db=db, id=document_id, tenant_id=document.tenant_id)
                if final_check.status != "stopped":
                    crud.document.update(
                        db=db,
                        db_obj=document,
                        obj_in={
                            "status": "completed",
                            "progress": 100,
                            "ai_cost_inr": total_cost_inr,  # ✅ Real cost tracking
                            "token_count_input": total_input_tokens,
                            "token_count_output": total_output_tokens,
                            "cost_breakdown": cost_breakdown  # ✅ Detailed breakdown
                        }
                    )

                return True
                
            except Exception as e:
                self.logger.error(f"Error during multi-pass analysis for document {document_id}: {e}")
                # Only set to failed if it wasn't a user stop
                current_doc = crud.document.get(db=db, id=document_id, tenant_id=document.tenant_id if document else tenant_id)
                if current_doc and current_doc.status != "stopped":
                    crud.document.update(db=db, db_obj=current_doc, obj_in={"status": "analysis_failed", "error_message": str(e)})
                return False
        finally:
            self._running_documents.discard(document_id)
            self._api_call_counter.pop(document_id, None)
            self._cost_tracker.pop(document_id, None)  # ✅ Cleanup cost tracker
            self.logger.debug(f"Released analysis lock for document {document_id}")
    
    async def _pass_1_composition_classification(self, raw_text: str, document_id: int) -> Dict:
        """Pass 1: Analyzes document composition."""
        try:
            prompt = prompt_manager.get_prompt(PromptType.DOCUMENT_COMPOSITION)
            full_prompt = f"{prompt}\n\nDOCUMENT TEXT TO ANALYZE:\n{raw_text[:15000]}" # Truncate large texts for Pass 1 summary

            self.logger.info("🔍 PASS 1: Starting composition analysis - 1 Gemini API call")
            self._increment_api_calls(document_id)

            response = await gemini_service.generate_content(full_prompt)

            # ✅ SPRINT 1 PHASE 2: Extract token counts and calculate real cost
            input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) if hasattr(response, 'usage_metadata') else 0
            output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) if hasattr(response, 'usage_metadata') else 0

            cost_data = cost_service.calculate_cost(full_prompt, response.text)
            self._cost_tracker[document_id]['pass_1_composition'] = {
                'cost_inr': cost_data['cost_inr'],
                'input_tokens': input_tokens or cost_data['input_tokens'],  # Use real count if available
                'output_tokens': output_tokens or cost_data['output_tokens']
            }

            cleaned_response = repair_json_response(response.text)

            try:
                return json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse Gemini response as JSON: {e}")
                raise AIAnalysisException("Failed to parse composition analysis response", model="gemini")

        except Exception as e:
            self.logger.error(f"Error in Pass 1: {e}")
            raise AIAnalysisException("Composition classification failed", model="gemini", details={"error": str(e)})
    
    async def _pass_2_content_segmentation(
        self, db: Session, document_id: int, raw_text: str, composition_analysis: Dict, analysis_run_id: int = None
    ) -> bool:
        """Pass 2: Creates document segments."""
        try:
            # Clean up existing segments
            self.logger.info(f"Cleaning up existing segments for document {document_id}")
            existing_segments = crud.document_segment.get_multi_by_document(db=db, document_id=document_id)
            for segment in existing_segments:
                crud.analysis_result.delete_by_segment(db=db, segment_id=segment.id)
            crud.document_segment.delete_by_document(db=db, document_id=document_id)
            
            prompt = prompt_manager.get_prompt(PromptType.CONTENT_SEGMENTATION)
            full_prompt = f"{prompt}\n\nCOMPOSITION ANALYSIS:\n{json.dumps(composition_analysis, indent=2)}\n\nDOCUMENT TEXT:\n{raw_text}"

            self.logger.info("🔍 PASS 2: Starting content segmentation - 1 Gemini API call")
            self._increment_api_calls(document_id)

            response = await gemini_service.generate_content(full_prompt)

            # ✅ SPRINT 1 PHASE 2: Extract token counts and calculate real cost
            input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) if hasattr(response, 'usage_metadata') else 0
            output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) if hasattr(response, 'usage_metadata') else 0

            cost_data = cost_service.calculate_cost(full_prompt, response.text)
            self._cost_tracker[document_id]['pass_2_segmentation'] = {
                'cost_inr': cost_data['cost_inr'],
                'input_tokens': input_tokens or cost_data['input_tokens'],
                'output_tokens': output_tokens or cost_data['output_tokens']
            }

            cleaned_response = repair_json_response(response.text)
            
            try:
                segmentation_data = json.loads(cleaned_response)
                segments = segmentation_data.get("segments", [])
                composition = composition_analysis.get("composition", {})
                
                valid_segments = []
                for segment_info in segments:
                    if composition.get(segment_info["segment_type"], 0) > 0:
                        valid_segments.append(segment_info)
                
                for segment_info in valid_segments:
                    crud.document_segment.create(db=db, obj_in=schemas.DocumentSegmentCreate(
                        segment_type=segment_info["segment_type"],
                        start_char_index=segment_info["start_char_index"],
                        end_char_index=segment_info["end_char_index"],
                        document_id=document_id,
                        analysis_run_id=analysis_run_id
                    ))
                
                self.logger.info(f"Created {len(valid_segments)} document segments")
                return True
                
            except json.JSONDecodeError as e:
                raise AIAnalysisException("Failed to parse segmentation response", model="gemini")
                
        except Exception as e:
            self.logger.error(f"Error in Pass 2: {e}")
            raise DocumentProcessingException("Content segmentation failed", document_id=document_id, details={"error": str(e)})
    
    async def _pass_3_structured_extraction(self, db: Session, document_id: int, analysis_run_id: int = None) -> bool:
        """Pass 3: Performs structured extraction on each document segment."""
        try:
            run_service = AnalysisRunService() if analysis_run_id else None
            segments = crud.document_segment.get_by_document(db=db, document_id=document_id)
            
            if not segments:
                self.logger.warning(f"No segments found for document {document_id}")
                return False
            
            self.logger.info(f"🔍 PASS 3: Starting structured extraction - {len(segments)} segments")
            base_prompt = prompt_manager.get_prompt(PromptType.STRUCTURED_EXTRACTION)

            # Get document - get tenant_id from segments if available
            tenant_id = segments[0].tenant_id if segments else None
            if tenant_id:
                document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
            else:
                document = db.query(models.Document).filter(models.Document.id == document_id).first()

            # ✅ SPRINT 1 PHASE 2: Initialize Pass 3 cost tracking
            pass_3_cost_inr = 0
            pass_3_input_tokens = 0
            pass_3_output_tokens = 0

            for i, segment in enumerate(segments):
                # --- CRITICAL: Check stop signal inside the loop ---
                if self._check_stop_signal(db, document_id, document.tenant_id if document else tenant_id):
                    return False
                
                # --- Rate Limit Throttle (Fix for 429 Error) ---
                # Wait 4 seconds between segments to respect 15 RPM limit
                time.sleep(4) 

                try:
                    segment.status = SegmentStatus.PROCESSING
                    db.commit()
                    
                    # Extract segment with surrounding context for better AI understanding
                    doc_length = len(document.raw_text)

                    # Calculate context boundaries (handle document edges safely)
                    context_start = max(0, segment.start_char_index - SEGMENT_CONTEXT_SIZE)
                    context_end = min(doc_length, segment.end_char_index + SEGMENT_CONTEXT_SIZE)

                    # Extract text sections
                    before_context = document.raw_text[context_start:segment.start_char_index]
                    segment_text = document.raw_text[segment.start_char_index:segment.end_char_index]
                    after_context = document.raw_text[segment.end_char_index:context_end]

                    # Build enhanced prompt with context markers
                    full_prompt = f"""{base_prompt}

SEGMENT TYPE: {segment.segment_type}

--- CONTEXT BEFORE (for reference only) ---
{before_context}

--- PRIMARY SEGMENT TO ANALYZE ---
{segment_text}

--- CONTEXT AFTER (for reference only) ---
{after_context}

INSTRUCTIONS: Focus your analysis on the PRIMARY SEGMENT, but use the surrounding context to understand references, dependencies, and relationships."""
                    
                    self.logger.info(f"🤖 Analyzing segment {segment.id} ({i+1}/{len(segments)})")
                    self._increment_api_calls(document_id)

                    response = await gemini_service.generate_content(full_prompt)

                    # ✅ SPRINT 1 PHASE 2: Track cost for this segment
                    input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) if hasattr(response, 'usage_metadata') else 0
                    output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) if hasattr(response, 'usage_metadata') else 0

                    cost_data = cost_service.calculate_cost(full_prompt, response.text)
                    pass_3_cost_inr += cost_data['cost_inr']
                    pass_3_input_tokens += input_tokens or cost_data['input_tokens']
                    pass_3_output_tokens += output_tokens or cost_data['output_tokens']

                    try:
                        structured_data = json.loads(repair_json_response(response.text))
                    except json.JSONDecodeError:
                        # Double repair attempt
                        try:
                            structured_data = json.loads(repair_json_response(repair_json_response(response.text)))
                        except:
                            self.logger.error(f"Failed to parse JSON for segment {segment.id}")
                            continue
                    
                    if structured_data:
                        crud.analysis_result.create_for_document(db=db, obj_in=schemas.AnalysisResultCreate(
                            segment_id=segment.id,
                            document_id=document_id,
                            structured_data=structured_data,
                            status=AnalysisResultStatus.SUCCESS
                        ))
                        segment.status = SegmentStatus.COMPLETED
                    else:
                        segment.status = SegmentStatus.FAILED
                        segment.last_error = "Empty structured data"
                    
                    db.commit()
                    
                    # Update progress
                    progress = int(((i + 1) / len(segments)) * 100)
                    total_progress = 50 + int(progress / 2)
                    crud.document.update(db=db, db_obj=document, obj_in={"progress": total_progress, "status": "pass_3_extraction"})
                    
                    if run_service and analysis_run_id:
                        run_service.update_run_progress(db=db, run_id=analysis_run_id)

                except Exception as e:
                    self.logger.error(f"Error processing segment {segment.id}: {e}")
                    segment.status = SegmentStatus.FAILED
                    segment.last_error = str(e)
                    db.commit()
                    continue

            # ✅ SPRINT 1 PHASE 2: Save accumulated Pass 3 costs
            self._cost_tracker[document_id]['pass_3_extraction'] = {
                'cost_inr': pass_3_cost_inr,
                'input_tokens': pass_3_input_tokens,
                'output_tokens': pass_3_output_tokens,
                'segments_analyzed': len(segments)
            }

            return True
            
        except Exception as e:
            self.logger.error(f"Error in Pass 3: {e}")
            raise DocumentProcessingException("Structured extraction failed", document_id=document_id, details={"error": str(e)})
    
    async def _feed_to_business_ontology(self, db: Session, document_id: int) -> bool:
        """Feeds extracted entities to the Business Ontology Engine."""
        try:
            self.logger.info(f"Feeding document {document_id} to Business Ontology Engine")
            # Placeholder for BOE integration
            return True
        except Exception as e:
            self.logger.error(f"Error feeding to Business Ontology Engine: {e}")
            return False

# Create a global instance
dae = DocumentAnalysisEngine()

async def run_initial_analysis(db: Session, document_id: int):
    return await dae.analyze_document(db, document_id)