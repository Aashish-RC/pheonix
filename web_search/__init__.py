"""Pheonix Web Search, Polite Scraping, and Grounded Source-Support Citation Verification."""

from .core.models import (
    WebSearchResultItem,
    ScrapedPage,
    WebCitation,
    SourceSupportCheck,
)
from .providers.mock_provider import MockWebSearchProvider
from .providers.duckduckgo import DuckDuckGoSearchProvider
from .scraper.parser import HTMLMarkdownParser
from .scraper.crawler import PoliteCrawler
from .verifier.claim_checker import SourceSupportVerifier

__all__ = [
    "WebSearchResultItem",
    "ScrapedPage",
    "WebCitation",
    "SourceSupportCheck",
    "MockWebSearchProvider",
    "DuckDuckGoSearchProvider",
    "HTMLMarkdownParser",
    "PoliteCrawler",
    "SourceSupportVerifier",
]
