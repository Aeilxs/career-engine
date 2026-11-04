"""Normalization of manually imported text postings, offer identity and duplicate hints.

Imported text is untrusted data: it is parsed into inert strings and never interpreted.
Unknown information stays ``None``; every field carries provenance (source offsets or status).
"""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from career_engine.domain.errors import ValidationFailed

MAX_POSTING_BYTES = 1024 * 1024
MAX_FIELD_CHARS = 2000
PROVENANCE_SCHEMA_VERSION = 1
CONNECTOR_VERSION = "manual-text-1"

_HEADER_KEYS = {
    "title": "title",
    "company": "company",
    "location": "locations",
    "locations": "locations",
    "contract": "contract",
    "salary": "salary_raw_text",
    "source id": "source_id",
    "application url": "apply_url",
    "description": "description",
}
_HEADER_LINE = re.compile(r"^(?P<label>[A-Za-z][A-Za-z ]{0,30}?)[ \t]*:(?P<rest>.*)$")
_LINE = re.compile(r"([^\r\n]*)(\r\n|\n|\r|\Z)")
_TRACKING_PARAMS = {"fbclid", "gclid", "msclkid", "mc_cid", "mc_eid"}
_DEFAULT_PORTS = {"http": 80, "https": 443}
_SIMILARITY_THRESHOLD = 0.75


@dataclass(frozen=True)
class NormalizedOffer:
    title: str | None
    company: str | None
    locations: tuple[str, ...] | None
    contract: str | None
    salary_raw_text: str | None
    description: str | None
    apply_url: str | None
    source_id: str | None
    provenance: dict[str, dict[str, Any]]

    def content_fields(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "company": self.company,
            "locations": None if self.locations is None else list(self.locations),
            "contract": self.contract,
            "salary_raw_text": self.salary_raw_text,
            "description": self.description,
            "apply_url": self.apply_url,
        }

    def normalized_sha256(self) -> str:
        payload = json.dumps(
            self.content_fields(), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OfferIdentity:
    provider: str
    board: str
    external_id: str
    kind: str  # native | url | content


@dataclass(frozen=True)
class DuplicateHint:
    score: float
    reason: str


def decode_posting(raw: bytes) -> str:
    if not raw.strip():
        raise ValidationFailed("The posting is empty.", "EMPTY_POSTING")
    if len(raw) > MAX_POSTING_BYTES:
        raise ValidationFailed(
            f"The posting exceeds {MAX_POSTING_BYTES} bytes.", "POSTING_TOO_LARGE"
        )
    if b"\x00" in raw:
        raise ValidationFailed("The posting looks binary (NUL byte).", "NOT_TEXT")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValidationFailed("The posting is not valid UTF-8 text.", "NOT_UTF8") from error


def _trim(text: str, start: int, end: int) -> tuple[int, int] | None:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end) if end > start else None


