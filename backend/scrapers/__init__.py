"""Traffic-source scrapers used by the backend monitor."""


class ScraperError(RuntimeError):
    """Raised when a source cannot provide a trustworthy scrape result."""
