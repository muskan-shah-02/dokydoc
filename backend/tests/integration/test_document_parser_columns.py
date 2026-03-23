"""
Integration Tests — Multi-Column PDF Detection (CAE-03)

Tests the column detection and merged extraction logic in the
pdfplumber parser strategy.
"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.document_parser import MultiModalDocumentParser


class MockWord:
    """Simulates a pdfplumber word dict."""
    def __init__(self, x0, x1, text="word"):
        self._dict = {"x0": x0, "x1": x1, "text": text}

    def __getitem__(self, key):
        return self._dict[key]


class MockPage:
    """Simulates a pdfplumber page with configurable column layout."""
    def __init__(self, width=612, words=None):
        self.width = width
        self.height = 792
        self._words = words or []
        self._text = "Page text content"

    def extract_words(self, **kwargs):
        return self._words

    def extract_text(self):
        return self._text

    def within_bbox(self, bbox):
        """Return self for simplicity — real pdfplumber returns a cropped page."""
        return self


def make_single_column_words(page_width=612, count=30):
    """Generate words centered in a single column."""
    words = []
    center = page_width / 2
    for i in range(count):
        x0 = center - 100
        x1 = center + 100
        words.append({"x0": x0, "x1": x1, "text": f"word{i}"})
    return words


def make_two_column_words(page_width=612, left_count=20, right_count=20):
    """Generate words split across two columns."""
    words = []
    for i in range(left_count):
        words.append({"x0": 50, "x1": 200, "text": f"left{i}"})
    for i in range(right_count):
        words.append({"x0": 350, "x1": 550, "text": f"right{i}"})
    return words


class TestColumnDetection:
    """Test the _detect_columns method."""

    @pytest.fixture(autouse=True)
    def setup_parser(self):
        """Create parser with mocked Gemini to avoid API key requirement."""
        with patch("app.services.document_parser.settings") as mock_settings, \
             patch("app.services.document_parser.genai"):
            mock_settings.GEMINI_API_KEY = "test-key"
            mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
            mock_settings.GEMINI_VISION_MODEL = "gemini-2.5-flash"
            self.parser = MultiModalDocumentParser.__new__(MultiModalDocumentParser)
            # Initialize the LoggerMixin manually
            import logging
            self.parser.logger = logging.getLogger("test_parser")

    def test_single_column_detected(self):
        page = MockPage(width=612, words=make_single_column_words())
        result = self.parser._detect_columns(page)
        assert result == 1

    def test_two_columns_detected(self):
        page = MockPage(width=612, words=make_two_column_words())
        result = self.parser._detect_columns(page)
        assert result == 2

    def test_few_words_defaults_single(self):
        """Pages with < 10 words should default to single column."""
        page = MockPage(width=612, words=[{"x0": 50, "x1": 150, "text": "hi"}] * 5)
        result = self.parser._detect_columns(page)
        assert result == 1

    def test_asymmetric_layout_single(self):
        """All words on one side should be single column."""
        words = [{"x0": 50, "x1": 200, "text": f"w{i}"} for i in range(30)]
        page = MockPage(width=612, words=words)
        result = self.parser._detect_columns(page)
        assert result == 1

    def test_exception_returns_single(self):
        """If extract_words fails, default to single column."""
        page = MagicMock()
        page.width = 612
        page.extract_words.side_effect = Exception("parse error")
        result = self.parser._detect_columns(page)
        assert result == 1


class TestColumnsMergedExtraction:
    """Test the _extract_columns_merged method."""

    @pytest.fixture(autouse=True)
    def setup_parser(self):
        with patch("app.services.document_parser.settings") as mock_settings, \
             patch("app.services.document_parser.genai"):
            mock_settings.GEMINI_API_KEY = "test-key"
            mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
            mock_settings.GEMINI_VISION_MODEL = "gemini-2.5-flash"
            self.parser = MultiModalDocumentParser.__new__(MultiModalDocumentParser)
            import logging
            self.parser.logger = logging.getLogger("test_parser")

    def test_merged_extraction_returns_text(self):
        page = MockPage(width=612)
        result = self.parser._extract_columns_merged(page)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_fallback_on_error(self):
        """If within_bbox fails, fall back to extract_text."""
        page = MagicMock()
        page.width = 612
        page.height = 792
        page.within_bbox.side_effect = Exception("bbox error")
        page.extract_text.return_value = "fallback text"
        result = self.parser._extract_columns_merged(page)
        assert result == "fallback text"
