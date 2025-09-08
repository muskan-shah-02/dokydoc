# backend/app/services/ai/gemini.py

import json
import asyncio
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, field
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import LoggerMixin
from app.services.ai.prompt_manager import prompt_manager, PromptType

class GeminiService(LoggerMixin):
    """
    Service class for interacting with Google's Gemini AI API.
    Provides both text and vision capabilities with retry logic and error handling.
    """
    
    def __init__(self):
        super().__init__()
        
        if not settings.GEMINI_API_KEY or "YOUR_GEMINI_API_KEY_HERE" in settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured correctly")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        self.vision_model = genai.GenerativeModel(settings.GEMINI_VISION_MODEL)
        self.logger.info("GeminiService initialized successfully")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_content(self, prompt: str, **kwargs) -> genai.types.GenerateContentResponse:
        """
        Generate content with retry logic and error handling.
        """
        try:
            self.logger.debug("Sending request to Gemini API")
            response = await self.model.generate_content_async(prompt, **kwargs)
            self.logger.debug("Gemini API response received successfully")
            return response
        except Exception as e:
            self.logger.error(f"Error calling Gemini API: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_content_with_vision(self, prompt: str, image, **kwargs) -> genai.types.GenerateContentResponse:
        """
        Generate content with vision capabilities and retry logic.
        """
        try:
            self.logger.debug("Sending vision request to Gemini API")
            response = await self.vision_model.generate_content_async([prompt, image], **kwargs)
            self.logger.debug("Gemini Vision API response received successfully")
            return response
        except Exception as e:
            self.logger.error(f"Error calling Gemini Vision API: {e}")
            raise

    async def call_gemini_for_code_analysis(self, code_content: str) -> dict:
        """
        Analyzes ANY file's content using a universal, adaptive prompt.
        Works with any programming language, framework, or architectural pattern.
        """
        try:
            self.logger.info("Making a real call to the Gemini API for universal code analysis...")
            
            # Use the prompt manager for code analysis
            prompt = prompt_manager.get_prompt(PromptType.CODE_ANALYSIS)
            
            # Prepare the full prompt with the code content
            full_prompt = f"{prompt}\n\nCODE TO ANALYZE:\n{code_content}"
            
            # Call Gemini API
            response = await self.generate_content(full_prompt)
            response_text = response.text
            
            # Parse the JSON response
            try:
                analysis_data = json.loads(response_text)
                self.logger.info("Code analysis completed successfully")
                return analysis_data
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse Gemini response as JSON: {e}")
                # Return a fallback structure
                return {
                    "summary": "Code analysis completed but response parsing failed",
                    "structured_analysis": {
                        "language_info": {"primary_language": "Unknown", "framework": "Unknown", "file_type": "Unknown"},
                        "components": [],
                        "dependencies": [],
                        "exports": [],
                        "patterns_and_architecture": {"design_patterns": [], "architectural_style": "Unknown", "key_concepts": []},
                        "quality_assessment": "Analysis failed due to response parsing error"
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Error in code analysis: {e}")
            raise

# Legacy compatibility - create a global instance
try:
    gemini_service = GeminiService()
    model = gemini_service.model  # For backward compatibility
except Exception as e:
    print(f"Warning: Could not initialize GeminiService: {e}")
    model = None
    gemini_service = None

# --- FUNCTION 1: CODE ANALYSIS (INTACT) ---
async def call_gemini_for_code_analysis(code_content: str) -> dict:
    """
    Legacy function for backward compatibility.
    """
    if gemini_service:
        return await gemini_service.call_gemini_for_code_analysis(code_content)
    else:
        raise RuntimeError("GeminiService not available")

# --- FUNCTION 3: SEMANTIC VALIDATION ENGINE (FULLY UPGRADED) ---

class ValidationType(Enum):
    """
    Defines the specific types of validation checks the engine can perform.
    This allows for focused, role-based analysis.
    """
    API_ENDPOINT_MISSING = "API Endpoint Missing"
    PARAMETER_MISMATCH = "Parameter Mismatch"
    BUSINESS_LOGIC_MISSING = "Business Logic Missing"
    DATA_FLOW_INCONSISTENCY = "Data Flow Inconsistency"
    SECURITY_REQUIREMENT_UNMET = "Security Requirement Unmet"
    PERFORMANCE_CONSTRAINT_UNMET = "Performance Constraint Unmet"
    GENERAL_CONSISTENCY = "General Consistency Check"

@dataclass
class ValidationContext:
    """
    **This is the upgraded context.** It holds structured analysis data,
    NOT raw text, which is the core of our intelligent strategy.
    """
    focus_area: ValidationType
    document_analysis: Optional[List[Dict]] = field(default_factory=list)
    code_analysis: Optional[Dict] = field(default_factory=dict)

def _build_validation_instructions(focus_area: ValidationType) -> str:
    """
    This helper generates detailed, specific instructions for the AI.
    This is the key to enabling different validation profiles for different user roles.
    """
    if focus_area == ValidationType.API_ENDPOINT_MISSING:
        return "API ENDPOINTS: Compare the functional requirements for API endpoints described in the document analysis against the implemented functions/classes in the code analysis. Identify any required endpoints that are completely missing from the code."
    if focus_area == ValidationType.BUSINESS_LOGIC_MISSING:
        return "BUSINESS LOGIC: Compare the high-level business requirements from the document analysis against the code's overall summary and component purposes. Identify any core business concepts or rules that are not mentioned or implemented in the code."
    return "GENERAL CONSISTENCY: Perform a general consistency check. Look for any other clear contradictions between the document's stated goals and the code's implementation details as presented in their respective analyses."

async def call_gemini_for_validation(context: ValidationContext) -> List[dict]:
    """
    **This is the upgraded validation function.**
    It sends structured data to the AI with a focused, role-based prompt.
    """
    if not model:
        raise RuntimeError("Gemini model not available")
        
    logger.info(f"Starting focused Gemini validation for: {context.focus_area.value}")
    
    validation_instructions = _build_validation_instructions(context.focus_area)

    prompt = f"""
    You are an expert software architect acting as a semantic validation engine.
    Your task is to perform a highly focused validation check by comparing the structured analysis of a technical document against the structured analysis of a code file.

    CRITICAL INSTRUCTIONS:
    1.  **FOCUS**: Adhere strictly to the 'VALIDATION AREA' defined below.
    2.  **PRECISION**: Only flag genuine, high-impact mismatches. Be precise and actionable.
    3.  **SEMANTICS**: Understand intent. 'getUser' is equivalent to 'fetch_user_data'.
    4.  **EVIDENCE**: The 'expected' field MUST come from the DOCUMENT ANALYSIS. The 'actual' field MUST come from the CODE ANALYSIS.

    VALIDATION AREA:
    {validation_instructions}

    STRICT RESPONSE FORMAT:
    Return ONLY a valid JSON array of mismatch objects. Each object must follow this exact schema:
    {{
        "mismatch_type": "{context.focus_area.value}",
        "description": "A clear, one-sentence summary of the core mismatch.",
        "severity": "High | Medium | Low",
        "confidence": "High | Medium | Low",
        "details": {{
            "expected": "What the document's structured analysis specifies.",
            "actual": "What the code's structured analysis shows (or 'Missing').",
            "evidence_document": "A direct quote or summary from the document analysis.",
            "evidence_code": "A direct quote or summary from the code analysis.",
            "suggested_action": "A brief, actionable recommendation for a developer to fix the issue."
        }}
    }}
    If no mismatches are found for this specific validation area, you MUST return an empty array: [].

    DOCUMENT ANALYSIS (The "Source of Truth"):
    ```json
    {json.dumps(context.document_analysis, indent=2)}
    ```

    CODE ANALYSIS (The "Implementation"):
    ```json
    {json.dumps(context.code_analysis, indent=2)}
    ```
    """
    try:
        response = await model.generate_content_async(prompt)
        cleaned_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        result = json.loads(cleaned_text)
        logger.info(f"Validation for {context.focus_area.value} complete: {len(result)} mismatches found.")
        return result if isinstance(result, list) else []
    except Exception as e:
        logger.error(f"Gemini validation for {context.focus_area.value} failed: {e}", exc_info=True)
        return []
    