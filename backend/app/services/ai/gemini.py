# This is the updated content for your file at:
# backend/app/services/ai/gemini.py

import json
import logging
from typing import List, Dict, Optional
from enum import Enum
from dataclasses import dataclass
import google.generativeai as genai
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure the Gemini client
genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

async def call_gemini_for_code_analysis(code_content: str) -> dict:
    """
    Analyzes a single file's content using a detailed, expert prompt.
    """
    logger.info("Making a real call to the Gemini API for single file analysis...")
    prompt = f"""
    You are a senior software engineer reviewing Python code. Analyze the following code thoroughly and professionally.

    ANALYSIS REQUIREMENTS:
    - Summary: Write 2-3 sentences explaining the file's purpose, main responsibility, and how it fits into a larger system.
    - Functions: For each function, provide its name, a concise purpose, a list of parameters, and its return type.
    - Classes: For each class, provide its name, purpose, key methods, and any inheritance.
    - Imports: Categorize all imports (standard library, third-party, local) and briefly explain their usage.
    - Code Quality: Note any observed design patterns, potential issues (e.g., error handling, performance), or key architectural decisions.

    RESPONSE FORMAT:
    Return ONLY a valid JSON object matching this exact schema:
    {{
        "summary": "A 2-3 sentence description of the file's purpose and role.",
        "structured_analysis": {{
            "functions": [
                {{
                    "name": "function_name",
                    "purpose": "A brief description of what the function does.",
                    "parameters": ["param1", "param2"],
                    "return_type": "A description of the return value."
                }}
            ],
            "classes": [
                {{
                    "name": "ClassName",
                    "purpose": "A brief description of the class's responsibility.",
                    "methods": ["method1", "method2"],
                    "inheritance": "Name of the parent class, if any."
                }}
            ],
            "imports": {{
                "standard_library": ["os", "json"],
                "third_party": ["fastapi", "sqlalchemy"],
                "local": ["app.models", "app.schemas"]
            }},
            "code_quality": {{
                "patterns": ["e.g., 'Repository Pattern', 'Dependency Injection'"],
                "potential_issues": ["e.g., 'Lacks comprehensive error handling in XYZ.'"],
                "architecture_notes": ["e.g., 'Follows a clean three-tier architecture.'"]
            }}
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
        logger.info("Successfully received and parsed analysis from Gemini API.")
        return result
    except Exception as e:
        logger.error(f"Error calling or parsing Gemini API response: {e}", exc_info=True)
        return {"summary": "AI analysis failed.", "structured_analysis": {"error": str(e)}}

# --- NEW: Validation Framework ---

class ValidationType(Enum):
    API_ENDPOINT = "API_Endpoint_Missing"
    PARAMETER_MISMATCH = "Parameter_Mismatch"
    BUSINESS_LOGIC = "Business_Logic_Missing"
    DATA_FLOW = "Data_Flow_Inconsistency"
    SECURITY_REQUIREMENT = "Security_Requirement_Missing"
    PERFORMANCE_CONSTRAINT = "Performance_Constraint_Missing"

@dataclass
class ValidationContext:
    """Context for validation to make prompts more focused"""
    focus_area: ValidationType
    severity_threshold: str = "Medium"
    max_mismatches: int = 8

def _build_validation_instructions(focus_area: ValidationType) -> str:
    """Builds a specific, focused validation instruction for the AI."""
    if focus_area == ValidationType.API_ENDPOINT:
        return "API ENDPOINTS: Compare documented API endpoints/functions with implemented methods. Check for missing endpoints, incorrect HTTP methods, and naming discrepancies."
    if focus_area == ValidationType.PARAMETER_MISMATCH:
        return "PARAMETERS: Validate function/endpoint parameters. Check for required vs. optional mismatches, data type inconsistencies, and missing parameters."
    # Add other instruction mappings here...
    return "General: Look for any clear contradictions between the document and the code."

def _parse_and_validate_response(response_text: str) -> List[dict]:
    """Parses and validates the AI's JSON response."""
    try:
        cleaned_text = response_text.strip().replace('```json', '').replace('```', '').strip()
        result = json.loads(cleaned_text)
        if not isinstance(result, list):
            logger.warning("AI returned non-list response, wrapping in list.")
            return [result] if result else []
        return result
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        return []

async def call_gemini_for_validation(
    document_analysis: dict, 
    code_analysis: dict,
    context: ValidationContext
) -> List[dict]:
    """
    Performs a single, focused validation check against the Gemini API.
    """
    logger.info(f"Starting Gemini validation for: {context.focus_area.value}")
    validation_instructions = _build_validation_instructions(context.focus_area)

    prompt = f"""
    You are an expert software architect acting as a validation engine. Your task is to perform a focused semantic validation check.

    CRITICAL INSTRUCTIONS:
    1. Focus ONLY on the validation area specified.
    2. Be precise and actionable. Only flag genuine, high-impact mismatches.
    3. Consider semantic equivalence (e.g., 'getUser' is equivalent to 'fetchUser').

    VALIDATION AREA:
    {validation_instructions}

    RESPONSE FORMAT:
    Return ONLY a valid JSON array of mismatch objects. Each object must follow this schema:
    {{
        "mismatch_type": "{context.focus_area.value}",
        "description": "Clear, one-sentence description of the mismatch.",
        "severity": "High/Medium/Low",
        "confidence": "High/Medium/Low",
        "details": {{
            "expected": "What the document specifies.",
            "actual": "What exists in the code (or 'Missing').",
            "evidence_document": "A direct quote from the document.",
            "evidence_code": "A direct quote or reference from the code.",
            "suggested_action": "A brief, actionable recommendation."
        }}
    }}
    If no mismatches are found for this specific validation area, return an empty array: [].

    DOCUMENT ANALYSIS:
    ```json
    {json.dumps(document_analysis, indent=2)}
    ```

    CODE ANALYSIS:
    ```json
    {json.dumps(code_analysis, indent=2)}
    ```
    """
    try:
        response = await model.generate_content_async(prompt)
        result = _parse_and_validate_response(response.text)
        logger.info(f"Validation for {context.focus_area.value} complete: {len(result)} mismatches found.")
        return result
    except Exception as e:
        logger.error(f"Gemini validation for {context.focus_area.value} failed: {e}", exc_info=True)
        return []

