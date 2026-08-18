"""Shared fixtures for the scraper test suite."""
import pytest

SAMPLE_HTML_FULL = """
<html><body>
<div class="product">
  <h2 class="product-title">Wireless Mouse</h2>
  <span class="price">$25.99</span>
  <span class="stock">In Stock</span>
</div>
<div class="product">
  <h2 class="product-title">Mechanical Keyboard</h2>
  <span class="price">$1,089.00</span>
  <span class="stock">Out of Stock</span>
</div>
</body></html>
"""

SAMPLE_HTML_MISSING_FIELDS = """
<html><body>
<div class="product">
  <h2 class="product-title">USB Cable</h2>
  <!-- price element missing entirely -->
  <span class="stock">In Stock</span>
</div>
<div class="product">
  <!-- title element missing entirely -->
  <span class="price">$5.50</span>
  <span class="stock">Currently Unknown</span>
</div>
<div class="product">
  <!-- everything missing -->
</div>
<div class="product">
  <h2 class="product-title"></h2>
  <span class="price"></span>
  <span class="stock"></span>
</div>
</body></html>
"""

# Deliberately broken/unclosed tags -- must not raise.
SAMPLE_HTML_MALFORMED = """
<html><body>
<div class="product">
  <h2 class="product-title">Broken Widget
  <span class="price">$12.50
  <div class="stock">In Stock
</body>
"""

SAMPLE_HTML_BAD_PRICE = """
<html><body>
<div class="product">
  <h2 class="product-title">Mystery Item</h2>
  <span class="price">Call for pricing</span>
  <span class="stock">Available</span>
</div>
</body></html>
"""

SAMPLE_HTML_NO_PRODUCTS = "<html><body><p>No products here</p></body></html>"


@pytest.fixture
def sample_html_full():
    return SAMPLE_HTML_FULL


@pytest.fixture
def sample_html_missing_fields():
    return SAMPLE_HTML_MISSING_FIELDS


@pytest.fixture
def sample_html_malformed():
    return SAMPLE_HTML_MALFORMED


@pytest.fixture
def sample_html_bad_price():
    return SAMPLE_HTML_BAD_PRICE


@pytest.fixture
def sample_html_no_products():
    return SAMPLE_HTML_NO_PRODUCTS