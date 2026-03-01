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
    # SPRINT 3: Business Ontology Engine
    ENTITY_EXTRACTION = "entity_extraction"
    RELATIONSHIP_INFERENCE = "relationship_inference"
    SYNONYM_DETECTION = "synonym_detection"
    # SPRINT 3: Code Analysis Engine
    REPO_FILE_ANALYSIS = "repo_file_analysis"
    CODE_ENTITY_EXTRACTION = "code_entity_extraction"
    SOURCE_RECONCILIATION = "source_reconciliation"
    # SPRINT 3 Day 5: Enhanced Semantic Analysis (AI-02)
    ENHANCED_SEMANTIC_ANALYSIS = "enhanced_semantic_analysis"
    DELTA_ANALYSIS = "delta_analysis"
    # SPRINT 4: Repository Synthesis (Reduce Phase)
    REPOSITORY_SYNTHESIS = "repository_synthesis"

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
            },

            # ============================================================
            # SPRINT 3: Business Ontology Engine Prompts
            # ============================================================

            PromptType.ENTITY_EXTRACTION.value: {
                "version": "1.0",
                "description": "Extracts named entities from document analysis results to populate the business ontology",
                "prompt": """
You are an expert business analyst extracting domain entities from structured document analysis data.

TASK:
From the structured analysis data below, extract all meaningful business entities that should be tracked in a knowledge graph. These entities represent the key concepts, actors, systems, and rules that define this business domain.

ENTITY TYPES TO EXTRACT:
- ACTOR: People, roles, or personas (e.g., "Admin User", "Payment Gateway")
- SYSTEM: Software systems, services, or platforms (e.g., "Order Management System", "Redis Cache")
- FEATURE: Product features or capabilities (e.g., "User Authentication", "Report Generation")
- TECHNOLOGY: Programming languages, frameworks, tools (e.g., "React", "PostgreSQL", "Docker")
- PROCESS: Business processes or workflows (e.g., "Order Fulfillment", "User Onboarding")
- RULE: Business rules or constraints (e.g., "Max 3 login attempts", "Orders over $500 need approval")
- DATA_ENTITY: Data objects or models (e.g., "Customer Record", "Invoice", "Product Catalog")
- REQUIREMENT: Specific requirements (e.g., "Response time < 200ms", "GDPR Compliance")

EXTRACTION RULES:
1. Extract specific, named entities — not generic terms
2. Normalize names: use Title Case, be consistent
3. Assign a confidence score (0.0-1.0) based on how clearly the entity appears
4. Include brief context showing WHERE in the analysis you found this entity
5. Deduplicate: if the same concept appears multiple times, list it once with the highest confidence

RESPONSE FORMAT:
Return ONLY valid JSON:
{{
    "entities": [
        {{
            "name": "Entity Name",
            "type": "ACTOR|SYSTEM|FEATURE|TECHNOLOGY|PROCESS|RULE|DATA_ENTITY|REQUIREMENT",
            "context": "Brief quote or description of where this entity was found",
            "confidence": 0.85
        }}
    ],
    "relationships": [
        {{
            "source": "Entity Name A",
            "target": "Entity Name B",
            "relationship_type": "implements|depends_on|is_part_of|validates|uses|produces|consumes",
            "confidence": 0.75
        }}
    ]
}}

STRUCTURED ANALYSIS DATA TO PROCESS:
""",
                "expected_schema": {
                    "type": "object",
                    "properties": {
                        "entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string"},
                                    "context": {"type": "string"},
                                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                                },
                                "required": ["name", "type", "context", "confidence"]
                            }
                        },
                        "relationships": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "source": {"type": "string"},
                                    "target": {"type": "string"},
                                    "relationship_type": {"type": "string"},
                                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                                },
                                "required": ["source", "target", "relationship_type", "confidence"]
                            }
                        }
                    },
                    "required": ["entities", "relationships"]
                }
            },

            PromptType.SYNONYM_DETECTION.value: {
                "version": "1.0",
                "description": "Detects synonym pairs from a list of ontology concept names",
                "prompt": """
You are a domain terminology expert. Given a list of concept names from a business knowledge graph, identify pairs that are synonyms or near-synonyms within a software/business context.

RULES:
1. Only flag genuine synonyms — terms that mean the SAME thing in a software/business context
2. Do NOT flag terms that are merely related (e.g., "Database" and "Cache" are related but NOT synonyms)
3. Consider abbreviations as synonyms (e.g., "API" and "Application Programming Interface")
4. Consider naming variations as synonyms (e.g., "User Auth" and "User Authentication")
5. Assign a confidence score (0.0-1.0) for each pair
6. For each pair, recommend which term should be the canonical (preferred) name

RESPONSE FORMAT:
Return ONLY valid JSON:
{{
    "synonym_pairs": [
        {{
            "term_a": "First term",
            "term_b": "Second term",
            "canonical": "The preferred term to keep",
            "confidence": 0.9,
            "reasoning": "Brief explanation of why these are synonyms"
        }}
    ]
}}

If no synonyms are found, return: {{"synonym_pairs": []}}

CONCEPT NAMES TO ANALYZE:
""",
                "expected_schema": {
                    "type": "object",
                    "properties": {
                        "synonym_pairs": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "term_a": {"type": "string"},
                                    "term_b": {"type": "string"},
                                    "canonical": {"type": "string"},
                                    "confidence": {"type": "number"},
                                    "reasoning": {"type": "string"}
                                },
                                "required": ["term_a", "term_b", "canonical", "confidence"]
                            }
                        }
                    },
                    "required": ["synonym_pairs"]
                }
            },

            # ============================================================
            # SPRINT 3: Code Analysis Engine — Enhanced Repo File Prompt
            # ============================================================

            PromptType.REPO_FILE_ANALYSIS.value: {
                "version": "1.0",
                "description": "Enhanced analysis for files within a repository context — extracts inter-file dependencies and domain signals",
                "prompt": """
You are an expert software architect performing deep analysis of a source file within a larger repository.

CONTEXT:
- Repository: {repo_name}
- File path: {file_path}
- Language hint: {language}

TASK:
Analyze this file with emphasis on:
1. **Purpose & Role**: What does this file do within the repository?
2. **Public API**: Functions, classes, endpoints, or exports that other files depend on
3. **Internal Dependencies**: Which other files/modules does this file import from the SAME repo?
4. **External Dependencies**: Third-party libraries or frameworks used
5. **Domain Concepts**: Business terms, domain entities, or domain-specific patterns
6. **Quality Signals**: Error handling, test coverage hints, security patterns

STRICT RESPONSE FORMAT:
Return ONLY valid JSON:
{{
    "summary": "2-3 sentences describing the file's purpose and role in the system",
    "structured_analysis": {{
        "language_info": {{
            "primary_language": "Detected language",
            "framework": "Framework if any",
            "file_type": "Service|Controller|Model|Component|Utility|Config|Test|Migration"
        }},
        "public_api": [
            {{
                "name": "Exported function/class/const name",
                "type": "Function|Class|Constant|Type|Endpoint",
                "signature": "Simplified signature or description",
                "purpose": "One sentence"
            }}
        ],
        "internal_imports": [
            "Relative imports from the same repository (e.g., ../utils/helpers)"
        ],
        "external_imports": [
            "Third-party packages (e.g., fastapi, react, lodash)"
        ],
        "domain_concepts": [
            {{
                "term": "Business term found in the code",
                "context": "How it's used (variable name, class name, comment, etc.)"
            }}
        ],
        "components": [
            {{
                "name": "Element name",
                "type": "Function|Class|Method|Component|Route|Hook",
                "purpose": "What it does",
                "details": "Parameters, return type, key logic"
            }}
        ],
        "patterns_and_architecture": {{
            "design_patterns": ["Patterns observed"],
            "architectural_style": "Overall style",
            "key_concepts": ["Programming concepts used"]
        }},
        "quality_assessment": "Brief quality assessment"
    }}
}}
""",
                "expected_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "structured_analysis": {"type": "object"}
                    },
                    "required": ["summary", "structured_analysis"]
                }
            },

            # ============================================================
            # SPRINT 3: Dual-Source BOE — Code Entity Extraction Prompt
            # ============================================================

            PromptType.CODE_ENTITY_EXTRACTION.value: {
                "version": "1.0",
                "description": "Extracts business-relevant entities from code analysis results to populate the ontology from code sources",
                "prompt": """
You are an expert software architect extracting business-relevant entities from code analysis data.

CONTEXT:
Unlike document analysis (which extracts from BRDs/specs), this extraction runs on CODE analysis results.
Your job is to identify entities that bridge the gap between what documents describe and what code implements.

ENTITY TYPES TO EXTRACT:
- SYSTEM: Services, microservices, modules (e.g., "Payment Service", "Auth Module")
- FEATURE: Implemented features or capabilities visible in the code (e.g., "JWT Authentication", "File Upload")
- TECHNOLOGY: Frameworks, libraries, tools actually used (e.g., "FastAPI", "SQLAlchemy", "Redis")
- DATA_ENTITY: Database models, schemas, data structures (e.g., "User Model", "Order Table", "Invoice Schema")
- API_ENDPOINT: REST/GraphQL endpoints (e.g., "POST /api/v1/documents/upload", "GET /users")
- PROCESS: Business workflows implemented in code (e.g., "Document Analysis Pipeline", "Checkout Flow")
- RULE: Business rules enforced in code (e.g., "Rate Limit 15 RPM", "Tenant Isolation Check")
- DEPENDENCY: Key external dependencies (e.g., "Google Gemini API", "Stripe SDK")

EXTRACTION RULES:
1. Focus on BUSINESS-RELEVANT entities — skip generic utilities, test helpers, boilerplate
2. Use the same naming conventions as document extraction for cross-referencing:
   - Title Case for names
   - Be specific: "User Authentication Service" not just "Auth"
3. For API endpoints, include the HTTP method and path
4. For business rules, describe the constraint as found in code
5. Assign confidence 0.7-1.0 (code is explicit, so confidence should generally be high)
6. Include the file path or function name as context

RELATIONSHIP TYPES:
- implements: Code entity implements a business concept
- depends_on: One entity requires another
- uses: Entity uses a technology/library
- exposes: Service exposes an API endpoint
- enforces: Code enforces a business rule
- persists: Code manages a data entity

RESPONSE FORMAT:
Return ONLY valid JSON:
{{
    "entities": [
        {{
            "name": "Entity Name",
            "type": "SYSTEM|FEATURE|TECHNOLOGY|DATA_ENTITY|API_ENDPOINT|PROCESS|RULE|DEPENDENCY",
            "context": "File path or function where this was found",
            "confidence": 0.85
        }}
    ],
    "relationships": [
        {{
            "source": "Entity Name A",
            "target": "Entity Name B",
            "relationship_type": "implements|depends_on|uses|exposes|enforces|persists",
            "confidence": 0.75
        }}
    ]
}}

CODE ANALYSIS DATA TO PROCESS:
""",
                "expected_schema": {
                    "type": "object",
                    "properties": {
                        "entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string"},
                                    "context": {"type": "string"},
                                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                                },
                                "required": ["name", "type", "context", "confidence"]
                            }
                        },
                        "relationships": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "source": {"type": "string"},
                                    "target": {"type": "string"},
                                    "relationship_type": {"type": "string"},
                                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                                },
                                "required": ["source", "target", "relationship_type", "confidence"]
                            }
                        }
                    },
                    "required": ["entities", "relationships"]
                }
            },

            # ============================================================
            # SPRINT 3: Dual-Source BOE — Reconciliation Prompt
            # ============================================================

            PromptType.SOURCE_RECONCILIATION.value: {
                "version": "1.0",
                "description": "Maps document-layer concepts to code-layer concepts, creating bridge relationships and detecting contradictions",
                "prompt": """
You are an expert solution architect reconciling business requirements (from BRD/SRS documents) with their implementation (from production code analysis).

CONTEXT:
You are given two sets of concepts:
1. DOCUMENT CONCEPTS — extracted from BRD/SRS documents (the "what should be")
2. CODE CONCEPTS — extracted from production code analysis (the "what is")

Your job is to find which code concepts IMPLEMENT, ENFORCE, or CONTRADICT which document concepts.

IMPORTANT RULES:
1. Documents describe things at a BUSINESS level (features, processes, rules)
2. Code describes things at an IMPLEMENTATION level (services, APIs, data models)
3. They are at DIFFERENT abstraction levels — a single document "Feature" may map to MULTIPLE code "Systems"
4. A code "System" may implement parts of MULTIPLE document "Features"
5. Not every document concept will have a code counterpart (unimplemented requirements)
6. Not every code concept will have a document counterpart (undocumented features)

BRIDGE RELATIONSHIP TYPES:
- "implements": Code concept fully implements what the document concept describes
- "partially_implements": Code concept covers SOME aspects of the document concept
- "enforces": Code concept enforces a business rule described in the document
- "contradicts": Code does something DIFFERENT from what the document says (THIS IS A MISMATCH!)
- "extends": Code adds functionality beyond what the document specified
- "undocumented": Code concept exists but has NO corresponding document concept

MISMATCH DETECTION:
- If a document says "Max 3 login attempts" but code has MAX_RETRIES=5 → "contradicts"
- If a document says "Payment requires approval over $500" but code has no such check → the document concept has no bridge (unimplemented)
- If code has a feature the document doesn't mention → "undocumented"

RESPONSE FORMAT:
Return ONLY valid JSON:
{{
    "bridges": [
        {{
            "document_concept": "Exact name of the document concept",
            "code_concept": "Exact name of the code concept",
            "relationship": "implements|partially_implements|enforces|contradicts|extends",
            "confidence": 0.85,
            "reasoning": "Brief explanation of WHY this mapping exists",
            "mismatch_detail": null
        }}
    ],
    "unimplemented": [
        {{
            "document_concept": "Name of document concept with NO code counterpart",
            "severity": "high|medium|low",
            "reasoning": "Why this is concerning"
        }}
    ],
    "undocumented": [
        {{
            "code_concept": "Name of code concept with NO document counterpart",
            "severity": "high|medium|low",
            "reasoning": "Why this matters (e.g., 'Critical payment logic not in any BRD')"
        }}
    ],
    "contradictions": [
        {{
            "document_concept": "What the document says",
            "code_concept": "What the code does",
            "document_says": "Specific claim from the document",
            "code_does": "What the code actually implements",
            "severity": "high|medium|low",
            "recommended_action": "Which side should change and why"
        }}
    ]
}}

CONCEPTS TO RECONCILE:
""",
                "expected_schema": {
                    "type": "object",
                    "properties": {
                        "bridges": {"type": "array"},
                        "unimplemented": {"type": "array"},
                        "undocumented": {"type": "array"},
                        "contradictions": {"type": "array"}
                    },
                    "required": ["bridges", "unimplemented", "undocumented", "contradictions"]
                }
            },

            # ============================================================
            # SPRINT 3 Day 5: Enhanced Semantic Code Analysis (AI-02)
            # ============================================================

            PromptType.ENHANCED_SEMANTIC_ANALYSIS.value: {
                "version": "2.0",
                "description": "Enhanced code analysis with business rules, API contracts, data models, and security pattern extraction",
                "prompt": """
You are an expert software architect performing deep semantic analysis of a source file.

CONTEXT:
- Repository: {repo_name}
- File path: {file_path}
- Language: {language}

{language_specific_guidance}

TASK:
Perform a comprehensive analysis extracting ALL of the following:

1. **BUSINESS RULES** — Logic constraints, validation rules, thresholds, conditional workflows
   - Look for: if/else branches with business meaning, constants with domain significance,
     validation functions, authorization checks, state machines, workflow transitions
   - Example: "Orders over $500 require manager approval" → found in `if order.total > 500`

2. **API CONTRACTS** — Endpoints, request/response schemas, authentication requirements
   - Look for: route decorators, handler functions, request body schemas, response models,
     status codes, middleware, rate limits, versioning
   - Example: "POST /api/v1/orders requires auth, accepts OrderCreate, returns 201"

3. **DATA MODEL RELATIONSHIPS** — How data entities relate to each other
   - Look for: foreign keys, relationships, joins, nested schemas, cascade rules,
     many-to-many through tables, inheritance hierarchies
   - Example: "User has-many Orders, Order belongs-to User via user_id FK"

4. **SECURITY PATTERNS** — Authentication, authorization, input validation, encryption
   - Look for: auth decorators/middleware, role checks, RBAC, token validation,
     input sanitization, SQL injection prevention, CORS config, secrets management
   - Example: "JWT Bearer auth required on all /api endpoints, RBAC with 4 roles"

5. **STANDARD ANALYSIS** — Components, dependencies, patterns (as before)

6. **COMPONENT INTERACTIONS** — How functions/classes call, inherit, or delegate to each other
   - Look for: function calls within the file, class inheritance, method delegation,
     validation chains, middleware pipelines, event handler wiring
   - Example: "OrderService.create_order() calls PaymentService.charge() and EmailService.notify()"

7. **DATA FLOWS** — How data moves through the file from input to output
   - Look for: request parameters flowing through processing, database reads feeding transforms,
     API responses being assembled, config values driving behavior
   - Example: "User input → validate() → transform() → db.save() → response"

STRICT RESPONSE FORMAT:
Return ONLY valid JSON:
{{
    "summary": "2-3 sentences describing the file's purpose and role",
    "structured_analysis": {{
        "language_info": {{
            "primary_language": "Detected language",
            "framework": "Framework if any",
            "file_type": "Service|Controller|Model|Component|Utility|Config|Test|Migration|Middleware"
        }},
        "business_rules": [
            {{
                "rule_id": "BR-001",
                "description": "Human-readable description of the business rule",
                "code_location": "function name or line reference where this rule lives",
                "rule_type": "validation|authorization|workflow|constraint|calculation|threshold",
                "parameters": {{"key": "value"}},
                "confidence": 0.9
            }}
        ],
        "api_contracts": [
            {{
                "method": "GET|POST|PUT|DELETE|PATCH",
                "path": "/api/endpoint/path",
                "description": "What this endpoint does",
                "request_schema": "Schema name or inline description of expected input",
                "response_schema": "Schema name or inline description of output",
                "auth_required": true,
                "status_codes": [200, 400, 404],
                "rate_limited": false
            }}
        ],
        "data_model_relationships": [
            {{
                "source_entity": "Entity name (e.g., User)",
                "target_entity": "Related entity (e.g., Order)",
                "relationship_type": "has_many|belongs_to|has_one|many_to_many",
                "foreign_key": "column name if applicable",
                "cascade": "delete|set_null|restrict|none",
                "description": "Brief description of the relationship"
            }}
        ],
        "security_patterns": [
            {{
                "pattern_type": "authentication|authorization|input_validation|encryption|secrets|cors|csrf|rate_limiting",
                "description": "What security measure is implemented",
                "implementation": "How it's implemented (e.g., 'JWT Bearer via Depends(get_current_user)')",
                "coverage": "Which endpoints/functions are protected",
                "gaps": "Any noted security gaps or missing protections"
            }}
        ],
        "component_interactions": [
            {{
                "source": "Function/Class that initiates the call",
                "target": "Function/Class that is called or referenced",
                "interaction_type": "calls|inherits|instantiates|validates_with|delegates_to|overrides|listens_to",
                "description": "Brief description of the interaction",
                "data_passed": "What data flows between them"
            }}
        ],
        "data_flows": [
            {{
                "name": "Short description of the flow",
                "source": "Where data originates (e.g., request body, DB query, config)",
                "destination": "Where data goes (e.g., response, DB write, external API)",
                "transformations": "What processing happens along the way",
                "data_type": "user_input|db_record|api_response|config|event|file_content"
            }}
        ],
        "components": [
            {{
                "name": "Element name",
                "type": "Function|Class|Method|Component|Route|Hook|Middleware",
                "purpose": "What it does",
                "details": "Parameters, return type, key logic"
            }}
        ],
        "dependencies": ["List of imports/dependencies"],
        "exports": ["What this file exports"],
        "patterns_and_architecture": {{
            "design_patterns": ["Patterns observed"],
            "architectural_style": "Overall style",
            "key_concepts": ["Programming concepts used"]
        }},
        "quality_assessment": "Brief quality assessment"
    }}
}}

CRITICAL:
- For business_rules: Extract ACTUAL rules from code logic, not just comments
- For api_contracts: Include ALL endpoints with their full contract
- For data_model_relationships: Include FK constraints and cascade behavior
- For security_patterns: Note GAPS as well as implemented patterns
- For component_interactions: Extract ALL function-to-function calls, class inheritance, and delegation patterns within this file
- For data_flows: Trace how data enters, transforms, and exits — this is crucial for understanding business logic
- If a section is not applicable to this file type, return an empty array []

CODE TO ANALYZE:
""",
                "expected_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "structured_analysis": {
                            "type": "object",
                            "properties": {
                                "language_info": {"type": "object"},
                                "business_rules": {"type": "array"},
                                "api_contracts": {"type": "array"},
                                "data_model_relationships": {"type": "array"},
                                "security_patterns": {"type": "array"},
                                "component_interactions": {"type": "array"},
                                "data_flows": {"type": "array"},
                                "components": {"type": "array"},
                                "dependencies": {"type": "array"},
                                "exports": {"type": "array"},
                                "patterns_and_architecture": {"type": "object"},
                                "quality_assessment": {"type": "string"}
                            }
                        }
                    },
                    "required": ["summary", "structured_analysis"]
                }
            },

            # ============================================================
            # SPRINT 3 Day 5: Delta Analysis (AI-02)
            # ============================================================

            PromptType.DELTA_ANALYSIS.value: {
                "version": "1.0",
                "description": "Compares new analysis with previous analysis to detect meaningful changes",
                "prompt": """
You are a software change analyst. Compare the PREVIOUS analysis of a code file with its CURRENT analysis to identify meaningful changes.

CONTEXT:
- File: {file_path}
- This file was previously analyzed and has been re-analyzed after code changes.

TASK:
Compare the two analyses and identify:
1. **Added** — New components, rules, endpoints, or patterns that didn't exist before
2. **Removed** — Components, rules, endpoints, or patterns that no longer exist
3. **Modified** — Elements that changed (different parameters, logic, contracts)
4. **Impact** — What the changes mean for the broader system

IMPORTANT:
- Focus on MEANINGFUL changes, not cosmetic ones (renamed variables, reformatted code)
- Flag breaking changes (removed endpoints, changed API contracts, weakened security)
- Identify new business rules or modified business rules as HIGH priority

RESPONSE FORMAT:
Return ONLY valid JSON:
{{
    "has_changes": true,
    "change_summary": "1-2 sentence summary of what changed",
    "changes": {{
        "added": [
            {{
                "category": "business_rule|api_contract|component|security_pattern|data_model|dependency",
                "name": "Name of what was added",
                "description": "What was added",
                "impact": "high|medium|low"
            }}
        ],
        "removed": [
            {{
                "category": "business_rule|api_contract|component|security_pattern|data_model|dependency",
                "name": "Name of what was removed",
                "description": "What was removed",
                "impact": "high|medium|low",
                "breaking": true
            }}
        ],
        "modified": [
            {{
                "category": "business_rule|api_contract|component|security_pattern|data_model|dependency",
                "name": "Name of modified element",
                "previous": "What it was before",
                "current": "What it is now",
                "impact": "high|medium|low",
                "breaking": false
            }}
        ]
    }},
    "risk_assessment": {{
        "overall_risk": "high|medium|low|none",
        "breaking_changes_count": 0,
        "requires_doc_update": false,
        "requires_test_update": false,
        "reasoning": "Why this risk level"
    }}
}}

If no meaningful changes were detected, return:
{{"has_changes": false, "change_summary": "No meaningful changes detected", "changes": {{"added": [], "removed": [], "modified": []}}, "risk_assessment": {{"overall_risk": "none", "breaking_changes_count": 0, "requires_doc_update": false, "requires_test_update": false, "reasoning": "No changes"}}}}

PREVIOUS ANALYSIS:
{previous_analysis}

CURRENT ANALYSIS:
{current_analysis}
""",
                "expected_schema": {
                    "type": "object",
                    "properties": {
                        "has_changes": {"type": "boolean"},
                        "change_summary": {"type": "string"},
                        "changes": {
                            "type": "object",
                            "properties": {
                                "added": {"type": "array"},
                                "removed": {"type": "array"},
                                "modified": {"type": "array"}
                            }
                        },
                        "risk_assessment": {"type": "object"}
                    },
                    "required": ["has_changes", "change_summary", "changes", "risk_assessment"]
                }
            },

            # ============================================================
            # SPRINT 4: Repository Synthesis — "Reduce Phase"
            # Combines per-file analyses into a System Architecture document
            # ============================================================

            PromptType.REPOSITORY_SYNTHESIS.value: {
                "version": "1.0",
                "description": "Synthesizes per-file code analyses into a comprehensive System Architecture document",
                "prompt": """
You are an expert solution architect. You have been given summaries of individual file analyses from a code repository, grouped by architectural layer.

CONTEXT:
- Repository: {repo_name}
- Total files analyzed: {total_files}
- Architectural layers detected: {layer_count}

TASK:
Synthesize these per-file analyses into a comprehensive System Architecture document. Do NOT just summarize each file — identify cross-cutting patterns, data flows, and architectural decisions that emerge from looking at the codebase as a whole.

LAYER SUMMARIES:
{layer_summaries}

STRICT RESPONSE FORMAT:
Return ONLY valid JSON:
{{
    "system_overview": "3-5 sentence executive summary of what this system does, its architecture style, and its key capabilities",
    "architecture": {{
        "style": "The dominant architectural style (e.g., Monolithic MVC, Microservices, Layered, Event-Driven, Hexagonal)",
        "layers": [
            {{
                "name": "Layer name (e.g., API Layer, Service Layer, Data Access Layer)",
                "description": "What this layer does",
                "key_files": ["List of critical files in this layer"],
                "patterns": ["Patterns used in this layer"]
            }}
        ],
        "patterns": ["Cross-cutting architectural patterns (e.g., Repository Pattern, Dependency Injection, CQRS)"]
    }},
    "data_flow": [
        {{
            "name": "Flow name (e.g., User Registration, Order Processing)",
            "description": "End-to-end description of the data flow",
            "steps": ["Step 1: Request hits controller", "Step 2: Service validates", "Step 3: Repository persists"]
        }}
    ],
    "api_surface": {{
        "total_endpoints": 0,
        "key_endpoints": [
            {{
                "method": "GET|POST|PUT|DELETE",
                "path": "/api/endpoint",
                "description": "What it does",
                "auth_required": true
            }}
        ],
        "authentication_mechanism": "How auth works across the API"
    }},
    "technology_stack": {{
        "languages": ["Primary languages with versions if detectable"],
        "frameworks": ["Key frameworks"],
        "databases": ["Database technologies"],
        "infrastructure": ["Docker, K8s, CI/CD tools if detectable"],
        "third_party": ["External services/APIs used"]
    }},
    "security_posture": {{
        "strengths": ["Security patterns implemented well"],
        "gaps": ["Potential security concerns or missing protections"],
        "authentication": "Auth mechanism summary",
        "authorization": "RBAC/permission model summary"
    }},
    "quality_observations": {{
        "strengths": ["Code quality strengths"],
        "concerns": ["Code quality concerns"],
        "test_coverage": "Observed testing approach",
        "documentation_quality": "How well the code is documented"
    }},
    "cross_cutting_concerns": [
        {{
            "concern": "Concern name (e.g., Logging, Error Handling, Configuration)",
            "approach": "How this concern is handled across the codebase",
            "consistency": "high|medium|low"
        }}
    ]
}}

CRITICAL:
- Synthesize ACROSS files — don't just list individual file summaries
- Identify the SYSTEM ARCHITECTURE that emerges from these files together
- Flag contradictions (e.g., different auth patterns in different controllers)
- Identify data flows that span multiple files
- Note any architectural debt or inconsistencies
""",
                "expected_schema": {
                    "type": "object",
                    "properties": {
                        "system_overview": {"type": "string"},
                        "architecture": {"type": "object"},
                        "data_flow": {"type": "array"},
                        "api_surface": {"type": "object"},
                        "technology_stack": {"type": "object"},
                        "security_posture": {"type": "object"},
                        "quality_observations": {"type": "object"},
                        "cross_cutting_concerns": {"type": "array"}
                    },
                    "required": ["system_overview", "architecture", "technology_stack"]
                }
            }
        }

    # ============================================================
    # SPRINT 3 Day 5: Language-Specific Analysis Templates
    # ============================================================

    LANGUAGE_TEMPLATES = {
        "python": """
LANGUAGE-SPECIFIC GUIDANCE (Python / FastAPI / Django):
- Look for FastAPI route decorators: @router.get(), @router.post(), @app.get(), etc.
- Extract Pydantic models used as request/response schemas (BaseModel subclasses)
- Identify SQLAlchemy models and their relationships (relationship(), ForeignKey, mapped_column)
- Find Depends() injection patterns for auth, DB sessions, tenant isolation
- Detect Celery task definitions (@celery_app.task) and their retry/rate-limit configs
- Look for middleware (app.add_middleware) and exception handlers
- Identify business rules in service methods (if/else logic with domain meaning)
- Check for alembic migration patterns
- Note: Python uses type hints — extract parameter types and return types
""",
        "javascript": """
LANGUAGE-SPECIFIC GUIDANCE (JavaScript / TypeScript / React / Next.js):
- Look for React component definitions (function components, class components, hooks)
- Extract Next.js API routes (pages/api/ or app/api/ route handlers)
- Identify useState, useEffect, useContext, useReducer and custom hooks
- Find data fetching patterns: fetch(), axios, SWR, React Query, tRPC
- Detect form validation (Zod, Yup, Formik, React Hook Form)
- Look for Redux/Zustand/Jotai state management patterns
- Extract TypeScript interfaces and type definitions as data models
- Identify middleware in Express/Next.js (auth, CORS, rate limiting)
- Note: Look for .tsx/.jsx for component files, .ts for services/utils
""",
        "java": """
LANGUAGE-SPECIFIC GUIDANCE (Java / Spring Boot):
- Look for @RestController, @GetMapping, @PostMapping, @RequestMapping annotations
- Extract @Entity JPA models and their @OneToMany, @ManyToOne, @ManyToMany relationships
- Identify @Service, @Repository, @Component Spring beans and their dependencies
- Find @Autowired/@Inject dependency injection patterns
- Detect Spring Security config: @PreAuthorize, @Secured, SecurityFilterChain
- Look for @Transactional boundaries and their propagation/isolation settings
- Extract DTO/VO classes used for request/response mapping
- Identify @Valid/@Validated input validation with Bean Validation annotations
- Note: Java uses annotations heavily — extract all relevant annotations
""",
        "go": """
LANGUAGE-SPECIFIC GUIDANCE (Go / Golang):
- Look for HTTP handlers: http.HandleFunc, gin.Context, echo.Context, chi.Router
- Extract struct definitions as data models and their JSON/DB tags
- Identify interface definitions and their implementations
- Find middleware patterns (func(http.Handler) http.Handler)
- Detect error handling patterns (error returns, custom error types)
- Look for database/sql or GORM model definitions
- Extract goroutine/channel patterns for concurrent processing
""",
        "typescript": """
LANGUAGE-SPECIFIC GUIDANCE (TypeScript / Node.js):
- Look for Express/Koa/Fastify route handlers and middleware
- Extract TypeScript interfaces, types, and enums as data contracts
- Identify Prisma/TypeORM/Sequelize model definitions and relations
- Find NestJS decorators (@Controller, @Injectable, @Module) if present
- Detect Zod/Joi/class-validator validation schemas
- Look for generic types and utility types for API contract definitions
- Extract tRPC router definitions if present
"""
    }

    def get_language_guidance(self, language: str) -> str:
        """Get language-specific analysis guidance for the enhanced prompt."""
        if not language:
            return ""
        lang_lower = language.lower().strip()
        # Match against known templates
        for key, template in self.LANGUAGE_TEMPLATES.items():
            if key in lang_lower:
                return template
        # Check common aliases
        aliases = {
            "py": "python", "python3": "python",
            "js": "javascript", "jsx": "javascript", "tsx": "typescript",
            "ts": "typescript", "node": "javascript", "react": "javascript",
            "nextjs": "javascript", "next.js": "javascript",
            "fastapi": "python", "django": "python", "flask": "python",
            "spring": "java", "springboot": "java", "spring-boot": "java",
            "golang": "go",
        }
        for alias, lang_key in aliases.items():
            if alias in lang_lower:
                return self.LANGUAGE_TEMPLATES.get(lang_key, "")
        return ""

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