def normalize_posting(text: str) -> NormalizedOffer:
    spans: dict[str, tuple[int, int]] = {}
    current: str | None = None
    for match in _LINE.finditer(text):
        if match.end() == match.start():
            continue
        line, line_start = match.group(1), match.start()
        header = _HEADER_LINE.match(line)
        key = _HEADER_KEYS.get(header.group("label").lower()) if header else None
        if header is not None and key is not None and key not in spans:
            spans[key] = (line_start + header.start("rest"), line_start + len(line))
            current = key if key == "description" else None
        elif current == "description":
            spans["description"] = (spans["description"][0], line_start + len(line))

    values: dict[str, str | None] = {}
    provenance: dict[str, dict[str, Any]] = {}
    for key in (
        "title",
        "company",
        "locations",
        "contract",
        "salary_raw_text",
        "source_id",
        "apply_url",
        "description",
    ):
        trimmed = _trim(text, *spans[key]) if key in spans else None
        if trimmed is None:
            values[key] = None
            provenance[key] = {"status": "unknown"}
            continue
        value = text[trimmed[0] : trimmed[1]].replace("\r\n", "\n").replace("\r", "\n")
        if key != "description" and len(value) > MAX_FIELD_CHARS:
            raise ValidationFailed(
                f"Field '{key}' exceeds {MAX_FIELD_CHARS} characters.", "FIELD_TOO_LONG"
            )
        values[key] = value
        provenance[key] = {"status": "extracted", "start": trimmed[0], "end": trimmed[1]}

    locations: tuple[str, ...] | None = None
    if values["locations"] is not None:
        parts = tuple(part.strip() for part in values["locations"].split(";") if part.strip())
        locations = parts or None

    apply_url = values["apply_url"]
    if apply_url is not None and canonicalize_url(apply_url) is None:
        provenance["apply_url"] = {
            **provenance["apply_url"],
            "status": "rejected",
            "reason": "not_a_plain_http_url",
        }
        apply_url = None

    return NormalizedOffer(
        title=values["title"],
        company=values["company"],
        locations=locations,
        contract=values["contract"],
        salary_raw_text=values["salary_raw_text"],
        description=values["description"],
        apply_url=apply_url,
        source_id=values["source_id"],
        provenance=provenance,
    )


def canonicalize_url(url: str) -> str | None:
    """Canonical http(s) URL, or None when unsafe/invalid.

    Only fragments and well-known click-tracking parameters are removed; every other query
    parameter is kept because it may identify the posting.
    """
    candidate = url.strip()
    if not candidate or any(ord(char) < 33 or ord(char) == 127 for char in candidate):
        return None
    try:
        parts = urlsplit(candidate)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() not in _DEFAULT_PORTS or not parts.hostname:
        return None
    if parts.username is not None or parts.password is not None:
        return None
    scheme = parts.scheme.lower()
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    netloc = host if port in (None, _DEFAULT_PORTS[scheme]) else f"{host}:{port}"
    kept = [
        pair
        for pair in parts.query.split("&")
        if pair
        and not (name := pair.split("=", 1)[0].lower()).startswith("utm_")
        and name not in _TRACKING_PARAMS
    ]
    query = "&".join(kept)
    return f"{scheme}://{netloc}{parts.path or '/'}" + (f"?{query}" if query else "")


def derive_identity(
    offer: NormalizedOffer,
    content_sha256: str,
    *,
    source_id: str | None = None,
    provider: str | None = None,
    board: str | None = None,
) -> OfferIdentity:
    """Native source identity wins; a URL or a content hash is only a labelled fallback."""
    chosen_provider = (provider or "").strip() or "manual"
    chosen_board = (board or "").strip()
    native = (source_id or "").strip() or offer.source_id
    if native:
        return OfferIdentity(chosen_provider, chosen_board, native, "native")
    canonical = canonicalize_url(offer.apply_url) if offer.apply_url else None
    if canonical:
        return OfferIdentity(chosen_provider, chosen_board or "url", canonical, "url")
    return OfferIdentity(chosen_provider, chosen_board or "content", content_sha256, "content")


def _text_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", stripped.casefold()).split())


def suggest_duplicate(
    title_a: str | None, company_a: str | None, title_b: str | None, company_b: str | None
) -> DuplicateHint | None:
    """Hint that two *distinct* offers may be the same vacancy. Never a merge decision.

    Unknown title or company yields no hint: absence of data is not similarity.
    """
    if not (title_a and company_a and title_b and company_b):
        return None
    if _text_key(company_a) != _text_key(company_b) or not _text_key(company_a):
        return None
    tokens_a, tokens_b = set(_text_key(title_a).split()), set(_text_key(title_b).split())
    if not tokens_a or not tokens_b:
        return None
    score = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    if score < _SIMILARITY_THRESHOLD:
        return None
    score = round(score, 2)
    return DuplicateHint(score, f"same company and similar title (token overlap {score:.2f})")
