"""Download a single Instagram video via Instaloader and collect metadata."""

from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .urls import UrlParseError, parse_instagram_url

from instaloader import Instaloader, Post
from instaloader.exceptions import (
    ConnectionException,
    InstaloaderException,
    InvalidArgumentException,
    LoginRequiredException,
    PrivateProfileNotFollowedException,
    ProfileNotExistsException,
    QueryReturnedNotFoundException,
    TooManyRequestsException,
)


class DownloadError(Exception):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code
        self.error = message


_download_lock = threading.Lock()
_loader: Any = None
_loader_logged_in = False


def data_dir() -> str:
    return os.environ.get("INSTALOADER_DATA", "/data")


def session_path(username: str) -> str:
    return os.path.join(data_dir(), f"session-{username}")


def files_dir() -> str:
    path = os.path.join(data_dir(), "files")
    os.makedirs(path, exist_ok=True)
    return path


def inline_max_bytes() -> int:
    raw = os.environ.get("INSTALOADER_INLINE_MAX_MB", "20")
    try:
        mb = float(raw)
    except ValueError:
        mb = 20.0
    return int(max(1.0, mb) * 1024 * 1024)


DEFAULT_FILE_TTL_DAYS = 3


def file_ttl_sec() -> int:
    """How long mp4 files stay on disk. Default 3 days (host cron matches)."""
    sec_raw = (os.environ.get("INSTALOADER_FILE_TTL_SEC") or "").strip()
    if sec_raw:
        try:
            return max(60, int(sec_raw))
        except ValueError:
            pass
    days_raw = (os.environ.get("INSTALOADER_FILE_TTL_DAYS") or "").strip()
    if days_raw:
        try:
            return max(60, int(float(days_raw) * 86400))
        except ValueError:
            pass
    return DEFAULT_FILE_TTL_DAYS * 24 * 3600


def get_username() -> str:
    return (os.environ.get("INSTALOADER_USERNAME") or "").strip()


def is_logged_in() -> bool:
    return bool(_loader_logged_in)


def _build_loader() -> tuple:
    loader = Instaloader(
        quiet=True,
        download_pictures=False,
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )
    username = get_username()
    path = session_path(username) if username else ""
    if username and path and os.path.isfile(path):
        loader.load_session_from_file(username, filename=path)
        return loader, True
    return loader, False


def init_loader() -> None:
    global _loader, _loader_logged_in
    _loader, _loader_logged_in = _build_loader()


def get_loader() -> Any:
    global _loader
    if _loader is None:
        init_loader()
    return _loader


def _map_exception(exc: BaseException) -> DownloadError:
    if isinstance(exc, DownloadError):
        return exc
    if isinstance(exc, UrlParseError):
        return DownloadError(exc.error_code, str(exc))
    if isinstance(exc, LoginRequiredException):
        return DownloadError("login_required", "Instagram просит войти в аккаунт. Обратитесь в поддержку.")
    if isinstance(exc, PrivateProfileNotFollowedException):
        return DownloadError("private", "Публикация приватная — скачать не получилось.")
    if isinstance(exc, (ProfileNotExistsException, QueryReturnedNotFoundException)):
        return DownloadError("not_found", "Публикация не найдена или удалена.")
    if isinstance(exc, TooManyRequestsException):
        return DownloadError("rate_limit", "Instagram временно ограничил запросы. Попробуйте позже.")
    if isinstance(exc, InvalidArgumentException):
        return DownloadError("invalid_url", "Некорректная ссылка на публикацию Instagram.")
    if isinstance(exc, ConnectionException):
        return DownloadError("unavailable", "Не удалось связаться с Instagram. Попробуйте позже.")
    if isinstance(exc, InstaloaderException):
        return DownloadError("unavailable", f"Не удалось скачать видео: {exc}")
    return DownloadError("unavailable", f"Не удалось скачать видео: {exc}")


def _safe_owner(post: Any) -> dict:
    owner: dict[str, Any] = {
        "username": None,
        "full_name": None,
        "profile_url": None,
        "is_verified": None,
        "followers": None,
    }
    try:
        username = post.owner_username
        owner["username"] = username
        owner["profile_url"] = f"https://www.instagram.com/{username}/" if username else None
    except Exception:
        pass
    try:
        profile = post.owner_profile
        owner["full_name"] = getattr(profile, "full_name", None)
        owner["is_verified"] = bool(getattr(profile, "is_verified", False))
        try:
            owner["followers"] = int(profile.followers)
        except Exception:
            owner["followers"] = None
    except Exception:
        pass
    return owner


