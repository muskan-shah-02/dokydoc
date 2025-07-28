# This is the final, complete, and correct content for your file at:
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
            "functions": [], "classes": [], "imports": {{}}, "code_quality": {{}}
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


# --- FUNCTION 2: REPOSITORY ANALYSIS (RESTORED) ---
async def call_gemini_for_repository_analysis(repo_metadata: dict) -> dict:
    """
    Analyzes a GitHub repository based on its metadata using a detailed, expert prompt.
    """
    logger.info("Making a real call to the Gemini API for repository analysis...")
    prompt = f"""
    You are a technical lead reviewing a GitHub repository. Analyze the repository metadata and provide insights about the project.

    ANALYSIS REQUIREMENTS:
    - Summary: Write 2-3 sentences about the project's purpose, its target users, and its main value proposition.
    - Architecture: Infer the likely architecture patterns, tech stack decisions, and project structure from the metadata.
    - Technology Assessment: Evaluate the choice of languages, key dependencies, and the overall technical approach.
    - Project Insights: Comment on the development activity, complexity, and any maintenance considerations.

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
        return {"summary": "AI repository analysis failed.", "structured_analysis": {"error": str(e)}}


# --- FUNCTION 3: VALIDATION & MISMATCH (INTACT AND CORRECTED) ---
class ValidationType(Enum):
    API_ENDPOINT = "API_Endpoint_Missing"
    PARAMETER_MISMATCH = "Parameter_Mismatch"
    BUSINESS_LOGIC = "Business_Logic_Missing"
    DATA_FLOW = "Data_Flow_Inconsistency"
    SECURITY_REQUIREMENT = "Security_Requirement_Missing"
    PERFORMANCE_CONSTRAINT = "Performance_Constraint_Missing"
    CONSISTENCY_CHECK = "Consistency_Check"

@dataclass
class ValidationContext:
    """Context for validation to make prompts more focused"""
    focus_area: ValidationType
    document_content: str
    code_content: str
    document_type: str
    severity_threshold: str = "Medium"
    max_mismatches: int = 8

def _build_validation_instructions(focus_area: ValidationType) -> str:
    if focus_area == ValidationType.API_ENDPOINT:
        return "API ENDPOINTS: Compare documented API endpoints/functions with implemented methods."
    return "General: Look for any clear contradictions between the document and the code."

def _parse_and_validate_response(response_text: str) -> List[dict]:
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

async def call_gemini_for_validation(context: ValidationContext) -> List[dict]:
    logger.info(f"Starting Gemini validation for: {context.focus_area.value}")
    validation_instructions = _build_validation_instructions(context.focus_area)
    document_analysis = {"content": context.document_content}
    code_analysis = {"content": context.code_content}
    prompt = f"""
    You are an expert software architect acting as a validation engine.

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
    If no mismatches are found, return an empty array: [].

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