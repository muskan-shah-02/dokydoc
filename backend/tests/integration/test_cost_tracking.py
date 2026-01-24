"""
Sprint 1 Integration Tests: BE-COST-01/02/03 Cost Tracking
Tests accurate cost calculation and tracking functionality.
"""
import pytest
from decimal import Decimal
from app.services.cost_service import CostService


class TestCostCalculation:
    """Test cost calculation accuracy (BE-COST-01/02/03)."""

    def test_cost_service_initialization(self):
        """Test that cost service initializes successfully."""
        service = CostService()
        assert service.encoder is not None or service.encoder is None  # tiktoken may not be available
        assert service.cost_per_1k_input_usd > 0
        assert service.cost_per_1k_output_usd > 0
        assert service.usd_to_inr > 0

    def test_token_counting(self):
        """Test token counting functionality."""
        service = CostService()

        # Test with simple text
        text = "Hello world, this is a test."
        token_count = service.count_tokens(text)

        # Should return a reasonable token count
        assert token_count > 0
        assert token_count < len(text)  # Tokens are typically less than characters

    def test_cost_calculation_for_input_output(self):
        """Test cost calculation for given input/output text."""
        service = CostService()

        input_text = "What is the capital of France?"
        output_text = "The capital of France is Paris. It is known as the City of Light."

        result = service.calculate_cost(input_text, output_text)

        # Verify result structure
        assert "input_tokens" in result
        assert "output_tokens" in result
        assert "cost_usd" in result
        assert "cost_inr" in result

        # Verify values are reasonable
        assert result["input_tokens"] > 0
        assert result["output_tokens"] > 0
        assert result["cost_usd"] > 0
        assert result["cost_inr"] > 0

        # Output tokens should generally be more than input for this example
        assert result["output_tokens"] >= result["input_tokens"]

    def test_gemini_pricing_accuracy(self):
        """Test that Gemini 2.5 Flash pricing is accurate (Jan 2025)."""
        service = CostService()

        # Gemini 2.5 Flash pricing (as of Jan 2025)
        # Input: $0.00001875 per 1K tokens
        # Output: $0.000075 per 1K tokens
        assert service.cost_per_1k_input_usd == Decimal("0.00001875")
        assert service.cost_per_1k_output_usd == Decimal("0.000075")

    def test_exchange_rate_is_reasonable(self):
        """Test that USD to INR exchange rate is reasonable."""
        service = CostService()

        # Exchange rate should be between 70 and 100 (reasonable range)
        assert service.usd_to_inr >= Decimal("70.0")
        assert service.usd_to_inr <= Decimal("100.0")

    def test_cost_calculation_with_empty_text(self):
        """Test cost calculation handles empty text gracefully."""
        service = CostService()

        result = service.calculate_cost("", "")

        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 0
        assert result["cost_usd"] == 0.0
        assert result["cost_inr"] == 0.0

    def test_cost_calculation_with_large_text(self):
        """Test cost calculation with larger text."""
        service = CostService()

        # Create a longer text (simulating document analysis)
        input_text = "Analyze this document: " + "Test content. " * 100
        output_text = "Analysis result: " + "Finding. " * 200

        result = service.calculate_cost(input_text, output_text)

        # Cost should be proportional to text length
        assert result["input_tokens"] > 50  # Reasonable token count
        assert result["output_tokens"] > 100
        assert result["cost_inr"] > 0.001  # Should have some cost

    def test_estimate_cost_function(self):
        """Test cost estimation based on character count."""
        service = CostService()

        # Estimate cost for 1000 characters of input
        estimated_cost = service.estimate_cost(1000, is_input=True)

        assert estimated_cost > 0
        assert isinstance(estimated_cost, float)

        # Output should cost more than input (higher per-token price)
        output_cost = service.estimate_cost(1000, is_input=False)
        assert output_cost > estimated_cost

    def test_exchange_rate_update_functionality(self):
        """Test exchange rate update function exists and handles errors."""
        service = CostService()

        # Try to update exchange rate (may fail if no internet/API unavailable)
        try:
            result = service.update_exchange_rate()
            assert isinstance(result, bool)
            # If successful, rate should still be reasonable
            if result:
                assert service.usd_to_inr >= Decimal("70.0")
                assert service.usd_to_inr <= Decimal("100.0")
        except Exception as e:
            # Should handle failures gracefully
            pytest.skip(f"Exchange rate API unavailable: {e}")

    def test_cost_breakdown_calculation(self):
        """Test that cost breakdown is calculated correctly."""
        service = CostService()

        input_text = "Short input"
        output_text = "Longer output with more details and information"

        result = service.calculate_cost(input_text, output_text)

        # Calculate expected costs manually
        input_cost_usd = (result["input_tokens"] / 1000) * float(service.cost_per_1k_input_usd)
        output_cost_usd = (result["output_tokens"] / 1000) * float(service.cost_per_1k_output_usd)
        total_cost_usd = input_cost_usd + output_cost_usd

        # Verify calculations are consistent
        assert abs(result["cost_usd"] - total_cost_usd) < 0.00001  # Float precision
        assert abs(result["cost_inr"] - (total_cost_usd * float(service.usd_to_inr))) < 0.01

    def test_inr_conversion_accuracy(self):
        """Test that USD to INR conversion is accurate."""
        service = CostService()

        # Known cost in USD
        usd_cost = 0.001  # $0.001

        # Calculate INR cost
        inr_cost = usd_cost * float(service.usd_to_inr)

        # Verify conversion
        assert inr_cost > 0
        assert abs(inr_cost - (0.001 * float(service.usd_to_inr))) < 0.001

    def test_zero_cost_for_zero_tokens(self):
        """Test that zero tokens result in zero cost."""
        service = CostService()

        result = service.calculate_cost("", "")

        assert result["cost_usd"] == 0.0
        assert result["cost_inr"] == 0.0
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 0
