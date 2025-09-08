# This is the content for your NEW file at:
# backend/app/services/analysis_service.py

import json
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app import crud, schemas
from app.services.document_parser import MultiModalDocumentParser
from app.services.ai.gemini import gemini_service
from app.services.ai.prompt_manager import prompt_manager, PromptType
from app.core.logging import LoggerMixin
from app.core.exceptions import AIAnalysisException, DocumentProcessingException

def repair_json_response(response_text: str) -> str:
    """
    Attempt to repair common JSON formatting issues from AI responses.
    
    Args:
        response_text: Raw AI response that may contain JSON formatting issues
        
    Returns:
        str: Cleaned JSON string
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
        # Try to find the first { or [
        json_start = max(cleaned.find('{'), cleaned.find('['))
        if json_start != -1:
            cleaned = cleaned[json_start:]
    
    # Add missing closing braces (simple heuristic)
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
        self.logger.info("DocumentAnalysisEngine initialized")
    
    async def analyze_document(self, db: Session, document_id: int, learning_mode: bool = False) -> bool:
        """
        Performs the complete multi-pass analysis on a document.
        
        Args:
            db: Database session
            document_id: ID of the document to analyze
            learning_mode: If True, feeds extracted entities to the Business Ontology Engine
            
        Returns:
            bool: True if analysis completed successfully, False otherwise
        """
        # Check if document is already being analyzed
        if document_id in self._running_documents:
            self.logger.warning(f"Analysis already running for document {document_id}")
            raise DocumentProcessingException(
                message="Analysis already in progress for this document",
                document_id=document_id,
                details={"status": "already_running"}
            )
        
        # Add document to running set
        self._running_documents.add(document_id)
        self.logger.info(f"Starting multi-pass analysis for document_id: {document_id}")
        
        try:
            
            # Get the document
            document = crud.document.get(db=db, id=document_id)
            if not document:
                self.logger.error(f"Document {document_id} not found")
                return False
                
            if not document.raw_text:
                self.logger.error(f"Document {document_id} has no raw_text to analyze")
                return False
            
            try:
                # Pass 1: Composition & Classification
                self.logger.info(f"Document {document_id}: Starting Pass 1 - Composition & Classification")
                composition_analysis = await self._pass_1_composition_classification(document.raw_text)
                
                # Save composition analysis to document
                document.composition_analysis = composition_analysis
                db.commit()
                
                # Pass 2: Deep Content Segmentation
                self.logger.info(f"Document {document_id}: Starting Pass 2 - Deep Content Segmentation")
                segments_created = await self._pass_2_content_segmentation(
                    db, document_id, document.raw_text, composition_analysis
                )
                
                # Pass 3: Profile-Based Structured Extraction
                self.logger.info(f"Document {document_id}: Starting Pass 3 - Profile-Based Structured Extraction")
                await self._pass_3_structured_extraction(db, document_id)
                
                # Learning Mode: Feed to Business Ontology Engine
                if learning_mode:
                    self.logger.info(f"Document {document_id}: Learning mode enabled - feeding to BOE")
                    await self._feed_to_business_ontology(db, document_id)
                
                self.logger.info(f"Document {document_id}: Multi-pass analysis completed successfully")
                return True
                
            except Exception as e:
                self.logger.error(f"Error during multi-pass analysis for document {document_id}: {e}")
                return False
        finally:
            # Always remove document from running set
            self._running_documents.discard(document_id)
            self.logger.debug(f"Released analysis lock for document {document_id}")
    
    async def _pass_1_composition_classification(self, raw_text: str) -> Dict:
        """
        Pass 1: Analyzes document composition and classifies content types.
        Returns a JSON object identifying content types and their percentage distribution.
        """
        try:
            # Use the prompt manager instead of hardcoded prompts
            prompt = prompt_manager.get_prompt(PromptType.DOCUMENT_COMPOSITION)
            
            # Prepare the full prompt with the document text
            full_prompt = f"{prompt}\n\nDOCUMENT TEXT TO ANALYZE:\n{raw_text}"
            
            self.logger.debug("Sending composition analysis request to Gemini")
            
            # Call Gemini API
            response = await gemini_service.generate_content(full_prompt)
            response_text = response.text
            
            # Debug: Log the actual response
            self.logger.info(f"Gemini response length: {len(response_text) if response_text else 0}")
            self.logger.debug(f"Gemini response content: {response_text[:500] if response_text else 'EMPTY'}")
            
            # Clean the response - remove markdown code block formatting
            cleaned_response = response_text.strip()
            if cleaned_response.startswith('```json'):
                # Remove ```json from start and ``` from end
                cleaned_response = cleaned_response[7:]  # Remove ```json
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]  # Remove ```
                cleaned_response = cleaned_response.strip()
            elif cleaned_response.startswith('```'):
                # Remove ``` from start and end
                cleaned_response = cleaned_response[3:]
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]
                cleaned_response = cleaned_response.strip()
            
            # Parse the JSON response
            try:
                composition_data = json.loads(cleaned_response)
                self.logger.info("Composition analysis completed successfully")
                return composition_data
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse Gemini response as JSON: {e}")
                self.logger.error(f"Raw response: {response_text}")
                self.logger.error(f"Cleaned response: {cleaned_response}")
                raise AIAnalysisException(
                    message="Failed to parse composition analysis response",
                    model="gemini",
                    details={"response": response_text, "cleaned_response": cleaned_response, "error": str(e)}
                )
                
        except Exception as e:
            self.logger.error(f"Error in Pass 1 composition classification: {e}")
            raise AIAnalysisException(
                message="Composition classification failed",
                model="gemini",
                details={"error": str(e)}
            )
    
    async def _pass_2_content_segmentation(
        self, db: Session, document_id: int, raw_text: str, composition_analysis: Dict
    ) -> bool:
        """
        Pass 2: Creates document segments based on composition analysis.
        """
        try:
            # Clean up existing segments and their analysis results for this document
            self.logger.info(f"Cleaning up existing segments for document {document_id}")
            
            # Get existing segments
            existing_segments = crud.document_segment.get_multi_by_document(db=db, document_id=document_id)
            
            # Delete analysis results for existing segments
            for segment in existing_segments:
                crud.analysis_result.delete_by_segment(db=db, segment_id=segment.id)
            
            # Delete existing segments
            crud.document_segment.delete_by_document(db=db, document_id=document_id)
            
            self.logger.info(f"Cleaned up {len(existing_segments)} existing segments and their analysis results")
            # Use the prompt manager for segmentation
            prompt = prompt_manager.get_prompt(PromptType.CONTENT_SEGMENTATION)
            
            # Prepare the full prompt with context
            full_prompt = f"""
            {prompt}
            
            COMPOSITION ANALYSIS:
            {json.dumps(composition_analysis, indent=2)}
            
            DOCUMENT TEXT:
            {raw_text}
            """
            
            self.logger.debug("Sending content segmentation request to Gemini")
            
            # Call Gemini API
            response = await gemini_service.generate_content(full_prompt)
            response_text = response.text
            
            # Clean the response - remove markdown code block formatting
            cleaned_response = response_text.strip()
            if cleaned_response.startswith('```json'):
                # Remove ```json from start and ``` from end
                cleaned_response = cleaned_response[7:]  # Remove ```json
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]  # Remove ```
                cleaned_response = cleaned_response.strip()
            elif cleaned_response.startswith('```'):
                # Remove ``` from start and end
                cleaned_response = cleaned_response[3:]
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]
                cleaned_response = cleaned_response.strip()
            
            # Parse the JSON response
            try:
                segmentation_data = json.loads(cleaned_response)
                segments = segmentation_data.get("segments", [])
                
                # Filter segments to only include those with > 0% composition
                composition = composition_analysis.get("composition", {})
                valid_segments = []
                
                for segment_info in segments:
                    segment_type = segment_info["segment_type"]
                    composition_percentage = composition.get(segment_type, 0)
                    
                    # Only create segments for document types that have > 0% composition
                    if composition_percentage > 0:
                        valid_segments.append(segment_info)
                        self.logger.debug(f"Creating segment for {segment_type} ({composition_percentage}% composition)")
                    else:
                        self.logger.debug(f"Skipping segment for {segment_type} (0% composition)")
                
                # Create document segments in the database
                for segment_info in valid_segments:
                    segment_data = {
                        "segment_type": segment_info["segment_type"],
                        "start_char_index": segment_info["start_char_index"],
                        "end_char_index": segment_info["end_char_index"],
                        "document_id": document_id
                    }
                    
                    # Create the segment
                    crud.document_segment.create(db=db, obj_in=schemas.DocumentSegmentCreate(**segment_data))
                
                self.logger.info(f"Created {len(valid_segments)} document segments (filtered from {len(segments)} total)")
                return True
                
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse segmentation response as JSON: {e}")
                self.logger.error(f"Raw response: {response_text}")
                self.logger.error(f"Cleaned response: {cleaned_response}")
                raise AIAnalysisException(
                    message="Failed to parse segmentation response",
                    model="gemini",
                    details={"response": response_text, "cleaned_response": cleaned_response, "error": str(e)}
                )
                
        except Exception as e:
            self.logger.error(f"Error in Pass 2 content segmentation: {e}")
            raise DocumentProcessingException(
                message="Content segmentation failed",
                document_id=document_id,
                details={"error": str(e)}
            )
    
    async def _pass_3_structured_extraction(self, db: Session, document_id: int) -> bool:
        """
        Pass 3: Performs structured extraction on each document segment.
        """
        try:
            # Get all segments for this document
            segments = crud.document_segment.get_by_document(db=db, document_id=document_id)
            
            if not segments:
                self.logger.warning(f"No segments found for document {document_id}")
                return False
            
            # Use the prompt manager for structured extraction
            base_prompt = prompt_manager.get_prompt(PromptType.STRUCTURED_EXTRACTION)
            
            for segment in segments:
                try:
                    # Get the segment text from the parent document
                    document = crud.document.get(db=db, id=document_id)
                    segment_text = document.raw_text[segment.start_char_index:segment.end_char_index]
                    
                    # Prepare the full prompt for this segment
                    full_prompt = f"""
                    {base_prompt}
                    
                    SEGMENT TYPE: {segment.segment_type}
                    SEGMENT TEXT:
                    {segment_text}
                    """
                    
                    self.logger.debug(f"Analyzing segment {segment.id} of type {segment.segment_type}")
                    
                    # Call Gemini API
                    response = await gemini_service.generate_content(full_prompt)
                    response_text = response.text
                    
                    # Parse the JSON response with repair logic
                    try:
                        # First attempt with basic cleaning
                        cleaned_response = response_text.strip()
                        if cleaned_response.startswith('```json'):
                            cleaned_response = cleaned_response[7:]
                        elif cleaned_response.startswith('```'):
                            cleaned_response = cleaned_response[3:]
                        if cleaned_response.endswith('```'):
                            cleaned_response = cleaned_response[:-3]
                        cleaned_response = cleaned_response.strip()
                        
                        structured_data = json.loads(cleaned_response)
                        
                    except json.JSONDecodeError as e:
                        # Attempt repair on first failure
                        self.logger.warning(f"Initial JSON parse failed for segment {segment.id}, attempting repair")
                        try:
                            repaired_response = repair_json_response(response_text)
                            structured_data = json.loads(repaired_response)
                            self.logger.info(f"Successfully repaired JSON for segment {segment.id}")
                        except json.JSONDecodeError as repair_error:
                            self.logger.error(f"JSON repair also failed for segment {segment.id}: {repair_error}")
                            self.logger.error(f"Raw response: {response_text}")
                            self.logger.error(f"Cleaned response: {cleaned_response}")
                            self.logger.error(f"Repaired response: {repaired_response}")
                            # Skip this segment - don't create empty result
                            continue
                    
                    # Only create analysis result if we have valid structured data
                    if structured_data and (isinstance(structured_data, dict) and structured_data or isinstance(structured_data, list) and structured_data):
                        analysis_result_data = {
                            "segment_id": segment.id,
                            "document_id": document_id,
                            "structured_data": structured_data
                        }
                        
                        crud.analysis_result.create_for_document(db=db, obj_in=schemas.AnalysisResultCreate(**analysis_result_data))
                        self.logger.info(f"Created analysis result for segment {segment.id}")
                    else:
                        self.logger.warning(f"Skipping empty structured data for segment {segment.id}")
                        continue
                        
                except Exception as e:
                    self.logger.error(f"Error processing segment {segment.id}: {e}")
                    # Continue with other segments
                    continue
            
            self.logger.info(f"Completed structured extraction for {len(segments)} segments")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in Pass 3 structured extraction: {e}")
            raise DocumentProcessingException(
                message="Structured extraction failed",
                document_id=document_id,
                details={"error": str(e)}
            )
    
    async def _feed_to_business_ontology(self, db: Session, document_id: int) -> bool:
        """
        Feeds extracted entities to the Business Ontology Engine (placeholder for future implementation).
        """
        try:
            self.logger.info(f"Feeding document {document_id} to Business Ontology Engine")
            
            # TODO: Implement Business Ontology Engine integration
            # This is a placeholder for future implementation
            
            self.logger.info(f"Successfully fed document {document_id} to Business Ontology Engine")
            return True
            
        except Exception as e:
            self.logger.error(f"Error feeding to Business Ontology Engine: {e}")
            return False

# Create a global instance
dae = DocumentAnalysisEngine()

# Legacy function for backward compatibility
async def run_initial_analysis(db: Session, document_id: int):
    """
    Legacy function that now delegates to the new DAE.
    """
    return await dae.analyze_document(db, document_id)

