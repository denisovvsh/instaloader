"""Parse Instagram media URLs without talking to Instagram."""

from __future__ import annotations

from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

MEDIA_KINDS = ("reel", "reels", "p", "tv", "share")
SHORTCODE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"

IG_HOSTS = {
    "instagram.com",
    "www.instagram.com",
    "instagr.am",
    "www.instagr.am",
    "l.instagram.com",
}


class UrlParseError(Exception):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


def _hostname(host: str) -> str:
    return (host or "").lower().rstrip(".")


def is_instagram_host(hostname: str) -> bool:
    h = _hostname(hostname)
    if h in IG_HOSTS:
        return True
    return h.endswith(".instagram.com")


def is_stories_path(pathname: str) -> bool:
    parts = [p for p in pathname.split("/") if p]
    return bool(parts) and parts[0].lower() == "stories"


def _clean_shortcode(raw: str) -> Optional[str]:
    code = (raw or "").strip().strip("/")
    if not code:
        return None
    if not all(c in SHORTCODE_CHARS for c in code):
        return None
    if not (5 <= len(code) <= 15):
        return None
    return code


def _from_path(pathname: str) -> Optional[tuple]:
    parts = [unquote(p) for p in pathname.split("/") if p]
    if not parts:
        return None
    kind = parts[0].lower()
    if kind == "share":
        if len(parts) >= 3 and parts[1].lower() in ("reel", "reels", "p", "tv"):
            code = _clean_shortcode(parts[2])
            if code:
                return code, "share"
        if len(parts) >= 2:
            code = _clean_shortcode(parts[1])
            if code:
                return code, "share"
        return None
    if kind in MEDIA_KINDS:
        if len(parts) < 2:
            return None
        code = _clean_shortcode(parts[1])
        if code:
            return code, "reel" if kind in ("reel", "reels") else kind
    return None


def parse_instagram_url(url: str) -> dict:
    """Return {ok, shortcode, kind, url} or raise UrlParseError. No network."""
    raw = (url or "").strip()
    if not raw:
        raise UrlParseError("invalid_url", "Пустая ссылка")
    try:
        parsed = urlparse(raw)
    except Exception as exc:
        raise UrlParseError("invalid_url", f"Некорректная ссылка: {exc}") from exc

    if parsed.scheme not in ("http", "https"):
        raise UrlParseError("invalid_url", "Нужна http(s) ссылка на Instagram")

    host = _hostname(parsed.hostname or "")
    if host == "l.instagram.com":
        qs = parse_qs(parsed.query)
        inner = (qs.get("u") or [None])[0]
        if inner:
            return parse_instagram_url(unquote(inner))
        raise UrlParseError("invalid_url", "Не удалось разобрать редирект l.instagram.com")

    if not is_instagram_host(host):
        raise UrlParseError("invalid_url", "Это не ссылка на Instagram")

    if is_stories_path(parsed.path or ""):
        raise UrlParseError("invalid_url", "Сторис Instagram этим сервисом не скачиваются")

    found = _from_path(parsed.path or "")
    if not found:
        raise UrlParseError("invalid_url", "Не удалось найти код публикации в ссылке")
    shortcode, kind = found
    return {"ok": True, "shortcode": shortcode, "kind": kind, "url": raw}


def is_instagram_media_url(url: str) -> bool:
    try:
        parse_instagram_url(url)
        return True
    except UrlParseError:
        return False
