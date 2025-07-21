# This is the updated content for your file at:
# backend/app/services/ai/gemini.py

import google.generativeai as genai
from app.core.config import settings
import logging
import json
import httpx

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
        "structured_analysis": {{
            "primary_language": "The main programming language.",
            "languages": {{
                "primary": "Main language with percentage if available.",
                "secondary": ["List", "of", "other", "languages", "used."]
            }},
            "architecture": {{
                "type": "e.g., 'Monolithic Web App', 'Microservices Backend'",
                "components": ["List", "of", "likely", "system", "components."],
                "tech_stack": ["List", "of", "probable", "technologies."]
            }},
            "project_insights": {{
                "complexity": "Low/Medium/High",
                "target_users": "A description of who would use this project.",
                "development_stage": "Early/Active/Mature",
                "maintenance_notes": "Observations about ongoing maintenance."
            }},
            "technology_assessment": {{
                "language_choice_rationale": "A brief explanation of why the language choice makes sense.",
                "notable_dependencies": ["List", "of", "key", "dependencies", "if available."],
                "scalability_considerations": "Brief thoughts on the project's scalability."
            }}
        }}
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
