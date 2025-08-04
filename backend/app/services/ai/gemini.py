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
    Analyzes ANY file's content using a universal, adaptive prompt.
    Works with any programming language, framework, or code pattern.
    """
    logger.info("Making a real call to the Gemini API for universal code analysis...")
    
    prompt = f"""
    You are an expert software architect analyzing source code. Your task is to understand and document ANY type of code file, regardless of language, framework, or architectural pattern.

    UNIVERSAL ANALYSIS APPROACH:
    1. **Identify the Language/Framework**: Determine what programming language and frameworks are being used
    2. **Understand the Purpose**: What does this file accomplish in the broader system?
    3. **Extract All Meaningful Elements**: Find all significant code constructs, regardless of type
    4. **Assess Quality & Patterns**: Evaluate code quality, patterns, and architectural decisions

    ADAPTIVE COMPONENT DETECTION:
    Scan for ANY of these code elements (language-agnostic):
    - Functions/Methods (def, function, async def, const myFunc, public void, etc.)
    - Classes/Objects (class, interface, struct, type, enum, etc.)
    - Components (React components, Vue components, Angular components)
    - Modules/Exports (export, module.exports, import/export statements)
    - Constants/Variables (const, let, var, final, static, etc.)
    - APIs/Endpoints (routes, controllers, handlers)
    - Database Models/Schemas
    - Configuration Objects
    - Custom Types/Interfaces
    - Hooks/Middleware
    - Services/Utilities
    
    LANGUAGE-SPECIFIC ADAPTATIONS:
    - **Python**: Functions, classes, decorators, async functions, dataclasses, enums
    - **JavaScript/TypeScript**: Functions, classes, React components, hooks, interfaces, types
    - **Java/C#**: Classes, methods, interfaces, enums, annotations
    - **Go**: Functions, structs, interfaces, methods
    - **Rust**: Functions, structs, enums, traits, impl blocks
    - **PHP**: Classes, functions, traits, interfaces
    - **Ruby**: Classes, modules, methods, constants
    - **And ANY other language patterns you encounter**

    STRICT RESPONSE FORMAT:
    Return ONLY valid JSON matching this schema:
    {{
        "summary": "2-3 sentences describing the file's purpose, language, and role in the system",
        "structured_analysis": {{
            "language_info": {{
                "primary_language": "Detected language (e.g., Python, JavaScript, TypeScript, Java)",
                "framework": "Main framework if detected (e.g., React, FastAPI, Express, Spring)",
                "file_type": "Type of file (e.g., Component, Service, Model, Configuration, Utility)"
            }},
            "components": [
                {{
                    "name": "Exact name found in code",
                    "type": "Function|AsyncFunction|Class|Interface|Component|Constant|Variable|Hook|Service|Route|Model|Type|Enum|Method|Module",
                    "purpose": "What this component does - one clear sentence",
                    "details": "Key parameters, return types, props, fields, or other relevant details",
                    "line_info": "Approximate location or signature if complex"
                }}
            ],
            "dependencies": [
                "List of imports, requires, or external dependencies with actual names from the code"
            ],
            "exports": [
                "What this file exports or makes available to other files"
            ],
            "patterns_and_architecture": {{
                "design_patterns": ["Any design patterns observed (e.g., Factory, Observer, MVC)"],
                "architectural_style": "Overall style (e.g., Functional, OOP, Component-based, Microservice)",
                "key_concepts": ["Main programming concepts used (e.g., async/await, HOCs, dependency injection)"]
            }},
            "quality_assessment": "Brief assessment of code quality, structure, error handling, and best practices observed"
        }}
    }}

    CRITICAL INSTRUCTIONS:
    - ALWAYS populate the components array with actual elements found in the code
    - If you find ANYTHING that looks like a meaningful code construct, include it
    - Use the exact names from the code, not generic placeholders
    - Be language-agnostic - adapt to whatever language/framework you encounter
    - If it's a configuration file, document the key configurations
    - If it's a test file, document the test cases and what they test
    - If it's a data file, document the data structure and purpose
    - Never return empty components array unless the file truly has no meaningful code elements

    EXAMPLES OF WHAT TO CAPTURE:
    - Python: `async def get_user(id: int)` → {{"name": "get_user", "type": "AsyncFunction", "details": "Parameters: id (int), fetches user data"}}
    - React: `const UserCard = ({{ user }}) =>` → {{"name": "UserCard", "type": "Component", "details": "Props: user object, renders user information"}}
    - Java: `public class UserService` → {{"name": "UserService", "type": "Class", "details": "Service class for user operations"}}
    - Config: `API_BASE_URL = "https://api.example.com"` → {{"name": "API_BASE_URL", "type": "Constant", "details": "Base URL for API requests"}}

    CODE TO ANALYZE:
    ```
    {code_content}
    ```
    """
    
    try:
        response = await model.generate_content_async(prompt)
        cleaned_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        result = json.loads(cleaned_text)
        
        # Validate that we got components
        components = result.get("structured_analysis", {}).get("components", [])
        if not components:
            logger.warning("AI returned empty components array - this might indicate an issue with analysis")
        else:
            logger.info(f"Successfully analyzed code: found {len(components)} components")
            
        return result
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}")
        logger.error(f"Raw response: {response.text if 'response' in locals() else 'No response'}")
        return {
            "summary": "AI analysis failed due to JSON parsing error.",
            "structured_analysis": {"error": f"JSON Parse Error: {str(e)}"}
        }
    except Exception as e:
        logger.error(f"Error calling or parsing Gemini API for code analysis: {e}", exc_info=True)
        return {
            "summary": "AI analysis failed due to unexpected error.",
            "structured_analysis": {"error": str(e)}
        }

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
    