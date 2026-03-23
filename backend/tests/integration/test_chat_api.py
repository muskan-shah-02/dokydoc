"""
Sprint 7 / Task 18: Chat API Tests

Tests for AskyDoc chat conversation endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import models


class TestCreateConversation:
    """Test POST /chat/conversations — create a new conversation."""

    def test_create_conversation_returns_201(self, client: TestClient, auth_headers: dict):
        """Authenticated user can create a new conversation."""
        response = client.post(
            "/api/v1/chat/conversations",
            headers=auth_headers,
            json={"title": "Test Conversation", "context_type": "general"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Conversation"
        assert data["context_type"] == "general"
        assert data["model_preference"] == "gemini"
        assert data["message_count"] == 0
