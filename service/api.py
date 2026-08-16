#!/usr/bin/env python3
"""Loopback HTTP API for Instaloader (LeadXClaw sidecar)."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# Allow `python service/api.py` from the repo root.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from service.download import (  # noqa: E402
    cleanup_old_files,
    download_video,
    file_ttl_sec,
    files_dir,
    init_loader,
    is_logged_in,
    DownloadError,
)
from service.urls import UrlParseError, parse_instagram_url  # noqa: E402

FILE_INDEX: dict[str, dict] = {}
FILE_INDEX_LOCK = threading.Lock()


def api_token() -> str:
    return (os.environ.get("INSTALOADER_API_TOKEN") or "").strip()


def listen_port() -> int:
    raw = os.environ.get("INSTALOADER_PORT", "11236")
    try:
        return int(raw)
    except ValueError:
        return 11236


def _json_bytes(payload: dict, status: int = 200) -> tuple[int, bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return status, body


class Handler(BaseHTTPRequestHandler):
    server_version = "leadx-instaloader/1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, status: int, body: bytes, content_type: str = "application/json; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        code, body = _json_bytes(payload, status)
        self._send(code, body)

    def _bearer_ok(self) -> bool:
        expected = api_token()
        if not expected:
            return False
        header = self.headers.get("Authorization") or ""
        if header.startswith("Bearer "):
            return header[7:].strip() == expected
        return False

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise DownloadError("invalid_url", f"Некорректный JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise DownloadError("invalid_url", "Ожидался JSON-объект")
        return data

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json({"status": "ok", "logged_in": is_logged_in()})
            return
        if parsed.path.startswith("/v1/files/"):
            if not self._bearer_ok():
                self._send_json({"ok": False, "error_code": "unauthorized", "error": "Нужен Authorization: Bearer"}, 401)
                return
            file_id = parsed.path[len("/v1/files/") :].strip("/")
            with FILE_INDEX_LOCK:
                meta = FILE_INDEX.get(file_id)
            path = meta["path"] if meta else os.path.join(files_dir(), f"{file_id}.mp4")
            if not path or not os.path.isfile(path):
                self._send_json({"ok": False, "error_code": "not_found", "error": "Файл не найден или истёк"}, 404)
                return
            try:
                if time.time() - os.path.getmtime(path) > file_ttl_sec():
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                    self._send_json({"ok": False, "error_code": "not_found", "error": "Файл не найден или истёк"}, 404)
                    return
            except OSError:
                self._send_json({"ok": False, "error_code": "not_found", "error": "Файл не найден или истёк"}, 404)
                return
            filename = (meta or {}).get("filename") or f"{file_id}.mp4"
            size = os.path.getsize(path)
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            with open(path, "rb") as fh:
                while True:
                    chunk = fh.read(1024 * 256)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            return
        self._send_json({"ok": False, "error_code": "not_found", "error": "Unknown path"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path not in ("/v1/parse-url", "/v1/download"):
            self._send_json({"ok": False, "error_code": "not_found", "error": "Unknown path"}, 404)
            return
        if not self._bearer_ok():
            self._send_json({"ok": False, "error_code": "unauthorized", "error": "Нужен Authorization: Bearer"}, 401)
            return
        try:
            body = self._read_json()
            url = str(body.get("url") or "").strip()
            if parsed.path == "/v1/parse-url":
                result = parse_instagram_url(url)
                self._send_json(result)
                return
            result = download_video(url)
            public = {k: v for k, v in result.items() if k != "path"}
            with FILE_INDEX_LOCK:
                FILE_INDEX[result["file_id"]] = result
            self._send_json(public)
        except UrlParseError as exc:
            self._send_json({"ok": False, "error_code": exc.error_code, "error": str(exc)}, 400)
        except DownloadError as exc:
            status = 503 if exc.error_code in ("unavailable", "rate_limit", "login_required") else 400
            self._send_json({"ok": False, "error_code": exc.error_code, "error": exc.error}, status)
        except Exception as exc:
            self._send_json({"ok": False, "error_code": "unavailable", "error": str(exc)}, 500)


def _cleanup_loop() -> None:
    while True:
        ttl = file_ttl_sec()
        cleanup_old_files(ttl)
        now = time.time()
        with FILE_INDEX_LOCK:
            stale = [fid for fid, meta in FILE_INDEX.items() if now - float(meta.get("created_at") or 0) > ttl]
            for fid in stale:
                FILE_INDEX.pop(fid, None)
        time.sleep(60)


def main() -> None:
    os.makedirs(files_dir(), exist_ok=True)
    try:
        init_loader()
    except Exception as exc:
        sys.stderr.write(f"warning: session not loaded ({exc}); starting anonymously\n")
    threading.Thread(target=_cleanup_loop, daemon=True).start()
    port = listen_port()
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    sys.stderr.write(f"instaloader API listening on 0.0.0.0:{port} logged_in={is_logged_in()}\n")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