def _pick_video_url(post: Any) -> str:
    try:
        if post.is_video and post.video_url:
            return post.video_url
    except Exception:
        pass
    try:
        if getattr(post, "typename", None) == "GraphSidecar":
            for node in post.get_sidecar_nodes():
                if getattr(node, "video_url", None):
                    return node.video_url
    except Exception:
        pass
    raise DownloadError("not_video", "По этой ссылке нет видео.")


def _opt_int(post: Any, name: str) -> Optional[int]:
    try:
        val = getattr(post, name)
        if val is None:
            return None
        return int(val)
    except Exception:
        return None


def _opt_float(post: Any, name: str) -> Optional[float]:
    try:
        val = getattr(post, name)
        if val is None:
            return None
        return float(val)
    except Exception:
        return None


def _metrics(post: Any) -> dict:
    return {
        "likes": _opt_int(post, "likes"),
        "comments": _opt_int(post, "comments"),
        "video_view_count": _opt_int(post, "video_view_count"),
        "video_play_count": _opt_int(post, "video_play_count"),
        "video_duration_sec": _opt_float(post, "video_duration"),
    }


def _permalink(shortcode: str, kind: str) -> str:
    if kind in ("reel", "reels", "share"):
        return f"https://www.instagram.com/reel/{shortcode}/"
    if kind == "tv":
        return f"https://www.instagram.com/tv/{shortcode}/"
    return f"https://www.instagram.com/p/{shortcode}/"


def download_video(url: str) -> dict:
    parsed = parse_instagram_url(url)
    shortcode = parsed["shortcode"]
    kind = parsed["kind"]
    loader = get_loader()
    file_id = str(uuid.uuid4())
    dest = os.path.join(files_dir(), f"{file_id}.mp4")
    video_url = ""
    post = None

    with _download_lock:
        try:
            post = Post.from_shortcode(loader.context, shortcode)
            video_url = _pick_video_url(post)
            loader.context.get_and_write_raw(video_url, dest)
        except Exception as exc:
            if os.path.isfile(dest):
                try:
                    os.remove(dest)
                except OSError:
                    pass
            raise _map_exception(exc) from exc

    size = os.path.getsize(dest) if os.path.isfile(dest) else 0
    if size <= 0:
        raise DownloadError("unavailable", "Файл видео пустой — скачать не удалось.")

    mode = "inline" if size < inline_max_bytes() else "link"
    caption = None
    date_utc = None
    typename = None
    is_sponsored = False
    try:
        caption = post.caption
    except Exception:
        pass
    try:
        dt = post.date_utc
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            date_utc = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    try:
        typename = post.typename
    except Exception:
        pass
    try:
        is_sponsored = bool(post.is_sponsored)
    except Exception:
        pass

    return {
        "ok": True,
        "is_video": True,
        "shortcode": shortcode,
        "filename": f"{shortcode}.mp4",
        "size_bytes": size,
        "content_type": "video/mp4",
        "mode": mode,
        "file_id": file_id,
        "cdn_url": video_url,
        "permalink": _permalink(shortcode, kind),
        "owner": _safe_owner(post),
        "metrics": _metrics(post),
        "caption": caption,
        "date_utc": date_utc,
        "typename": typename,
        "is_sponsored": is_sponsored,
        "created_at": time.time(),
        "path": dest,
    }


def cleanup_old_files(ttl_sec: int | None = None) -> int:
    ttl = file_ttl_sec() if ttl_sec is None else ttl_sec
    root = files_dir()
    now = time.time()
    removed = 0
    try:
        names = os.listdir(root)
    except OSError:
        return 0
    for name in names:
        if name.startswith("."):
            continue
        path = os.path.join(root, name)
        try:
            if not os.path.isfile(path):
                continue
            if now - os.path.getmtime(path) > ttl:
                os.remove(path)
                removed += 1
        except OSError:
            continue
    return removed
