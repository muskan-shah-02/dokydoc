"""
Sprint 4 ADHOC Integration Tests

Tests for:
  - ADHOC-07: AnthropicService (Claude API integration)
  - ADHOC-08: ProviderRouter (dual-provider routing)
  - ADHOC-09: Git Webhook endpoint + incremental analysis task
"""

import hmac
import hashlib
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from decimal import Decimal


# ============================================================
# ADHOC-07: AnthropicService Tests
# ============================================================

class TestAnthropicService:
    """Test AnthropicService initialization and behavior."""

    def test_service_unavailable_without_api_key(self):
        """Service should be unavailable when ANTHROPIC_API_KEY is not set."""
        with patch("app.services.ai.anthropic.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = None
            from app.services.ai.anthropic import AnthropicService
            service = AnthropicService()
            assert service.available is False
            assert service.client is None

    def test_service_unavailable_without_package(self):
        """Service should gracefully handle missing anthropic package."""
        with patch("app.services.ai.anthropic.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = "test-key"
            with patch.dict("sys.modules", {"anthropic": None}):
                from app.services.ai.anthropic import AnthropicService
                service = AnthropicService()
                assert service.available is False

    @pytest.mark.asyncio
    async def test_generate_content_raises_when_unavailable(self):
        """generate_content should raise RuntimeError when service is unavailable."""
        with patch("app.services.ai.anthropic.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = None
            from app.services.ai.anthropic import AnthropicService
            service = AnthropicService()
            with pytest.raises(RuntimeError, match="not available"):
                await service.generate_content("test prompt")

    @pytest.mark.asyncio
    async def test_generate_content_success(self):
        """generate_content should return text and token counts on success."""
        mock_anthropic = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"summary": "test"}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        with patch("app.services.ai.anthropic.settings") as mock_settings, \
             patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            mock_settings.ANTHROPIC_API_KEY = "test-key"
            mock_settings.ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
            mock_settings.ANTHROPIC_MAX_TOKENS = 4096
            from app.services.ai.anthropic import AnthropicService
            service = AnthropicService()
            result = await service.generate_content("analyze this code")

            assert result["text"] == '{"summary": "test"}'
            assert result["input_tokens"] == 100
            assert result["output_tokens"] == 50

    def test_parse_json_response_valid(self):
        """_parse_json_response should parse valid JSON."""
        with patch("app.services.ai.anthropic.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = None
            from app.services.ai.anthropic import AnthropicService
            service = AnthropicService()
            result = service._parse_json_response('{"key": "value"}', "test")
            assert result == {"key": "value"}

    def test_parse_json_response_with_markdown_fences(self):
        """_parse_json_response should strip markdown code fences."""
        with patch("app.services.ai.anthropic.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = None
            from app.services.ai.anthropic import AnthropicService
            service = AnthropicService()
            result = service._parse_json_response('```json\n{"key": "value"}\n```', "test")
            assert result == {"key": "value"}

    def test_parse_json_response_returns_fallback_on_failure(self):
        """_parse_json_response should return fallback structure on parse failure."""
        with patch("app.services.ai.anthropic.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = None
            from app.services.ai.anthropic import AnthropicService
            service = AnthropicService()
            result = service._parse_json_response("not valid json at all", "test")
            assert "summary" in result
            assert "structured_analysis" in result


# ============================================================
# ADHOC-08: ProviderRouter Tests
# ============================================================

class TestProviderRouter:
    """Test ProviderRouter routing logic and fallback behavior."""

    def test_router_defaults_to_gemini_mode(self):
        """Router should default to gemini mode."""
        with patch("app.services.ai.provider_router.settings") as mock_settings:
            mock_settings.AI_PROVIDER_MODE = "gemini"
            from app.services.ai.provider_router import ProviderRouter
            router = ProviderRouter()
            assert router.mode == "gemini"
            assert router.dual_mode is False

    def test_get_provider_info_gemini_mode(self):
        """get_provider_info should report correct state in gemini mode."""
        with patch("app.services.ai.provider_router.settings") as mock_settings:
            mock_settings.AI_PROVIDER_MODE = "gemini"
            from app.services.ai.provider_router import ProviderRouter
            router = ProviderRouter()
            info = router.get_provider_info()
            assert info["mode"] == "gemini"
            assert info["effective_mode"] == "gemini"
            assert info["document_provider"] == "gemini"

    @pytest.mark.asyncio
    async def test_analyze_code_routes_to_gemini_by_default(self):
        """In gemini mode, code analysis should route to Gemini."""
        mock_gemini = AsyncMock()
        mock_gemini.call_gemini_for_code_analysis.return_value = {"summary": "gemini result"}

        with patch("app.services.ai.provider_router.settings") as mock_settings:
            mock_settings.AI_PROVIDER_MODE = "gemini"
            from app.services.ai.provider_router import ProviderRouter
            router = ProviderRouter()
            router._gemini = mock_gemini

            result = await router.analyze_code("def foo(): pass")
            assert result == {"summary": "gemini result"}
            mock_gemini.call_gemini_for_code_analysis.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_analyze_code_routes_to_claude_in_dual_mode(self):
        """In dual mode with Claude available, code analysis should route to Claude."""
        mock_claude = AsyncMock()
        mock_claude.available = True
        mock_claude.call_claude_for_code_analysis.return_value = {"summary": "claude result"}

        with patch("app.services.ai.provider_router.settings") as mock_settings:
            mock_settings.AI_PROVIDER_MODE = "dual"
            from app.services.ai.provider_router import ProviderRouter
            router = ProviderRouter()
            router._claude = mock_claude

            result = await router.analyze_code("def foo(): pass")
            assert result == {"summary": "claude result"}
            mock_claude.call_claude_for_code_analysis.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dual_mode_falls_back_to_gemini_on_claude_failure(self):
        """When Claude fails in dual mode, should fall back to Gemini."""
        mock_claude = AsyncMock()
        mock_claude.available = True
        mock_claude.call_claude_for_code_analysis.side_effect = Exception("Claude API error")

        mock_gemini = AsyncMock()
        mock_gemini.call_gemini_for_code_analysis.return_value = {"summary": "gemini fallback"}

        with patch("app.services.ai.provider_router.settings") as mock_settings:
            mock_settings.AI_PROVIDER_MODE = "dual"
            from app.services.ai.provider_router import ProviderRouter
            router = ProviderRouter()
            router._claude = mock_claude
            router._gemini = mock_gemini

            result = await router.analyze_code("def foo(): pass")
            assert result == {"summary": "gemini fallback"}
            mock_gemini.call_gemini_for_code_analysis.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_document_analysis_always_uses_gemini(self):
        """Document analysis should always route to Gemini regardless of mode."""
        mock_gemini = AsyncMock()
        mock_gemini.generate_content.return_value = "document result"

        with patch("app.services.ai.provider_router.settings") as mock_settings:
            mock_settings.AI_PROVIDER_MODE = "dual"
            from app.services.ai.provider_router import ProviderRouter
            router = ProviderRouter()
            router._gemini = mock_gemini

            result = await router.generate_content("analyze this document")
            assert result == "document result"
            mock_gemini.generate_content.assert_awaited_once()

    def test_calculate_claude_cost(self):
        """Claude cost calculation should use correct pricing."""
        with patch("app.services.ai.provider_router.settings") as mock_settings:
            mock_settings.AI_PROVIDER_MODE = "gemini"
            mock_settings.ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
            from app.services.ai.provider_router import ProviderRouter
            router = ProviderRouter()

            cost = router.calculate_claude_cost(input_tokens=1_000_000, output_tokens=100_000)
            assert cost["provider"] == "claude"
            assert cost["input_tokens"] == 1_000_000
            assert cost["output_tokens"] == 100_000
            # Input: 1M * $3.00/1M = $3.00, Output: 100K * $15.00/1M = $1.50
            assert abs(cost["cost_usd"] - 4.50) < 0.01
            assert cost["cost_inr"] > 0


# ============================================================
# ADHOC-09: Webhook Tests
# ============================================================

class TestWebhookSignatureVerification:
    """Test GitHub webhook signature verification."""

    def test_valid_github_signature(self):
        """Valid HMAC-SHA256 signature should pass verification."""
        from app.api.endpoints.webhooks import _verify_github_signature
        secret = "test-webhook-secret"
        payload = b'{"action": "push"}'
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        signature = f"sha256={expected}"

        assert _verify_github_signature(payload, signature, secret) is True

    def test_invalid_github_signature(self):
        """Invalid signature should fail verification."""
        from app.api.endpoints.webhooks import _verify_github_signature
        assert _verify_github_signature(b"payload", "sha256=invalid", "secret") is False

    def test_missing_signature_prefix(self):
        """Signature without sha256= prefix should fail."""
        from app.api.endpoints.webhooks import _verify_github_signature
        assert _verify_github_signature(b"payload", "invalid-format", "secret") is False

    def test_empty_signature(self):
        """Empty signature should fail."""
        from app.api.endpoints.webhooks import _verify_github_signature
        assert _verify_github_signature(b"payload", "", "secret") is False


class TestWebhookPayloadExtraction:
    """Test payload extraction from GitHub/GitLab events."""

    def test_extract_github_push_payload(self):
        """Should correctly extract data from a GitHub push event."""
        from app.api.endpoints.webhooks import _extract_github_push
        payload = {
            "repository": {
                "clone_url": "https://github.com/org/repo.git",
                "html_url": "https://github.com/org/repo",
            },
            "ref": "refs/heads/main",
            "pusher": {"name": "testuser"},
            "head_commit": {"id": "abc12345def67890"},
            "commits": [
                {"added": ["src/new_file.py"], "modified": ["src/existing.py"]},
                {"added": [], "modified": ["src/another.py"]},
            ]
        }

        result = _extract_github_push(payload)
        assert result is not None
        assert result["repo_url"] == "https://github.com/org/repo"
        assert result["branch"] == "main"
        assert result["pusher"] == "testuser"
        assert result["head_commit"] == "abc12345"
        assert set(result["changed_files"]) == {"src/new_file.py", "src/existing.py", "src/another.py"}

    def test_extract_gitlab_push_payload(self):
        """Should correctly extract data from a GitLab push event."""
        from app.api.endpoints.webhooks import _extract_gitlab_push
        payload = {
            "repository": {"homepage": "https://gitlab.com/org/repo"},
            "ref": "refs/heads/develop",
            "user_name": "gitlab-user",
            "after": "deadbeef12345678",
            "commits": [
                {"added": ["lib/new.rb"], "modified": ["lib/old.rb"]},
            ]
        }

        result = _extract_gitlab_push(payload)
        assert result is not None
        assert result["repo_url"] == "https://gitlab.com/org/repo"
        assert result["branch"] == "develop"
        assert result["pusher"] == "gitlab-user"
        assert "lib/new.rb" in result["changed_files"]
        assert "lib/old.rb" in result["changed_files"]

    def test_extract_github_push_no_repo_url(self):
        """Should return None if no repository URL found."""
        from app.api.endpoints.webhooks import _extract_github_push
        result = _extract_github_push({"repository": {}})
        assert result is None


class TestWebhookEndpoint:
    """Test the webhook HTTP endpoint."""

    def test_non_push_event_ignored(self, client):
        """Non-push events should be ignored with 200 status."""
        response = client.post(
            "/api/v1/webhooks/git",
            json={"action": "created"},
            headers={"x-github-event": "issues"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"

    def test_github_push_repo_not_onboarded(self, client, db_session):
        """Push for a non-onboarded repo should be ignored."""
        payload = {
            "repository": {
                "clone_url": "https://github.com/unknown/repo.git",
                "html_url": "https://github.com/unknown/repo",
            },
            "ref": "refs/heads/main",
            "pusher": {"name": "user"},
            "head_commit": {"id": "abc12345"},
            "commits": [
                {"added": ["file.py"], "modified": []},
            ],
        }
        response = client.post(
            "/api/v1/webhooks/git",
            json=payload,
            headers={"x-github-event": "push"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"
        assert data["reason"] == "repo_not_onboarded"

    def test_github_push_with_onboarded_repo(self, client, db_session, test_tenant):
        """Push for an onboarded repo should dispatch analysis task."""
        from app.models.repository import Repository

        repo = Repository(
            name="test-repo",
            url="https://github.com/org/test-repo",
            platform="github",
            owner_id=1,
            tenant_id=test_tenant.id,
            analysis_status="completed",
        )
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)

        payload = {
            "repository": {
                "clone_url": "https://github.com/org/test-repo.git",
                "html_url": "https://github.com/org/test-repo",
            },
            "ref": "refs/heads/main",
            "pusher": {"name": "dev"},
            "head_commit": {"id": "commit123"},
            "commits": [
                {"added": ["src/app.py"], "modified": ["src/utils.py"]},
            ],
        }

        with patch("app.api.endpoints.webhooks.crud") as mock_crud:
            # Mock the db query to find the repo
            mock_query = MagicMock()
            mock_filter = MagicMock()
            mock_filter.all.return_value = [repo]
            mock_query.filter.return_value = mock_filter
            mock_crud.repository.model = Repository
            db_session.query = MagicMock(return_value=mock_query)

            with patch("app.tasks.code_analysis_tasks.webhook_triggered_analysis") as mock_task:
                mock_task.delay = MagicMock()

                response = client.post(
                    "/api/v1/webhooks/git",
                    json=payload,
                    headers={"x-github-event": "push"},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "accepted"
                assert data["files_queued"] == 2

    def test_invalid_payload_returns_error(self, client):
        """Invalid payload with no repo info should return error."""
        response = client.post(
            "/api/v1/webhooks/git",
            json={"ref": "refs/heads/main", "commits": []},
            headers={"x-github-event": "push"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["reason"] == "invalid_payload"

    def test_webhook_signature_rejection(self, client):
        """Invalid webhook signature should return 401."""
        with patch("app.api.endpoints.webhooks.settings") as mock_settings:
            mock_settings.WEBHOOK_SECRET = "real-secret"
            mock_settings.API_VERSION = "v1"

            response = client.post(
                "/api/v1/webhooks/git",
                json={"repository": {"clone_url": "https://github.com/org/repo.git"}},
                headers={
                    "x-github-event": "push",
                    "x-hub-signature-256": "sha256=badsignature",
                },
            )
            assert response.status_code == 401
