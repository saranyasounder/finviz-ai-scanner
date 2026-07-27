from __future__ import annotations


class PipelineError(Exception):
    """Base class for every domain-specific error raised anywhere in the pipeline.
    Catching PipelineError (rather than bare Exception) lets callers distinguish
    a known, named failure mode from a truly unexpected bug."""


class EmptyScreenerError(PipelineError):
    """Raised when a downloaded Finviz screener CSV has no rows."""


class NewsFetchError(PipelineError):
    """Raised when a single ticker's news table can't be fetched or parsed."""


class FibonacciAnalysisError(PipelineError):
    """Raised when there isn't enough price history to compute Fibonacci levels."""


class PriceHistoryError(PipelineError):
    """Raised when OHLC history for a ticker cannot be retrieved."""
