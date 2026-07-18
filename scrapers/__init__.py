"""Traffic-source scraper package."""


class ScraperError(RuntimeError):
    """Raised when a source cannot provide a trustworthy scrape result."""
