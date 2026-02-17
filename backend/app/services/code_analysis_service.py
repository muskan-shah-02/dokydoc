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

    async def _resolve_github_url(self, url: str) -> str | None:
        """
        Resolve GitHub URLs to actual code content.
        - Blob URLs → fetch raw file content from raw.githubusercontent.com
        - Repo/tree URLs → use GitHub API to list files, fetch key source files
        Returns concatenated code content, or None if not a GitHub URL.
        """
        # Check for blob (single file) URL first
        blob_match = re.match(
            r'https?://github\.com/([^/]+)/([^/]+)/blob/(.+)', url
        )
        if blob_match:
            owner, repo, blob_path = blob_match.groups()
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{blob_path}"
            self.logger.info(f"Fetching single file from GitHub: {raw_url}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(raw_url)
                resp.raise_for_status()
                return resp.text

        # Check for repo/tree URL
        tree_match = re.match(
            r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/tree/(.+?))?(?:\?.*)?$',
            url
        )
        if not tree_match:
            return None

        owner, repo, ref_path = tree_match.groups()
        branch = ref_path or "main"

        self.logger.info(f"Fetching GitHub repo: {owner}/{repo} (branch: {branch})")

        # File extensions to include
        code_extensions = {
            '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs',
            '.rb', '.php', '.cs', '.cpp', '.c', '.h', '.swift', '.kt',
            '.vue', '.svelte',
        }
        # Config/doc files to prioritize
        priority_files = {
            'README.md', 'readme.md', 'package.json', 'requirements.txt',
            'setup.py', 'pyproject.toml', 'Cargo.toml', 'go.mod',
            'docker-compose.yml', 'Dockerfile', 'main.py', 'app.py',
            'index.ts', 'index.js', 'main.go', 'manage.py',
        }
        # Directories to skip
        skip_dirs = {
            'node_modules', '.git', '__pycache__', '.next', 'dist', 'build',
            '.venv', 'venv', 'env', '.env', 'vendor', '.idea', '.vscode',
            'coverage', '.pytest_cache', '.mypy_cache', '.tox',
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: Resolve branch → tree SHA via commits API
            # (handles branch names with slashes safely as a query param)
            commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            commits_resp = await client.get(
                commits_url, params={"sha": branch, "per_page": 1}
            )

            if commits_resp.status_code != 200 and not ref_path:
                # Fallback: try main/master if no explicit branch
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
                return None

            commits_data = commits_resp.json()
            if not commits_data:
                self.logger.error("No commits found on branch")
                return None

            tree_sha = commits_data[0]["commit"]["tree"]["sha"]

            # Step 2: Get the full recursive tree
            tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1"
            tree_resp = await client.get(tree_url)

            if tree_resp.status_code != 200:
                self.logger.error(f"GitHub API error fetching tree: {tree_resp.status_code}")
                return None

            tree_data = tree_resp.json()
            all_files = [
                item for item in tree_data.get("tree", [])
                if item["type"] == "blob"
            ]

            # Step 3: Filter to relevant code files
            relevant_files = []
            for item in all_files:
                path = item["path"]
                parts = path.split('/')

                if any(d in skip_dirs for d in parts):
                    continue

                filename = parts[-1]
                ext = ''
                if '.' in filename:
                    ext = '.' + filename.rsplit('.', 1)[-1]

                if filename in priority_files or ext in code_extensions:
                    relevant_files.append(path)

            # Step 4: Sort by priority (config first, then by depth)
            def file_priority(p):
                fname = p.split('/')[-1]
                depth = p.count('/')
                return (0 if fname in priority_files else 1, depth, p)

            relevant_files.sort(key=file_priority)
            selected_files = relevant_files[:30]

            self.logger.info(
                f"Selected {len(selected_files)}/{len(relevant_files)} files "
                f"from {len(all_files)} total in {owner}/{repo}"
            )

            # Step 5: Fetch raw content in parallel batches
            async def fetch_file(file_path):
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"
                try:
                    file_resp = await client.get(raw_url)
                    if file_resp.status_code == 200:
                        content = file_resp.text
                        if len(content) > 10000:
                            content = content[:10000] + "\n... [TRUNCATED]"
                        return (file_path, content)
                except Exception:
                    pass
                return None

            results = []
            batch_size = 5
            for i in range(0, len(selected_files), batch_size):
                batch = selected_files[i:i + batch_size]
                batch_results = await asyncio.gather(*[fetch_file(f) for f in batch])
                results.extend([r for r in batch_results if r])

            # Build concatenated content (cap at ~100K chars ≈ 25K tokens)
            contents = []
            total_chars = 0
            max_total = 100000
            for file_path, content in results:
                if total_chars >= max_total:
                    break
                contents.append(f"=== FILE: {file_path} ===\n{content}")
                total_chars += len(content)

            if not contents:
                self.logger.error("No files could be fetched from repository")
                return None

            header = (
                f"# Repository: {owner}/{repo}\n"
                f"# Branch: {branch}\n"
                f"# Total files in repo: {len(all_files)}\n"
                f"# Analyzed files: {len(contents)}/{len(relevant_files)} code files\n\n"
            )
            return header + "\n\n".join(contents)

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

            # 1. Update status to 'processing' to give feedback to the UI
            crud.code_component.update(db, db_obj=component, obj_in={"analysis_status": "processing"})
            db.commit()

            # 2. Fetch the raw code content
            self.logger.info(f"Fetching code from URL: {component.location}")
            github_content = await self._resolve_github_url(component.location)
            if github_content is not None:
                code_content = github_content
                self.logger.info(f"Fetched {len(code_content)} chars from GitHub repository")
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

            # 4. Calculate cost from token usage
            token_usage = analysis_result.pop("_token_usage", {})
            input_tokens = token_usage.get("input_tokens", 0)
            output_tokens = token_usage.get("output_tokens", 0)

            cost_data = {}
            total_cost_inr = 0.0
            if input_tokens or output_tokens:
                cost_data = cost_service.calculate_cost_from_actual_tokens(input_tokens, output_tokens)
                total_cost_inr = float(cost_data.get("cost_inr", 0))
                self.logger.info(
                    f"💰 Code analysis cost: ₹{total_cost_inr:.4f} "
                    f"({input_tokens} in + {output_tokens} out tokens)"
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

                # Log usage for analytics
                try:
                    crud.usage_log.log_usage(
                        db=db,
                        tenant_id=tenant_id,
                        user_id=component.owner_id,
                        feature_type="code_analysis",
                        operation="code_analysis",
                        model_used="gemini-2.5-flash",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_usd=float(cost_data.get("cost_usd", 0)),
                        cost_inr=total_cost_inr,
                        extra_data={"component_id": component_id, "component_name": component.name}
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
            }
            crud.code_component.update(db, db_obj=component, obj_in=update_data)
            self.logger.info(f"Successfully completed and stored analysis for component_id: {component.id}")

        except httpx.RequestError as e:
            self.logger.error(f"HTTP Error fetching code for component {component_id}: {e}")
            if component:
                crud.code_component.update(db, db_obj=component, obj_in={"analysis_status": "failed"})
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during analysis for component {component_id}: {e}", exc_info=True)
            if component:
                crud.code_component.update(db, db_obj=component, obj_in={"analysis_status": "failed", "summary": f"AI analysis failed: {str(e)}"})
        finally:
            # 5. Critically important: ensure the database session is always closed
            if db.is_active:
                db.commit()
            db.close()

# Create a singleton instance for easy importing elsewhere in the app
code_analysis_service = CodeAnalysisService()