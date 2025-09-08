from typing import Dict, Any, Optional
from enum import Enum
import json
from pathlib import Path

from app.core.logging import LoggerMixin

class PromptType(Enum):
    """Enumeration of prompt types."""
    DOCUMENT_COMPOSITION = "document_composition"
    CONTENT_SEGMENTATION = "content_segmentation"
    STRUCTURED_EXTRACTION = "structured_extraction"
    CODE_ANALYSIS = "code_analysis"
    IMAGE_ANALYSIS = "image_analysis"
    VALIDATION = "validation"
    BUSINESS_ONTOLOGY = "business_ontology"

class PromptManager(LoggerMixin):
    """
    Centralized prompt management system for all AI interactions.
    Manages prompts, their versions, and provides dynamic prompt generation.
    """
    
    def __init__(self):
        self.prompts = self._load_default_prompts()
        self.logger.info("PromptManager initialized with default prompts")
    
    def _load_default_prompts(self) -> Dict[str, Dict[str, Any]]:
        """Load default prompts for the system."""
        return {
            PromptType.DOCUMENT_COMPOSITION.value: {
                "version": "1.0",
                "description": "Analyzes document composition and classifies content types",
                "prompt": """
                You are an expert document analyst. Analyze the following document text and classify its content composition.
                
                TASK:
                Identify the types of content present in this document and estimate their percentage distribution.
                
                CONTENT TYPES TO LOOK FOR:
                - BRD (Business Requirements Document)
                - SRS (Software Requirements Specification)
                - API_DOCS (API Documentation)
                - USER_STORIES (User Stories)
                - TECHNICAL_SPECS (Technical Specifications)
                - PROCESS_FLOWS (Process Flows)
                - DATA_MODELS (Data Models)
                - SECURITY_REQUIREMENTS (Security Requirements)
                - PERFORMANCE_REQUIREMENTS (Performance Requirements)
                - UI_UX_SPECS (UI/UX Specifications)
                - UNKNOWN (Content that doesn't fit other categories)
                
                ANALYSIS APPROACH:
                1. Read through the entire document text
                2. Identify distinct sections or content types
                3. Estimate the percentage of each content type
                4. Ensure percentages add up to 100%
                
                RESPONSE FORMAT:
                Return ONLY valid JSON matching this exact schema:
                {{
                    "composition": {{
                        "BRD": <percentage>,
                        "SRS": <percentage>,
                        "API_DOCS": <percentage>,
                        "USER_STORIES": <percentage>,
                        "TECHNICAL_SPECS": <percentage>,
                        "PROCESS_FLOWS": <percentage>,
                        "DATA_MODELS": <percentage>,
                        "SECURITY_REQUIREMENTS": <percentage>,
                        "PERFORMANCE_REQUIREMENTS": <percentage>,
                        "UI_UX_SPECS": <percentage>,
                        "UNKNOWN": <percentage>
                    }},
                    "confidence": "HIGH|MEDIUM|LOW",
                    "reasoning": "Brief explanation of your analysis approach"
                }}
                
                IMPORTANT:
                - Only include content types that are actually present
                - Set percentages to 0 for absent content types
                - Ensure all percentages are integers
                - Total must equal 100%
                """,
                "expected_schema": {
                    "type": "object",
                    "properties": {
                        "composition": {
                            "type": "object",
                            "properties": {
                                "BRD": {"type": "integer", "minimum": 0, "maximum": 100},
                                "SRS": {"type": "integer", "minimum": 0, "maximum": 100},
                                "API_DOCS": {"type": "integer", "minimum": 0, "maximum": 100},
                                "USER_STORIES": {"type": "integer", "minimum": 0, "maximum": 100},
                                "TECHNICAL_SPECS": {"type": "integer", "minimum": 0, "maximum": 100},
                                "PROCESS_FLOWS": {"type": "integer", "minimum": 0, "maximum": 100},
                                "DATA_MODELS": {"type": "integer", "minimum": 0, "maximum": 100},
                                "SECURITY_REQUIREMENTS": {"type": "integer", "minimum": 0, "maximum": 100},
                                "PERFORMANCE_REQUIREMENTS": {"type": "integer", "minimum": 0, "maximum": 100},
                                "UI_UX_SPECS": {"type": "integer", "minimum": 0, "maximum": 100},
                                "UNKNOWN": {"type": "integer", "minimum": 0, "maximum": 100}
                            },
                            "required": ["BRD", "SRS", "API_DOCS", "USER_STORIES", "TECHNICAL_SPECS", 
                                       "PROCESS_FLOWS", "DATA_MODELS", "SECURITY_REQUIREMENTS", 
                                       "PERFORMANCE_REQUIREMENTS", "UI_UX_SPECS", "UNKNOWN"]
                        },
                        "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["composition", "confidence", "reasoning"]
                }
            },
            
            PromptType.CONTENT_SEGMENTATION.value: {
                "version": "1.0",
                "description": "Segments document content based on composition analysis",
                "prompt": """
                You are an expert content analyst. Based on the composition analysis, segment the document text into logical sections.
                
                TASK:
                Analyze the document text and create segments based on the identified content types.
                
                SEGMENTATION RULES:
                1. Each segment should represent a distinct content type
                2. Segments should be logical and coherent
                3. Maintain the original text structure
                4. Identify start and end character positions
                
                RESPONSE FORMAT:
                Return ONLY valid JSON matching this exact schema:
                {{
                    "segments": [
                        {{
                            "segment_type": "BRD|SRS|API_DOCS|USER_STORIES|TECHNICAL_SPECS|PROCESS_FLOWS|DATA_MODELS|SECURITY_REQUIREMENTS|PERFORMANCE_REQUIREMENTS|UI_UX_SPECS|UNKNOWN",
                            "start_char_index": <integer>,
                            "end_char_index": <integer>,
                            "content_preview": "First 100 characters of the segment",
                            "confidence": "HIGH|MEDIUM|LOW"
                        }}
                    ],
                    "total_segments": <integer>,
                    "segmentation_quality": "HIGH|MEDIUM|LOW"
                }}
                
                IMPORTANT:
                - start_char_index and end_char_index must be valid positions in the text
                - Segments should not overlap
                - Cover the entire document text
                """,
                "expected_schema": {
                    "type": "object",
                    "properties": {
                        "segments": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "segment_type": {"type": "string"},
                                    "start_char_index": {"type": "integer", "minimum": 0},
                                    "end_char_index": {"type": "integer", "minimum": 0},
                                    "content_preview": {"type": "string"},
                                    "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]}
                                },
                                "required": ["segment_type", "start_char_index", "end_char_index", "content_preview", "confidence"]
                            }
                        },
                        "total_segments": {"type": "integer", "minimum": 1},
                        "segmentation_quality": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]}
                    },
                    "required": ["segments", "total_segments", "segmentation_quality"]
                }
            },
            
            PromptType.STRUCTURED_EXTRACTION.value: {
                "version": "1.0",
                "description": "Extracts structured data from document segments",
                "prompt": """
                You are an expert data extraction specialist. Extract structured information from the given document segment.
                
                TASK:
                Analyze the document segment and extract relevant structured data based on the segment type.
                
                EXTRACTION APPROACH:
                1. Identify the segment type and purpose
                2. Extract relevant entities, requirements, or specifications
                3. Structure the data in a logical format
                4. Maintain accuracy and completeness
                
                RESPONSE FORMAT:
                Return ONLY valid JSON with a structure appropriate for the content type.
                The response should be well-organized and contain all relevant extracted information.
                
                EXAMPLES BY SEGMENT TYPE:
                - BRD: Business requirements, stakeholders, business objectives
                - SRS: Functional requirements, non-functional requirements, constraints
                - API_DOCS: Endpoints, parameters, response formats, authentication
                - USER_STORIES: User personas, acceptance criteria, business value
                - TECHNICAL_SPECS: Technical details, architecture, implementation notes
                
                IMPORTANT:
                - Be comprehensive but concise
                - Use consistent naming conventions
                - Include all relevant details
                - Structure data logically
                """,
                "expected_schema": {
                    "type": "object",
                    "additionalProperties": True
                }
            },
            
            PromptType.CODE_ANALYSIS.value: {
                "version": "1.0",
                "description": "Analyzes source code for structure and purpose",
                "prompt": """
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
                """,
                "expected_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "structured_analysis": {
                            "type": "object",
                            "properties": {
                                "language_info": {
                                    "type": "object",
                                    "properties": {
                                        "primary_language": {"type": "string"},
                                        "framework": {"type": "string"},
                                        "file_type": {"type": "string"}
                                    }
                                },
                                "components": {"type": "array", "items": {"type": "object"}},
                                "dependencies": {"type": "array", "items": {"type": "string"}},
                                "exports": {"type": "array", "items": {"type": "string"}},
                                "patterns_and_architecture": {"type": "object"},
                                "quality_assessment": {"type": "string"}
                            }
                        }
                    }
                }
            },
            
            PromptType.IMAGE_ANALYSIS.value: {
                "version": "1.0",
                "description": "Analyzes images from technical documents",
                "prompt": """
                Analyze this image from a technical document. Provide a clear, concise description that would be useful for understanding the document's content.
                
                Focus on:
                - What the image shows (diagrams, charts, screenshots, etc.)
                - Key information or data presented
                - How it relates to technical documentation
                
                Return a brief, professional description suitable for inclusion in document text.
                """,
                "expected_schema": {"type": "string"}
            }
        }
    
    def get_prompt(self, prompt_type: PromptType, **kwargs) -> str:
        """
        Get a prompt of the specified type.
        
        Args:
            prompt_type: The type of prompt to retrieve
            **kwargs: Variables to substitute in the prompt
            
        Returns:
            The formatted prompt string
        """
        if prompt_type.value not in self.prompts:
            raise ValueError(f"Unknown prompt type: {prompt_type.value}")
        
        prompt_data = self.prompts[prompt_type.value]
        prompt = prompt_data["prompt"]
        
        # Apply any variable substitutions
        if kwargs:
            prompt = prompt.format(**kwargs)
        
        self.logger.debug(f"Retrieved prompt for type: {prompt_type.value}")
        return prompt
    
    def get_expected_schema(self, prompt_type: PromptType) -> Dict[str, Any]:
        """Get the expected schema for a prompt type."""
        if prompt_type.value not in self.prompts:
            raise ValueError(f"Unknown prompt type: {prompt_type.value}")
        
        return self.prompts[prompt_type.value]["expected_schema"]
    
    def add_custom_prompt(self, prompt_type: str, prompt: str, expected_schema: Dict[str, Any], version: str = "1.0"):
        """Add a custom prompt to the manager."""
        self.prompts[prompt_type] = {
            "version": version,
            "description": f"Custom prompt for {prompt_type}",
            "prompt": prompt,
            "expected_schema": expected_schema
        }
        self.logger.info(f"Added custom prompt for type: {prompt_type}")
    
    def list_prompt_types(self) -> list:
        """List all available prompt types."""
        return list(self.prompts.keys())
    
    def get_prompt_info(self, prompt_type: str) -> Dict[str, Any]:
        """Get information about a specific prompt type."""
        if prompt_type not in self.prompts:
            raise ValueError(f"Unknown prompt type: {prompt_type}")
        
        return {
            "type": prompt_type,
            "version": self.prompts[prompt_type]["version"],
            "description": self.prompts[prompt_type]["description"]
        }

# Global prompt manager instance
prompt_manager = PromptManager()
