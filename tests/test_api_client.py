"""Unit tests for LiveAPIClient."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from jlcpcb_mcp.server import LiveAPIClient


class TestLiveAPIClient:
    """Test LiveAPIClient.fetch_component_details."""

    @patch("jlcpcb_mcp.server.requests.get")
    def test_fetch_successful_response(self, mock_get):
        """Test successful API response with valid component data."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 200,
            "result": {
                "productCode": "C17976",
                "productModel": "1206W4F680JT5E",
                "productNameEn": "RES 68Ω ±1% 250mW 1206",
                "stockNumber": 33900,
                "productPriceList": [
                    {"ladder": 100, "usdPrice": 0.0037},
                    {"ladder": 1000, "usdPrice": 0.0029},
                ],
                "paramVOList": [
                    {"paramNameEn": "Resistance", "paramValueEn": "68Ω"},
                    {"paramNameEn": "Power(Watts)", "paramValueEn": "250mW"},
                ],
                "pdfUrl": "https://datasheet.lcsc.com/test.pdf",
                "productImages": ["https://assets.lcsc.com/images/test.jpg"],
            },
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call function
        result = LiveAPIClient.fetch_component_details("C17976")

        # Verify request was made correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "productCode=C17976" in call_args[0][0]
        assert call_args[1]["timeout"] == 10
        assert "User-Agent" in call_args[1]["headers"]

        # Verify result
        assert result is not None
        assert result["productCode"] == "C17976"
        assert result["stockNumber"] == 33900
        assert len(result["productPriceList"]) == 2
        assert result["productPriceList"][0]["ladder"] == 100

    @patch("jlcpcb_mcp.server.requests.get")
    def test_fetch_non_200_code(self, mock_get):
        """Test API response with non-200 code."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 404,
            "message": "Component not found",
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = LiveAPIClient.fetch_component_details("C99999999")

        assert result is None

    @patch("jlcpcb_mcp.server.requests.get")
    def test_fetch_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        mock_get.side_effect = requests.exceptions.HTTPError("404 Not Found")

        result = LiveAPIClient.fetch_component_details("C99999999")

        assert result is None

    @patch("jlcpcb_mcp.server.requests.get")
    def test_fetch_timeout_error(self, mock_get):
        """Test handling of timeout errors."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        result = LiveAPIClient.fetch_component_details("C17976")

        assert result is None

    @patch("jlcpcb_mcp.server.requests.get")
    def test_fetch_connection_error(self, mock_get):
        """Test handling of connection errors."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

        result = LiveAPIClient.fetch_component_details("C17976")

        assert result is None

    @patch("jlcpcb_mcp.server.requests.get")
    def test_fetch_invalid_json(self, mock_get):
        """Test handling of invalid JSON response."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = LiveAPIClient.fetch_component_details("C17976")

        assert result is None

    @patch("jlcpcb_mcp.server.requests.get")
    def test_fetch_missing_result_key(self, mock_get):
        """Test API response without result key."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 200}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = LiveAPIClient.fetch_component_details("C17976")

        # Should return empty dict when result key is missing
        assert result == {}

    @patch("jlcpcb_mcp.server.requests.get")
    def test_fetch_with_different_lcsc_formats(self, mock_get):
        """Test that LCSC number is passed correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 200,
            "result": {"productCode": "C123"},
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Test with C prefix
        LiveAPIClient.fetch_component_details("C123")
        assert "productCode=C123" in mock_get.call_args[0][0]

        # Test with different LCSC number
        LiveAPIClient.fetch_component_details("C999999")
        assert "productCode=C999999" in mock_get.call_args[0][0]

    @patch("jlcpcb_mcp.server.requests.get")
    def test_fetch_includes_required_headers(self, mock_get):
        """Test that required headers are included in request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 200, "result": {}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        LiveAPIClient.fetch_component_details("C17976")

        # Check headers
        headers = mock_get.call_args[1]["headers"]
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert headers["Accept"] == "application/json"
        assert "Referer" in headers
        assert headers["Referer"] == "https://jlcpcb.com/"

    @patch("jlcpcb_mcp.server.requests.get")
    def test_fetch_empty_price_list(self, mock_get):
        """Test handling of component with no pricing data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 200,
            "result": {
                "productCode": "C17976",
                "stockNumber": 0,
                "productPriceList": [],  # No pricing
            },
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = LiveAPIClient.fetch_component_details("C17976")

        assert result is not None
        assert result["stockNumber"] == 0
        assert result["productPriceList"] == []

    @patch("jlcpcb_mcp.server.requests.get")
    def test_fetch_minimal_response(self, mock_get):
        """Test handling of minimal valid response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 200,
            "result": {
                "productCode": "C17976",
            },
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = LiveAPIClient.fetch_component_details("C17976")

        assert result is not None
        assert result["productCode"] == "C17976"
        # Should handle missing optional fields gracefully
        assert result.get("stockNumber") is None
        assert result.get("productPriceList") is None
