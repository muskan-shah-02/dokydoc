# backend/app/services/code_analysis_service.py

import re
import httpx
from sqlalchemy.orm import Session
import asyncio

from app import crud
from app.db.session import SessionLocal
from app.services.ai.gemini import call_gemini_for_code_analysis
from app.services.cache_service import cache_service
from app.services.cost_service import cost_service
from app.services.billing_enforcement_service import billing_enforcement_service, InsufficientBalanceException, MonthlyLimitExceededException
from app.core.logging import LoggerMixin
from app.core.exceptions import DocumentProcessingException, AIAnalysisException

class CodeAnalysisService(LoggerMixin):
    
    def __init__(self):
        super().__init__()

    # ================================================================
    # GitHub URL Detection & Resolution
    # ================================================================

    # File extensions to include for code analysis
    # Expanded to capture web, config, data, infra, and documentation files
    CODE_EXTENSIONS = {
        # Programming languages
        '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs',
        '.rb', '.php', '.cs', '.cpp', '.c', '.h', '.hpp', '.swift', '.kt',
        '.scala', '.lua', '.dart', '.r', '.m', '.mm',
        '.ex', '.exs',        # Elixir
        '.clj', '.cljs',      # Clojure
        '.hs',                 # Haskell
        '.ml', '.mli',        # OCaml
        '.zig',                # Zig
        # Web frontend
        '.vue', '.svelte', '.html', '.htm', '.css', '.scss', '.sass', '.less',
        # Data & config
        '.json', '.yaml', '.yml', '.toml', '.xml', '.ini', '.cfg', '.conf',
        '.env.example', '.env.sample',
        # Database & queries
        '.sql', '.prisma', '.graphql', '.gql',
        # Shell & scripting
        '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
        # Infrastructure & CI/CD
        '.tf', '.hcl',        # Terraform
        '.dockerfile',
        # Protocol & serialization
        '.proto',              # Protobuf
        # Documentation (code-adjacent)
        '.md', '.rst', '.txt',
        # Build & project files
        '.gradle', '.cmake', '.makefile',
    }
    # Directories to skip
    SKIP_DIRS = {
        'node_modules', '.git', '__pycache__', '.next', 'dist', 'build',
        '.venv', 'venv', 'env', '.env', 'vendor', '.idea', '.vscode',
        'coverage', '.pytest_cache', '.mypy_cache', '.tox',
        '.gradle', '.cache', 'target', 'bin', 'obj',
        '.terraform', '.serverless', '.vercel',
    }
    # Language detection by extension
    EXT_TO_LANG = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
        '.tsx': 'typescript', '.jsx': 'javascript', '.java': 'java',
        '.go': 'go', '.rs': 'rust', '.rb': 'ruby', '.php': 'php',
        '.cs': 'csharp', '.cpp': 'cpp', '.c': 'c', '.h': 'c',
        '.hpp': 'cpp', '.swift': 'swift',
        '.kt': 'kotlin', '.scala': 'scala', '.lua': 'lua',
        '.dart': 'dart', '.r': 'r', '.m': 'objective-c', '.mm': 'objective-cpp',
        '.ex': 'elixir', '.exs': 'elixir',
        '.clj': 'clojure', '.cljs': 'clojurescript',
        '.hs': 'haskell', '.ml': 'ocaml', '.mli': 'ocaml', '.zig': 'zig',
        '.vue': 'javascript', '.svelte': 'javascript',
        '.html': 'html', '.htm': 'html',
        '.css': 'css', '.scss': 'scss', '.sass': 'sass', '.less': 'less',
        '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml',
        '.toml': 'toml', '.xml': 'xml', '.ini': 'ini',
        '.sql': 'sql', '.prisma': 'prisma',
        '.graphql': 'graphql', '.gql': 'graphql',
        '.sh': 'shell', '.bash': 'shell', '.zsh': 'shell', '.fish': 'shell',
        '.ps1': 'powershell', '.bat': 'batch', '.cmd': 'batch',
        '.tf': 'terraform', '.hcl': 'hcl',
        '.dockerfile': 'dockerfile',
        '.proto': 'protobuf',
        '.md': 'markdown', '.rst': 'restructuredtext',
        '.gradle': 'gradle', '.cmake': 'cmake',
    }

    def _detect_github_url_type(self, url: str) -> tuple:
        """
        Classify a GitHub URL as single_file, repository, or other.

        Returns:
            ("single_file", owner, repo, blob_path) for blob URLs
            ("repository", owner, repo, branch) for repo/tree URLs
            ("other", None, None, None) for non-GitHub URLs
        """
        blob_match = re.match(
            r'https?://github\.com/([^/]+)/([^/]+)/blob/(.+)', url
        )
        if blob_match:
            owner, repo, blob_path = blob_match.groups()
            return ("single_file", owner, repo, blob_path)

        tree_match = re.match(
            r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/tree/(.+?))?(?:\?.*)?$',
            url
        )
        if tree_match:
            owner, repo, ref_path = tree_match.groups()
            branch = ref_path or "main"
            return ("repository", owner, repo, branch)

        return ("other", None, None, None)

    async def _fetch_single_github_file(self, owner: str, repo: str, blob_path: str) -> str:
        """Fetch a single file from GitHub raw content."""
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{blob_path}"
        self.logger.info(f"Fetching single file from GitHub: {raw_url}")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(raw_url)
            resp.raise_for_status()
            return resp.text

    async def _get_repo_file_list(self, owner: str, repo: str, branch: str) -> list:
        """
        Get the file list for a GitHub repository, suitable for dispatching
        to repo_analysis_task. Returns list of dicts with path, url, language.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Resolve branch → tree SHA
            commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            commits_resp = await client.get(
                commits_url, params={"sha": branch, "per_page": 1}
            )

            if commits_resp.status_code != 200:
                for fb in ["main", "master"]:
                    if fb != branch:
                        commits_resp = await client.get(
                            commits_url, params={"sha": fb, "per_page": 1}
                        )
                        if commits_resp.status_code == 200:
                            branch = fb
                            break

            if commits_resp.status_code != 200:
                self.logger.error(f"GitHub API error resolving branch: {commits_resp.status_code}")
                return []

            commits_data = commits_resp.json()
            if not commits_data:
                return []

            tree_sha = commits_data[0]["commit"]["tree"]["sha"]

            # Get recursive tree
            tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1"
            tree_resp = await client.get(tree_url)
            if tree_resp.status_code != 200:
                return []

            tree_data = tree_resp.json()
            all_files = [
                item for item in tree_data.get("tree", [])
                if item["type"] == "blob"
            ]

            # Special filenames (no extension) that should be included
            SPECIAL_FILENAMES = {
                'Dockerfile': 'dockerfile',
                'Makefile': 'makefile',
                'Jenkinsfile': 'groovy',
                'Vagrantfile': 'ruby',
                'Procfile': 'procfile',
                'Gemfile': 'ruby',
                'Rakefile': 'ruby',
                'docker-compose.yml': 'yaml',
                'docker-compose.yaml': 'yaml',
                '.gitignore': 'gitignore',
                '.dockerignore': 'dockerignore',
                '.eslintrc': 'json',
                '.prettierrc': 'json',
                'requirements.txt': 'pip',
                'Pipfile': 'toml',
                'pyproject.toml': 'toml',
                'package.json': 'json',
                'tsconfig.json': 'json',
            }

            # Filter to relevant code files
            file_list = []
            for item in all_files:
                path = item["path"]
                parts = path.split('/')
                if any(d in self.SKIP_DIRS for d in parts):
                    continue
                filename = parts[-1]
                ext = ''
                if '.' in filename:
                    ext = '.' + filename.rsplit('.', 1)[-1]

                # Match by extension OR by special filename
                if ext in self.CODE_EXTENSIONS:
                    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
                    language = self.EXT_TO_LANG.get(ext, "")
                    file_list.append({
                        "path": path,
                        "url": raw_url,
                        "language": language,
                    })
                elif filename in SPECIAL_FILENAMES:
                    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
                    language = SPECIAL_FILENAMES[filename]
                    file_list.append({
                        "path": path,
                        "url": raw_url,
                        "language": language,
                    })

            self.logger.info(
                f"Found {len(file_list)} code files in {owner}/{repo} "
                f"(from {len(all_files)} total)"
            )
            return file_list

    async def _resolve_github_url(self, url: str) -> str | None:
        """
        Resolve GitHub URLs to actual code content.
        - Blob URLs → fetch raw file content
        - Repo/tree URLs → returns sentinel "__REPOSITORY_URL__" to signal
          that _async_analyze_component should redirect to the repo pipeline.
        Returns raw content for single files, sentinel for repos, None for non-GitHub.
        """
        url_type, owner, repo_name, extra = self._detect_github_url_type(url)

        if url_type == "single_file":
            return await self._fetch_single_github_file(owner, repo_name, extra)

        if url_type == "repository":
            return "__REPOSITORY_URL__"

        return None

    async def _redirect_to_repo_pipeline(self, db, component, tenant_id: int) -> None:
        """
        When a user submits a GitHub repository URL as a single code component,
        redirect to the proper per-file repository analysis pipeline instead
        of concatenating files (context stuffing).

        Creates a Repository record, builds the file list, and dispatches
        repo_analysis_task via Celery.
        """
        url_type, owner, repo_name, branch = self._detect_github_url_type(component.location)
        if url_type != "repository":
            return

        repo_url = f"https://github.com/{owner}/{repo_name}"
        display_name = f"{owner}/{repo_name}"

        self.logger.info(
            f"Redirecting component {component.id} to repo pipeline: "
            f"{display_name} (branch: {branch})"
        )

        # Check if repo already exists for this tenant
        existing_repo = crud.repository.get_by_url(
            db=db, url=repo_url, tenant_id=tenant_id
        )

        if existing_repo:
            repo = existing_repo
            self.logger.info(f"Reusing existing repository {repo.id} for {display_name}")
        else:
            # Create Repository record
            from app.schemas.repository import RepositoryCreate
            repo_in = RepositoryCreate(
                name=display_name,
                url=repo_url,
                default_branch=branch,
                description=f"Auto-created from code component {component.id}",
            )
            repo = crud.repository.create_with_owner(
                db=db, obj_in=repo_in, owner_id=component.owner_id, tenant_id=tenant_id
            )
            self.logger.info(f"Created repository {repo.id} for {display_name}")

        # Link component to repository
        crud.code_component.update(
            db, db_obj=component, obj_in={
                "repository_id": repo.id,
                "analysis_status": "redirected",
                "summary": f"Redirected to repository analysis (repo_id={repo.id}). "
                           f"Per-file analysis provides better results than single-prompt concatenation.",
            }
        )
        db.commit()

        # Build file list from GitHub API
        file_list = await self._get_repo_file_list(owner, repo_name, branch)
        if not file_list:
            crud.code_component.update(
                db, db_obj=component, obj_in={
                    "analysis_status": "failed",
                    "summary": f"Failed to fetch file list from {display_name}",
                }
            )
            db.commit()
            return

        # Dispatch repo_analysis_task via Celery
        from app.tasks.code_analysis_tasks import repo_analysis_task
        task = repo_analysis_task.delay(repo.id, tenant_id, file_list)

        self.logger.info(
            f"Dispatched repo_analysis_task for {display_name}: "
            f"{len(file_list)} files, celery_task={task.id}"
        )

    def analyze_component_in_background(self, component_id: int, tenant_id: int = None) -> None:
        """
        This is the main entry point that will be called as a background task.
        It's a synchronous function that sets up and runs the main async logic.

        SPRINT 2 Phase 6: Added tenant_id for multi-tenancy isolation.

        Args:
            component_id: ID of the code component to analyze
            tenant_id: Tenant ID for isolation (SPRINT 2)
        """
        self.logger.info(f"Setting up async analysis for component_id: {component_id}, tenant_id: {tenant_id}")
        asyncio.run(self._async_analyze_component(component_id, tenant_id))

    async def _async_analyze_component(self, component_id: int, tenant_id: int = None) -> None:
        """
        This is the core asynchronous logic for analyzing a single code component.
        It handles the entire lifecycle of fetching, analyzing, and storing results.

        SPRINT 2 Phase 6: Added tenant_id for multi-tenancy isolation.

        Args:
            component_id: ID of the code component to analyze
            tenant_id: Tenant ID for isolation (SPRINT 2)
        """
        db: Session = SessionLocal()
        component = None
        try:
            # Retrieve the component from the database
            # SPRINT 2 Phase 6: Filter by tenant_id for isolation
            component = crud.code_component.get(db=db, id=component_id, tenant_id=tenant_id)
            if not component:
                self.logger.error(
                    f"CodeAnalysisService: Component with ID {component_id} not found "
                    f"in tenant {tenant_id}"
                )
                return

            # 1. Update status to 'processing' and record start time
            from datetime import datetime as dt
            analysis_start = dt.now()
            crud.code_component.update(db, db_obj=component, obj_in={
                "analysis_status": "processing",
                "analysis_started_at": analysis_start,
            })
            db.commit()

            # 2. Fetch the raw code content
            self.logger.info(f"Fetching code from URL: {component.location}")
            github_content = await self._resolve_github_url(component.location)

            if github_content == "__REPOSITORY_URL__":
                # Repository URL detected — redirect to proper per-file repo pipeline
                await self._redirect_to_repo_pipeline(
                    db=db, component=component, tenant_id=tenant_id
                )
                return

            if github_content is not None:
                code_content = github_content
                self.logger.info(f"Fetched {len(code_content)} chars from GitHub")
            else:
                # Non-GitHub URL: fetch directly
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(component.location)
                    response.raise_for_status()
                    code_content = response.text

            # 3. Try to get cached analysis first (80% cost savings!)
            self.logger.info(f"Checking cache for component {component_id}...")
            cached_result = cache_service.get_cached_analysis(
                content=code_content,
                analysis_type="code_analysis"
            )

            if cached_result:
                # Cache HIT - use cached result (no AI cost!)
                self.logger.info(f"✅ Using cached analysis for component {component_id}")
                analysis_result = cached_result
            else:
                # ✅ BILLING CHECK: Check if tenant can afford this analysis BEFORE calling Gemini
                self.logger.info(f"💰 Checking billing: tenant {tenant_id} for code component {component_id}")
                try:
                    billing_check = billing_enforcement_service.check_can_afford_analysis(
                        db=db,
                        tenant_id=tenant_id,
                        estimated_cost_inr=5.0  # Estimated cost for code analysis
                    )

                    if not billing_check["can_proceed"]:
                        error_msg = f"Insufficient funds: {billing_check['reason']}"
                        self.logger.error(f"❌ {error_msg}")
                        crud.code_component.update(
                            db, db_obj=component,
                            obj_in={"analysis_status": "failed", "analysis_error": error_msg}
                        )
                        db.commit()
                        return

                    self.logger.info(f"✅ Billing check passed for tenant {tenant_id}")

                except (InsufficientBalanceException, MonthlyLimitExceededException) as e:
                    error_msg = str(e)
                    self.logger.error(f"❌ Billing enforcement failed: {error_msg}")
                    crud.code_component.update(
                        db, db_obj=component,
                        obj_in={"analysis_status": "failed", "analysis_error": error_msg}
                    )
                    db.commit()
                    return

                # Cache MISS - call Gemini API
                self.logger.info(f"❌ Cache miss. Sending code for component {component_id} to Gemini for analysis...")
                analysis_result = await call_gemini_for_code_analysis(code_content)

                # Store result in cache for future use
                cache_service.set_cached_analysis(
                    content=code_content,
                    analysis_type="code_analysis",
                    result=analysis_result,
                    ttl_seconds=2592000  # 30 days
                )
                self.logger.info(f"💾 Cached analysis result for component {component_id}")

            # 4. Calculate cost from token usage (including thinking tokens!)
            token_usage = analysis_result.pop("_token_usage", {})
            input_tokens = token_usage.get("input_tokens", 0)
            output_tokens = token_usage.get("output_tokens", 0)
            thinking_tokens = token_usage.get("thinking_tokens", 0)

            cost_data = {}
            total_cost_inr = 0.0
            if input_tokens or output_tokens or thinking_tokens:
                cost_data = cost_service.calculate_cost_from_actual_tokens(
                    input_tokens, output_tokens, thinking_tokens=thinking_tokens
                )
                total_cost_inr = float(cost_data.get("cost_inr", 0))
                self.logger.info(
                    f"💰 Code analysis cost: ₹{total_cost_inr:.4f} "
                    f"({input_tokens} in + {output_tokens} out + {thinking_tokens} thinking tokens)"
                )

                # Deduct cost from tenant billing
                try:
                    billing_enforcement_service.deduct_cost(
                        db=db,
                        tenant_id=tenant_id,
                        cost_inr=total_cost_inr,
                        description=f"Code analysis: {component.name}"
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to deduct cost: {e}")

                # Log usage for analytics (combine output + thinking for total output)
                try:
                    crud.usage_log.log_usage(
                        db=db,
                        tenant_id=tenant_id,
                        user_id=component.owner_id,
                        feature_type="code_analysis",
                        operation="code_analysis",
                        model_used="gemini-2.5-flash",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens + thinking_tokens,
                        cost_usd=float(cost_data.get("cost_usd", 0)),
                        cost_inr=total_cost_inr,
                        extra_data={"component_id": component_id, "component_name": component.name, "thinking_tokens": thinking_tokens}
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to log usage: {e}")

            # 5. Prepare the data and update the component in the database
            cost_breakdown = {
                "code_analysis": {
                    "cost_inr": total_cost_inr,
                    "cost_usd": float(cost_data.get("cost_usd", 0)) if cost_data else 0,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "thinking_tokens": thinking_tokens,
                }
            }
            update_data = {
                "summary": analysis_result.get("summary"),
                "structured_analysis": analysis_result.get("structured_analysis"),
                "analysis_status": "completed",
                "ai_cost_inr": total_cost_inr,
                "token_count_input": input_tokens,
                "token_count_output": output_tokens,
                "cost_breakdown": cost_breakdown,
                "analysis_completed_at": dt.now(),
            }
            crud.code_component.update(db, db_obj=component, obj_in=update_data)
            self.logger.info(f"Successfully completed and stored analysis for component_id: {component.id}")

            # 6. Extract ontology concepts from analysis (no additional AI calls)
            try:
                self._extract_ontology_from_analysis(
                    db=db,
                    structured_analysis=analysis_result.get("structured_analysis", {}),
                    component_name=component.name,
                    tenant_id=tenant_id,
                )
            except Exception as e:
                self.logger.warning(f"Ontology extraction failed (non-fatal): {e}")

        except httpx.RequestError as e:
            self.logger.error(f"HTTP Error fetching code for component {component_id}: {e}")
            if component:
                try:
                    db.rollback()
                    crud.code_component.update(db, db_obj=component, obj_in={"analysis_status": "failed"})
                except Exception as update_err:
                    self.logger.warning(f"Failed to mark component as failed: {update_err}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during analysis for component {component_id}: {e}", exc_info=True)
            if component:
                try:
                    db.rollback()
                    crud.code_component.update(db, db_obj=component, obj_in={"analysis_status": "failed", "summary": f"AI analysis failed: {str(e)[:500]}"})
                except Exception as update_err:
                    self.logger.warning(f"Failed to mark component as failed: {update_err}")
        finally:
            # 5. Critically important: ensure the database session is always closed
            try:
                if db.is_active:
                    db.commit()
            except Exception:
                db.rollback()
            db.close()

    # Map code component types to ontology concept types
    _TYPE_MAPPING = {
        "Class": "Entity",
        "Interface": "Entity",
        "Service": "Service",
        "Model": "Entity",
        "Function": "Process",
        "AsyncFunction": "Process",
        "Method": "Process",
        "Component": "Entity",
        "Route": "Process",
        "Hook": "Process",
        "Enum": "Attribute",
        "Type": "Attribute",
        "Constant": "Attribute",
        "Variable": "Attribute",
        "Module": "Entity",
    }

    def _extract_ontology_from_analysis(
        self, db, structured_analysis: dict, component_name: str, tenant_id: int
    ) -> None:
        """
        Extract ontology concepts AND relationships from code analysis results.
        Creates concepts with source_type="code" — no additional AI calls.
        Also creates relationships from data_model_relationships, dependencies,
        and API contracts found in the structured analysis.
        """
        if not structured_analysis or not tenant_id:
            return

        components = structured_analysis.get("components", [])
        key_concepts = (
            structured_analysis
            .get("patterns_and_architecture", {})
            .get("key_concepts", [])
        )
        created_count = 0
        relationship_count = 0
        concept_map = {}  # name -> OntologyConcept object (for relationship linking)

        # Extract significant code components as concepts
        # Only extract Classes, Services, Models, Interfaces, Components (skip functions/variables)
        significant_types = {"Class", "Interface", "Service", "Model", "Component", "Module"}
        for comp in components:
            comp_type = comp.get("type", "")
            if comp_type not in significant_types:
                continue

            name = comp.get("name", "").strip()
            if not name or len(name) < 2:
                continue

            concept_type = self._TYPE_MAPPING.get(comp_type, "Entity")
            description = comp.get("purpose", "") or comp.get("details", "")

            concept = crud.ontology_concept.get_or_create(
                db,
                name=name,
                concept_type=concept_type,
                tenant_id=tenant_id,
                description=description[:500] if description else None,
                confidence_score=0.75,
                source_type="code",
            )
            concept_map[name] = concept
            created_count += 1

        # Extract key architectural concepts
        for concept_name in key_concepts:
            if not concept_name or len(concept_name.strip()) < 2:
                continue
            concept = crud.ontology_concept.get_or_create(
                db,
                name=concept_name.strip(),
                concept_type="Process",
                tenant_id=tenant_id,
                description=f"Architectural concept from code: {component_name}",
                confidence_score=0.65,
                source_type="code",
            )
            concept_map[concept_name.strip()] = concept
            created_count += 1

        # ── Phase 2: Extract RELATIONSHIPS from structured analysis ──

        # 2a. data_model_relationships → "has_many", "belongs_to", etc.
        data_rels = structured_analysis.get("data_model_relationships", [])
        for rel in data_rels:
            source_name = rel.get("source_entity", "").strip()
            target_name = rel.get("target_entity", "").strip()
            rel_type = rel.get("relationship_type", "related_to").strip()
            if not source_name or not target_name:
                continue

            # Ensure both concepts exist
            source_concept = concept_map.get(source_name)
            if not source_concept:
                source_concept = crud.ontology_concept.get_or_create(
                    db, name=source_name, concept_type="Entity",
                    tenant_id=tenant_id, source_type="code",
                    description=rel.get("description", "")[:500] if rel.get("description") else None,
                    confidence_score=0.7,
                )
                concept_map[source_name] = source_concept

            target_concept = concept_map.get(target_name)
            if not target_concept:
                target_concept = crud.ontology_concept.get_or_create(
                    db, name=target_name, concept_type="Entity",
                    tenant_id=tenant_id, source_type="code",
                    description=None, confidence_score=0.7,
                )
                concept_map[target_name] = target_concept

            if source_concept.id != target_concept.id:
                crud.ontology_relationship.create_if_not_exists(
                    db, source_concept_id=source_concept.id,
                    target_concept_id=target_concept.id,
                    relationship_type=rel_type, tenant_id=tenant_id,
                    description=rel.get("description", ""),
                    confidence_score=0.8,
                )
                relationship_count += 1

        # 2b. API contracts → create "exposes_endpoint" relationships
        api_contracts = structured_analysis.get("api_contracts", [])
        if api_contracts:
            # Create a concept for the file/module itself
            file_short = component_name.rsplit("/", 1)[-1] if "/" in component_name else component_name
            file_concept = concept_map.get(file_short)
            if not file_concept:
                file_concept = crud.ontology_concept.get_or_create(
                    db, name=file_short, concept_type="Service",
                    tenant_id=tenant_id, source_type="code",
                    description=f"API module: {component_name}",
                    confidence_score=0.7,
                )
                concept_map[file_short] = file_concept

            for api in api_contracts:
                method = api.get("method", "")
                path = api.get("path", "")
                if not path:
                    continue
                endpoint_name = f"{method} {path}" if method else path
                endpoint_concept = crud.ontology_concept.get_or_create(
                    db, name=endpoint_name, concept_type="Process",
                    tenant_id=tenant_id, source_type="code",
                    description=api.get("description", "")[:500] if api.get("description") else None,
                    confidence_score=0.8,
                )
                if file_concept.id != endpoint_concept.id:
                    crud.ontology_relationship.create_if_not_exists(
                        db, source_concept_id=file_concept.id,
                        target_concept_id=endpoint_concept.id,
                        relationship_type="exposes_endpoint", tenant_id=tenant_id,
                        confidence_score=0.85,
                    )
                    relationship_count += 1

        # 2c. Component-level dependencies within the same file
        # If file has multiple significant components, create "contains" relationships
        if len(concept_map) >= 2 and api_contracts:
            for comp in components:
                comp_type = comp.get("type", "")
                comp_name = comp.get("name", "").strip()
                if comp_type in significant_types and comp_name in concept_map:
                    file_short = component_name.rsplit("/", 1)[-1] if "/" in component_name else component_name
                    if file_short in concept_map and comp_name != file_short:
                        fc = concept_map[file_short]
                        cc = concept_map[comp_name]
                        if fc.id != cc.id:
                            crud.ontology_relationship.create_if_not_exists(
                                db, source_concept_id=fc.id,
                                target_concept_id=cc.id,
                                relationship_type="contains", tenant_id=tenant_id,
                                confidence_score=0.75,
                            )
                            relationship_count += 1

        if created_count > 0 or relationship_count > 0:
            self.logger.info(
                f"📊 Extracted {created_count} concepts + {relationship_count} relationships "
                f"from code analysis of {component_name}"
            )


# Create a singleton instance for easy importing elsewhere in the app
code_analysis_service = CodeAnalysisService()