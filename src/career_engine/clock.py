"""Single source of persisted time: UTC ISO-8601 with an explicit offset."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds")


def now_iso() -> str:
    return iso(utc_now())
