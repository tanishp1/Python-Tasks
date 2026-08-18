
from unittest.mock import patch, Mock

import pytest
import requests

from scraper import (
    fetch_html,
    parse_product,
    parse_products,
    scrape_products,
    Product,
    ScraperError,
    ParsingError,
)


# ==========================================================================
# fetch_html -- mocking the external API dependency
# ==========================================================================
class TestFetchHtml:
    @patch("scraper.requests.get")
    def test_returns_page_text_on_success(self, mock_get):
        mock_response = Mock()
        mock_response.text = "<html>hi</html>"
        mock_response.raise_for_status = Mock()  # no-op = 200 OK
        mock_get.return_value = mock_response

        result = fetch_html("https://example.com/products")

        assert result == "<html>hi</html>"
        mock_get.assert_called_once_with(
            "https://example.com/products", timeout=10
        )

    @patch("scraper.requests.get")
    def test_custom_timeout_is_forwarded(self, mock_get):
        mock_response = Mock()
        mock_response.text = "<html></html>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetch_html("https://example.com", timeout=3)

        mock_get.assert_called_once_with("https://example.com", timeout=3)

    @patch("scraper.requests.get")
    def test_http_error_raises_scraper_error(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Client Error"
        )
        mock_get.return_value = mock_response

        with pytest.raises(ScraperError, match="Failed to fetch"):
            fetch_html("https://example.com/missing")

    @patch("scraper.requests.get")
    def test_connection_error_raises_scraper_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("no network")

        with pytest.raises(ScraperError):
            fetch_html("https://example.com")

    @patch("scraper.requests.get")
    def test_timeout_raises_scraper_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("timed out")

        with pytest.raises(ScraperError):
            fetch_html("https://example.com")

    def test_empty_url_raises_value_error(self):
        with pytest.raises(ValueError):
            fetch_html("")


# ==========================================================================
# parse_products -- happy path
# ==========================================================================
class TestParseProductsHappyPath:
    def test_parses_all_products(self, sample_html_full):
        products = parse_products(sample_html_full)
        assert len(products) == 2
        assert all(isinstance(p, Product) for p in products)

    def test_parses_title_price_stock_correctly(self, sample_html_full):
        products = parse_products(sample_html_full)
        first, second = products

        assert first.title == "Wireless Mouse"
        assert first.price == 25.99
        assert first.in_stock is True

        assert second.title == "Mechanical Keyboard"
        assert second.price == 1089.00  # comma stripped correctly
        assert second.in_stock is False

    def test_no_products_returns_empty_list(self, sample_html_no_products):
        assert parse_products(sample_html_no_products) == []


# ==========================================================================
# parse_products -- defensive handling of missing/malformed DOM
# ==========================================================================
class TestParseProductsDefensive:
    def test_missing_fields_degrade_to_none_not_exception(
        self, sample_html_missing_fields
    ):
        # Should not raise despite missing/empty elements.
        products = parse_products(sample_html_missing_fields)
        assert len(products) == 4

    def test_missing_price_element_is_none(self, sample_html_missing_fields):
        products = parse_products(sample_html_missing_fields)
        cable = products[0]
        assert cable.title == "USB Cable"
        assert cable.price is None
        assert cable.in_stock is True

    def test_missing_title_element_is_none(self, sample_html_missing_fields):
        products = parse_products(sample_html_missing_fields)
        unnamed = products[1]
        assert unnamed.title is None
        assert unnamed.price == 5.50
        assert unnamed.in_stock is None  # unrecognized status text

    def test_completely_empty_product_div_is_all_none(
        self, sample_html_missing_fields
    ):
        products = parse_products(sample_html_missing_fields)
        empty = products[2]
        assert empty.title is None
        assert empty.price is None
        assert empty.in_stock is None

    def test_empty_text_elements_are_none(self, sample_html_missing_fields):
        products = parse_products(sample_html_missing_fields)
        blank = products[3]
        assert blank.title is None
        assert blank.price is None
        assert blank.in_stock is None

    def test_malformed_unclosed_html_does_not_raise(self, sample_html_malformed):
        # The real defensive-programming test: badly broken markup.
        products = parse_products(sample_html_malformed)
        assert len(products) == 1
        assert products[0].title.startswith("Broken Widget")

    def test_non_numeric_price_text_is_none(self, sample_html_bad_price):
        products = parse_products(sample_html_bad_price)
        assert products[0].price is None
        assert products[0].title == "Mystery Item"
        assert products[0].in_stock is True

    def test_none_input_raises_parsing_error(self):
        with pytest.raises(ParsingError):
            parse_products(None)

    def test_non_string_input_raises_parsing_error(self):
        with pytest.raises(ParsingError):
            parse_products(12345)

    def test_empty_string_returns_empty_list(self):
        assert parse_products("") == []


