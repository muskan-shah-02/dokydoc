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
                # Resolve initiative_id: CodeComponent → Repository → InitiativeAsset
                _initiative_id = self._resolve_initiative_for_component(
                    db, repository_id=component.repository_id, tenant_id=tenant_id
                )
                self._extract_ontology_from_analysis(
                    db=db,
                    structured_analysis=analysis_result.get("structured_analysis", {}),
                    component_name=component.name,
                    tenant_id=tenant_id,
                    source_component_id=component.id,
                    initiative_id=_initiative_id,
                )
            except Exception as e:
                self.logger.warning(f"Ontology extraction failed (non-fatal): {e}")

            # 7. Save graph version snapshot for fast rendering + versioning
            try:
                self._save_graph_version(
                    db=db,
                    source_type="component",
                    source_id=component.id,
                    tenant_id=tenant_id,
                )
            except Exception as e:
                self.logger.warning(f"Graph version save failed (non-fatal): {e}")

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
        "Middleware": "Process",
    }

    # File types that focus on business logic, API contracts, security, call chains
    def _resolve_initiative_for_component(
        self, db, *, repository_id: int = None, tenant_id: int
    ):
        """Resolve initiative_id for a code component via Repository → InitiativeAsset."""
        if not repository_id:
            return None
        try:
            from app.models.initiative_asset import InitiativeAsset
            asset = db.query(InitiativeAsset).filter(
                InitiativeAsset.tenant_id == tenant_id,
                InitiativeAsset.asset_type == "REPOSITORY",
                InitiativeAsset.asset_id == repository_id,
                InitiativeAsset.is_active == True,
            ).first()
            return asset.initiative_id if asset else None
        except Exception:
            return None

    _LOGIC_FILE_TYPES = {"Service", "Controller", "Middleware"}
    # File types that focus on data entities, field relationships, constraints
    _DATA_FILE_TYPES = {"Model", "Migration"}
    # File types that focus on UI props, state, events
    _UI_FILE_TYPES = {"Component"}
    # File types that focus on test coverage and implicit rules
    _TEST_FILE_TYPES = {"Test"}
    # File types that focus on settings and feature flags
    _CONFIG_FILE_TYPES = {"Config"}

    def _extract_ontology_from_analysis(
        self, db, structured_analysis: dict, component_name: str, tenant_id: int,
        source_component_id: int = None,
        initiative_id: int = None,
    ) -> None:
        """
        Extract ontology concepts AND relationships from code analysis results.
        Uses file-type-specific strategies to build rich, connected knowledge graphs.
        Creates concepts with source_type="code" — no additional AI calls needed.
        """
        if not structured_analysis or not tenant_id:
            return

        created_count = 0
        relationship_count = 0
        concept_map = {}  # name (lowered) -> OntologyConcept for dedup + relationship linking

        # Helper: get-or-create a concept and track it in concept_map
        def _ensure_concept(name: str, concept_type: str, description: str = None,
                            confidence: float = 0.75) -> "OntologyConcept | None":
            nonlocal created_count
            name = (name or "").strip()
            if not name or len(name) < 2:
                return None
            key = name.lower()
            if key in concept_map:
                return concept_map[key]
            concept = crud.ontology_concept.get_or_create(
                db, name=name, concept_type=concept_type,
                tenant_id=tenant_id, source_type="code",
                description=description[:500] if description else None,
                confidence_score=confidence,
                source_component_id=source_component_id,
                initiative_id=initiative_id,
            )
            concept_map[key] = concept
            created_count += 1
            return concept

        # Helper: create a relationship between two concepts
        def _ensure_rel(source_name: str, target_name: str, rel_type: str,
                        description: str = None, confidence: float = 0.8) -> bool:
            nonlocal relationship_count
            src = concept_map.get((source_name or "").strip().lower())
            tgt = concept_map.get((target_name or "").strip().lower())
            if not src or not tgt or src.id == tgt.id:
                return False
            crud.ontology_relationship.create_if_not_exists(
                db, source_concept_id=src.id, target_concept_id=tgt.id,
                relationship_type=rel_type, tenant_id=tenant_id,
                description=description[:500] if description else None,
                confidence_score=confidence,
            )
            relationship_count += 1
            return True

        # Detect file type
        lang_info = structured_analysis.get("language_info", {})
        file_type = lang_info.get("file_type", "Utility")

        # ═══════════════════════════════════════════════════════════════
        # COMMON EXTRACTION — runs for ALL file types
        # ═══════════════════════════════════════════════════════════════

        # 1. Root file/module concept
        file_short = component_name.rsplit("/", 1)[-1] if "/" in component_name else component_name
        summary = structured_analysis.get("summary", "") if isinstance(structured_analysis.get("summary"), str) else ""
        file_concept = _ensure_concept(
            file_short, "Service" if file_type in self._LOGIC_FILE_TYPES else "Entity",
            description=summary or f"Module: {component_name}",
            confidence=0.9,
        )

        # 2. Extract ALL components (no significant_types filter — every function matters)
        components = structured_analysis.get("components", [])
        for comp in components:
            comp_type = comp.get("type", "")
            name = (comp.get("name", "") or "").strip()
            if not name or len(name) < 2:
                continue
            concept_type = self._TYPE_MAPPING.get(comp_type, "Process")
            description = comp.get("purpose", "") or comp.get("details", "")
            _ensure_concept(name, concept_type, description=description)
            # Every component → defined_in → file (no orphans)
            _ensure_rel(name, file_short, "defined_in", confidence=0.9)

        # 3. Key architectural concepts
        key_concepts = (
            structured_analysis.get("patterns_and_architecture", {})
            .get("key_concepts", [])
        )
        for concept_name in key_concepts:
            if concept_name and len(concept_name.strip()) >= 2:
                _ensure_concept(concept_name.strip(), "Process",
                                description=f"Architectural concept: {concept_name}")

        # 4. Data model relationships → always extracted
        data_rels = structured_analysis.get("data_model_relationships", [])
        for rel in data_rels:
            src_name = (rel.get("source_entity", "") or "").strip()
            tgt_name = (rel.get("target_entity", "") or "").strip()
            rel_type = (rel.get("relationship_type", "related_to") or "related_to").strip()
            if not src_name or not tgt_name:
                continue
            _ensure_concept(src_name, "Entity", description=rel.get("description"))
            _ensure_concept(tgt_name, "Entity")
            _ensure_rel(src_name, tgt_name, rel_type,
                        description=rel.get("description"), confidence=0.85)

        # 5. Component interactions → calls, inherits, delegates_to, etc.
        interactions = structured_analysis.get("component_interactions", [])
        for ix in interactions:
            src = (ix.get("source", "") or "").strip()
            tgt = (ix.get("target", "") or "").strip()
            ix_type = (ix.get("interaction_type", "calls") or "calls").strip()
            if not src or not tgt:
                continue
            _ensure_concept(src, "Process", description=ix.get("description"))
            _ensure_concept(tgt, "Process", description=ix.get("description"))
            _ensure_rel(src, tgt, ix_type,
                        description=ix.get("data_passed", ix.get("description")),
                        confidence=0.8)

        # 6. Data flows → transforms, flows_to edges
        data_flows = structured_analysis.get("data_flows", [])
        for flow in data_flows:
            flow_name = (flow.get("name", "") or "").strip()
            source = (flow.get("source", "") or "").strip()
            dest = (flow.get("destination", "") or "").strip()
            if not source or not dest:
                continue
            _ensure_concept(source, "Attribute",
                            description=f"Data source: {flow.get('data_type', '')}")
            _ensure_concept(dest, "Attribute",
                            description=f"Data destination")
            desc = flow.get("transformations", flow_name)
            _ensure_rel(source, dest, "flows_to", description=desc, confidence=0.75)

        # ═══════════════════════════════════════════════════════════════
        # FILE-TYPE-SPECIFIC EXTRACTION
        # ═══════════════════════════════════════════════════════════════

        if file_type in self._LOGIC_FILE_TYPES:
            self._extract_logic_file(structured_analysis, _ensure_concept, _ensure_rel, file_short)
        elif file_type in self._DATA_FILE_TYPES:
            self._extract_data_file(structured_analysis, _ensure_concept, _ensure_rel, file_short)
        elif file_type in self._UI_FILE_TYPES:
            self._extract_ui_file(structured_analysis, _ensure_concept, _ensure_rel, file_short)
        elif file_type in self._TEST_FILE_TYPES:
            self._extract_test_file(structured_analysis, _ensure_concept, _ensure_rel, file_short)
        elif file_type in self._CONFIG_FILE_TYPES:
            self._extract_config_file(structured_analysis, _ensure_concept, _ensure_rel, file_short)
        # Utility/Generic — common extraction above is sufficient

        if created_count > 0 or relationship_count > 0:
            self.logger.info(
                f"[{file_type}] Extracted {created_count} concepts + {relationship_count} "
                f"relationships from {component_name}"
            )

    # ── File-type-specific extractors ──────────────────────────────────

    @staticmethod
    def _extract_logic_file(analysis: dict, ensure_concept, ensure_rel, file_short: str):
        """Service/Controller/Middleware — business rules, API contracts, security."""
        # Business rules → Rule concepts + enforces edges
        for rule in analysis.get("business_rules", []):
            rule_desc = (rule.get("description", "") or "").strip()
            rule_loc = (rule.get("code_location", "") or "").strip()
            rule_type = rule.get("rule_type", "constraint")
            if not rule_desc:
                continue
            rule_name = rule.get("rule_id", "") or rule_desc[:60]
            ensure_concept(rule_name, "Rule",
                           description=f"[{rule_type}] {rule_desc}")
            ensure_rel(rule_name, file_short, "defined_in", confidence=0.85)
            if rule_loc:
                ensure_rel(rule_loc, rule_name, "enforces",
                           description=rule_desc, confidence=0.85)

        # API contracts → Endpoint concepts + exposes edges
        for api in analysis.get("api_contracts", []):
            method = api.get("method", "")
            path = api.get("path", "")
            if not path:
                continue
            endpoint_name = f"{method} {path}" if method else path
            ensure_concept(endpoint_name, "Process",
                           description=api.get("description"))
            ensure_rel(file_short, endpoint_name, "exposes_endpoint", confidence=0.9)

        # Security patterns → Security concepts + protects edges
        for sec in analysis.get("security_patterns", []):
            sec_desc = (sec.get("description", "") or "").strip()
            sec_type = sec.get("pattern_type", "security")
            if not sec_desc:
                continue
            sec_name = f"{sec_type}: {sec_desc[:50]}"
            ensure_concept(sec_name, "Rule",
                           description=f"[Security/{sec_type}] {sec.get('implementation', '')}")
            ensure_rel(sec_name, file_short, "protects", confidence=0.8)

    @staticmethod
    def _extract_data_file(analysis: dict, ensure_concept, ensure_rel, file_short: str):
        """Model/Migration — data entities, field relationships, constraints, validations."""
        # Business rules in models = validation/constraint rules
        for rule in analysis.get("business_rules", []):
            rule_desc = (rule.get("description", "") or "").strip()
            rule_type = rule.get("rule_type", "validation")
            if not rule_desc:
                continue
            rule_name = rule.get("rule_id", "") or rule_desc[:60]
            ensure_concept(rule_name, "Rule",
                           description=f"[{rule_type}] {rule_desc}")
            ensure_rel(rule_name, file_short, "validates", confidence=0.85)

    @staticmethod
    def _extract_ui_file(analysis: dict, ensure_concept, ensure_rel, file_short: str):
        """Component (UI) — props, state, events, user interactions."""
        # Business rules in UI = form validations, conditional rendering
        for rule in analysis.get("business_rules", []):
            rule_desc = (rule.get("description", "") or "").strip()
            if not rule_desc:
                continue
            rule_name = rule.get("rule_id", "") or rule_desc[:60]
            ensure_concept(rule_name, "Rule",
                           description=f"[UI Rule] {rule_desc}")
            ensure_rel(file_short, rule_name, "enforces", confidence=0.8)

        # Security patterns in UI = input validation, CSRF tokens
        for sec in analysis.get("security_patterns", []):
            sec_desc = (sec.get("description", "") or "").strip()
            if not sec_desc:
                continue
            sec_name = f"UI: {sec_desc[:50]}"
            ensure_concept(sec_name, "Rule",
                           description=sec.get("implementation", sec_desc))
            ensure_rel(sec_name, file_short, "protects", confidence=0.75)

    @staticmethod
    def _extract_test_file(analysis: dict, ensure_concept, ensure_rel, file_short: str):
        """Test — test cases as implicit business rules, mocks as system boundaries."""
        # Business rules in tests = assertions about expected behavior
        for rule in analysis.get("business_rules", []):
            rule_desc = (rule.get("description", "") or "").strip()
            if not rule_desc:
                continue
            rule_name = rule.get("rule_id", "") or f"Test: {rule_desc[:50]}"
            ensure_concept(rule_name, "Rule",
                           description=f"[Test Assertion] {rule_desc}")
            ensure_rel(file_short, rule_name, "tests", confidence=0.8)

    @staticmethod
    def _extract_config_file(analysis: dict, ensure_concept, ensure_rel, file_short: str):
        """Config — settings, feature flags, connections."""
        # Business rules in config = threshold/limit configs
        for rule in analysis.get("business_rules", []):
            rule_desc = (rule.get("description", "") or "").strip()
            if not rule_desc:
                continue
            rule_name = rule.get("rule_id", "") or rule_desc[:60]
            ensure_concept(rule_name, "Rule",
                           description=f"[Config] {rule_desc}")
            ensure_rel(file_short, rule_name, "configures", confidence=0.85)

    def _save_graph_version(
        self, db, *, source_type: str, source_id: int, tenant_id: int
    ) -> None:
        """
        Build a graph snapshot from the ontology tables and save it as a
        KnowledgeGraphVersion for fast rendering and version tracking.
        """
        # Fetch all concepts for this source
        if source_type == "component":
            concepts = db.query(crud.ontology_concept.model).filter(
                crud.ontology_concept.model.tenant_id == tenant_id,
                crud.ontology_concept.model.source_component_id == source_id,
                crud.ontology_concept.model.is_active == True,
            ).all()
        else:
            concepts = db.query(crud.ontology_concept.model).filter(
                crud.ontology_concept.model.tenant_id == tenant_id,
                crud.ontology_concept.model.source_document_id == source_id,
                crud.ontology_concept.model.is_active == True,
            ).all()

        if not concepts:
            return

        concept_ids = {c.id for c in concepts}

        # Fetch relationships between these concepts
        relationships = db.query(crud.ontology_relationship.model).filter(
            crud.ontology_relationship.model.tenant_id == tenant_id,
            crud.ontology_relationship.model.source_concept_id.in_(concept_ids),
            crud.ontology_relationship.model.target_concept_id.in_(concept_ids),
        ).all()

        # Build graph JSON
        nodes = [
            {
                "id": c.id,
                "name": c.name,
                "type": c.concept_type,
                "description": c.description or "",
                "confidence": c.confidence_score,
                "source_type": c.source_type,
            }
            for c in concepts
        ]
        edges = [
            {
                "id": r.id,
                "source": r.source_concept_id,
                "target": r.target_concept_id,
                "type": r.relationship_type,
                "description": r.description or "",
                "confidence": r.confidence_score,
            }
            for r in relationships
        ]
        graph_data = {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "source_type": source_type,
                "source_id": source_id,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            },
        }

        crud.knowledge_graph_version.save_version(
            db,
            source_type=source_type,
            source_id=source_id,
            tenant_id=tenant_id,
            graph_data=graph_data,
        )
        self.logger.info(
            f"Saved graph version: {source_type}:{source_id} "
            f"({len(nodes)} nodes, {len(edges)} edges)"
        )


# Create a singleton instance for easy importing elsewhere in the app
code_analysis_service = CodeAnalysisService()