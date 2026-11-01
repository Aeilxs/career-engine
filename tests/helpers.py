"""Shared test helpers (synthetic data only)."""

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "offers"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def posting(
    title: str | None = "Backend Engineer",
    company: str | None = "Example Corp (synthetic)",
    source_id: str | None = "synthetic/board/offer-900",
    description: str = "Build and operate services.",
    extra: str = "",
) -> bytes:
    lines = []
    if title is not None:
        lines.append(f"Title: {title}")
    if company is not None:
        lines.append(f"Company: {company}")
    if source_id is not None:
        lines.append(f"Source ID: {source_id}")
    lines.append(f"Description: {description}")
    if extra:
        lines.append(extra)
    return ("\n".join(lines) + "\n").encode("utf-8")