# ==========================================================================
# Field-level parametrized edge cases
# ==========================================================================
class TestPriceParsingEdgeCases:
    @pytest.mark.parametrize(
        "price_html,expected",
        [
            ('<span class="price">$9.99</span>', 9.99),
            ('<span class="price">9.99</span>', 9.99),
            ('<span class="price">$1,234.56</span>', 1234.56),
            ('<span class="price"></span>', None),
            ('<span class="price">N/A</span>', None),
            ("", None),  # element missing entirely
        ],
    )
    def test_price_variants(self, price_html, expected):
        html = f'<div class="product"><h2 class="product-title">X</h2>{price_html}</div>'
        product = parse_products(html)[0]
        assert product.price == expected


class TestStockParsingEdgeCases:
    @pytest.mark.parametrize(
        "stock_html,expected",
        [
            ('<span class="stock">In Stock</span>', True),
            ('<span class="stock">Available</span>', True),
            ('<span class="stock">Out of Stock</span>', False),
            ('<span class="stock">Unavailable</span>', False),
            ('<span class="stock">Backordered</span>', None),
            ('<span class="stock"></span>', None),
            ("", None),  # element missing entirely
        ],
    )
    def test_stock_variants(self, stock_html, expected):
        html = f'<div class="product"><h2 class="product-title">X</h2>{stock_html}</div>'
        product = parse_products(html)[0]
        assert product.in_stock == expected


# ==========================================================================
# parse_product (single element) via BeautifulSoup directly
# ==========================================================================
class TestParseProductSingleElement:
    def test_parse_product_on_bare_bs4_tag(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(
            '<div class="product"><h2 class="product-title">Lamp</h2>'
            '<span class="price">$40</span>'
            '<span class="stock">In Stock</span></div>',
            "html.parser",
        )
        el = soup.select_one(".product")
        product = parse_product(el)
        assert product == Product(title="Lamp", price=40.0, in_stock=True)


# ==========================================================================
# scrape_products -- integration of fetch + parse, network fully mocked
# ==========================================================================
class TestScrapeProductsIntegration:
    @patch("scraper.requests.get")
    def test_end_to_end_with_mocked_network(self, mock_get, sample_html_full):
        mock_response = Mock()
        mock_response.text = sample_html_full
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        results = scrape_products("https://example.com/shop")

        assert results == [
            {"title": "Wireless Mouse", "price": 25.99, "in_stock": True},
            {"title": "Mechanical Keyboard", "price": 1089.00, "in_stock": False},
        ]
        mock_get.assert_called_once()

    @patch("scraper.requests.get")
    def test_end_to_end_propagates_scraper_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("offline")

        with pytest.raises(ScraperError):
            scrape_products("https://example.com/shop")

    @patch("scraper.fetch_html")
    def test_can_also_mock_fetch_html_directly(self, mock_fetch, sample_html_no_products):
        mock_fetch.return_value = sample_html_no_products
        assert scrape_products("https://example.com/empty-shop") == []
        mock_fetch.assert_called_once_with("https://example.com/empty-shop")