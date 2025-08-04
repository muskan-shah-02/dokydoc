# backend/app/services/ai/gemini.py

import json
import logging
from typing import List, Dict, Optional
from enum import Enum
from dataclasses import dataclass, field
import google.generativeai as genai
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure the Gemini client
genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')


# --- FUNCTION 1: CODE ANALYSIS (INTACT) ---
async def call_gemini_for_code_analysis(code_content: str) -> dict:
    """
    Analyzes a single file's content using a detailed, expert prompt.
    """
    logger.info("Making a real call to the Gemini API for structured code analysis...")
    
    prompt = f"""
    You are a senior software engineer conducting a professional code review.
    Your task is to analyze the provided source code and return a structured JSON object.

    ANALYSIS REQUIREMENTS:
    1.  **Summary**: Write a concise, 2-3 sentence paragraph explaining the file's primary purpose and its role within a larger application.
    2.  **Functions/Classes**: For each function or class, identify its name, its specific purpose, and list its key parameters or methods.
    3.  **Dependencies**: List the main libraries or modules imported at the top of the file.
    4.  **Code Quality**: Provide a brief assessment of the code's quality, noting any potential issues like missing error handling, performance bottlenecks, or good design patterns observed.

    STRICT RESPONSE FORMAT:
    You MUST return ONLY a valid JSON object. Do not include any explanatory text before or after the JSON.
    The JSON object must match this exact schema:
    {{
        "summary": "A 2-3 sentence description of the file's purpose and role.",
        "structured_analysis": {{
            "components": [
                {{
                    "name": "Function or Class Name",
                    "type": "Function | Class",
                    "purpose": "A one-sentence description of what it does.",
                    "details": "e.g., Parameters: [param1, param2] or Key Methods: [method1, method2]"
                }}
            ],
            "dependencies": ["List of imported libraries"],
            "quality_assessment": "A brief assessment of the code's quality."
        }}
    }}

    CODE TO ANALYZE:
    ```python
    {code_content}
    ```
    """
    
    try:
        response = await model.generate_content_async(prompt)
        cleaned_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        result = json.loads(cleaned_text)
        logger.info("Successfully received and parsed structured code analysis from Gemini API.")
        return result
    except Exception as e:
        logger.error(f"Error calling or parsing Gemini API for code analysis: {e}", exc_info=True)
        return {{
            "summary": "AI analysis failed.",
            "structured_analysis": {{"error": str(e)}}
        }}

# --- FUNCTION 2: REPOSITORY ANALYSIS (INTACT) ---
async def call_gemini_for_repository_analysis(repo_metadata: dict) -> dict:
    """
    Analyzes a GitHub repository based on its metadata using a detailed, expert prompt.
    """
    logger.info("Making a real call to the Gemini API for repository analysis...")
    prompt = f"""
    You are a technical lead reviewing a GitHub repository. Analyze the repository metadata and provide insights about the project.

    RESPONSE FORMAT:
    Return ONLY a valid JSON object matching this exact schema:
    {{
        "summary": "A 2-3 sentence description of the project's purpose and value.",
        "structured_analysis": {{}}
    }}

    REPOSITORY METADATA:
    {json.dumps(repo_metadata, indent=2)}
    """
    try:
        response = await model.generate_content_async(prompt)
        cleaned_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        result = json.loads(cleaned_text)
        logger.info("Successfully received and parsed repository analysis from Gemini API.")
        return result
    except Exception as e:
        logger.error(f"Error calling or parsing Gemini API response for repo: {e}", exc_info=True)
        return {{"summary": "AI repository analysis failed.", "structured_analysis": {{"error": str(e)}}}}


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