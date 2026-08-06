"""Date and datetime utilities with explicit UTC handling."""

from datetime import UTC, date, datetime


def utcnow() -> datetime:
    """Return the current UTC datetime as a timezone-aware object."""
    return datetime.now(UTC)


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return utcnow().isoformat()


def parse_iso_date(date_str: str) -> date:
    """Parse an ISO-8601 date string (``YYYY-MM-DD``) into a ``date`` object.

    Args:
        date_str: String in ``YYYY-MM-DD`` format.

    Raises:
        ValueError: If the string is not a valid ISO-8601 date.
    """
    return date.fromisoformat(date_str)


def parse_iso_datetime(dt_str: str) -> datetime:
    """Parse an ISO-8601 datetime string into a timezone-aware ``datetime``.

    Args:
        dt_str: ISO-8601 datetime string.
    """
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def date_to_iso(d: date) -> str:
    """Format a ``date`` object as an ISO-8601 string."""
    return d.isoformat()


def is_before(date_str: str, reference: str) -> bool:
    """Return True if *date_str* is strictly before *reference*.

    Both arguments must be ISO-8601 date strings (``YYYY-MM-DD``).
    """
    return parse_iso_date(date_str) < parse_iso_date(reference)


def is_on_or_before(date_str: str, reference: str) -> bool:
    """Return True if *date_str* is on or before *reference*."""
    return parse_iso_date(date_str) <= parse_iso_date(reference)
