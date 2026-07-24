from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
import re
import ssl
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from models import Item


class SourceError(RuntimeError):
    pass


@dataclass(slots=True)
class SourceResult:
    items: list[Item]
    errors: list[str]


class SourceAdapter:
    source_type = "unknown"

    def __init__(self, config: dict[str, Any], source_config: dict[str, Any]) -> None:
        self.config = config
        self.source_config = source_config
        self.tier = source_config.get("tier", "C")

    def fetch(self) -> SourceResult:
        raise NotImplementedError


def fetch_url(url: str, *, headers: dict[str, str] | None = None, timeout: int = 30) -> bytes:
    request = Request(url, headers=headers or {"User-Agent": "SoftRoboticsIntelligence/0.1"})
    try:
        with urlopen(request, timeout=timeout, context=certificate_context()) as response:
            return response.read()
    except URLError as exc:
        raise SourceError(str(exc)) from exc


def certificate_context() -> ssl.SSLContext | None:
    try:
        import certifi
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return parsed.isoformat() if parsed <= datetime.now(timezone.utc).date() else None
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value).date()
        return parsed.isoformat() if parsed <= datetime.now(timezone.utc).date() else None
    except (TypeError, ValueError, IndexError):
        return None


def first_real_date(*values: str | None) -> str | None:
    for value in values:
        parsed = normalize_date(value)
        if parsed:
            return parsed
    return None


def vocabulary_match(item: Item, config: dict[str, Any]) -> bool:
    """Single-axis robotics gate: a candidate must hit >=1 robotics_term (soft/humanoid
    robotics is the domain anchor). Materials relevance is a downstream score boost, not a
    gate — news like "humanoid breakthrough" carries no materials keyword. Excludes hard-drop
    obvious off-topic matches first."""
    targeting = config.get("targeting", {})
    text = f"{item.title} {item.abstract or ''}".lower()
    excludes = [term.lower() for term in targeting.get("exclude_terms", [])]
    if any(term in text for term in excludes):
        return False

    robotics_terms = [term.lower() for term in targeting.get("robotics_terms", [])]
    return any(term in text for term in robotics_terms)


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def lookback_date(config: dict[str, Any]) -> str:
    hours = int(config.get("meta", {}).get("lookback_hours", 48))
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).date().isoformat()


def resolve_filter_placeholders(filters: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    replacements = {"{lookback_date}": lookback_date(config)}
    for key, value in filters.items():
        if isinstance(value, str):
            for placeholder, replacement in replacements.items():
                value = value.replace(placeholder, replacement)
        resolved[key] = value
    return resolved
