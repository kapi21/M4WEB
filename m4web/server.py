"""Servidor HTTP local: UI estática + /api/* hacia la M4."""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .m4_client import DEFAULT_HOST, M4Client, M4Error

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_PORT = int(os.environ.get("M4WEB_PORT", "8787"))


def _json_bytes(data: Any, status: int = 200) -> tuple[int, bytes, str]:
    return status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"


def _parse_multipart(body: bytes, content_type: str) -> dict[str, Any]:
    """Parseo mínimo multipart/form-data → {name: str|{'filename', 'content'}}."""
    m = re.search(r"boundary=([^;]+)", content_type, re.I)
    if not m:
        raise ValueError("Sin boundary")
    boundary = m.group(1).strip().strip('"').encode("ascii")
    parts = body.split(b"--" + boundary)
    out: dict[str, Any] = {}
    for part in parts:
        if part in (b"", b"--", b"--\r\n", b"\r\n", b"--\r\n"):
            continue
        if part.startswith(b"--"):
            continue
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        if b"\r\n\r\n" not in part:
            continue
        head, payload = part.split(b"\r\n\r\n", 1)
        if payload.endswith(b"\r\n"):
            payload = payload[:-2]
        headers = head.decode("latin-1", errors="replace")
        name_m = re.search(r'name="([^"]+)"', headers)
        if not name_m:
            continue
        name = name_m.group(1)
        fn_m = re.search(r'filename="([^"]*)"', headers)
        if fn_m:
            out[name] = {"filename": fn_m.group(1), "content": payload}
        else:
            out[name] = payload.decode("utf-8", errors="replace")
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "M4Web/0.1"
    client: M4Client

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data: Any, status: int = 200) -> None:
        st, body, ctype = _json_bytes(data, status)
        self._send(st, body, ctype)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _read_json(self) -> dict[str, Any]:
        raw = self._read_body()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path.startswith("/api/"):
            self._api_get(path, qs)
            return

        if path in ("/", "/index.html"):
            self._static("index.html")
            return
        # static files
        rel = path.lstrip("/")
        self._static(rel)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/"):
            self._send_json({"error": "Not found"}, 404)
            return
        try:
            self._api_post(path)
        except M4Error as e:
            self._send_json({"ok": False, "error": str(e)}, 502)
        except Exception as e:  # noqa: BLE001
            self._send_json({"ok": False, "error": str(e)}, 500)

    def _static(self, rel: str) -> None:
        # Evitar path traversal
        candidate = (STATIC_DIR / rel).resolve()
        if not str(candidate).startswith(str(STATIC_DIR.resolve())):
            self._send(403, b"Forbidden", "text/plain")
            return
        if not candidate.is_file():
            self._send(404, b"Not found", "text/plain")
            return
        data = candidate.read_bytes()
        ctype = "application/octet-stream"
        if rel.endswith(".html"):
            ctype = "text/html; charset=utf-8"
        elif rel.endswith(".css"):
            ctype = "text/css; charset=utf-8"
        elif rel.endswith(".js"):
            ctype = "application/javascript; charset=utf-8"
        elif rel.endswith(".svg"):
            ctype = "image/svg+xml"
        self._send(200, data, ctype)

    def _api_get(self, path: str, qs: dict[str, list[str]]) -> None:
        c = self.client
        try:
            if path == "/api/status":
                self._send_json(c.status())
                return
            if path == "/api/files":
                p = qs.get("path", ["/"])[0]
                self._send_json(c.list_dir(p))
                return
            if path == "/api/files/download":
                p = qs.get("path", [""])[0]
                if not p:
                    self._send_json({"error": "path requerido"}, 400)
                    return
                data, name = c.download(p)
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header(
                    "Content-Disposition", f'attachment; filename="{name}"'
                )
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if path == "/api/settings":
                self._send_json(c.get_settings())
                return
            if path == "/api/roms":
                self._send_json(c.get_roms())
                return
            self._send_json({"error": "Not found"}, 404)
        except M4Error as e:
            self._send_json({"ok": False, "error": str(e)}, 502)
        except Exception as e:  # noqa: BLE001
            self._send_json({"ok": False, "error": str(e)}, 500)

    def _api_post(self, path: str) -> None:
        c = self.client
        ctype = self.headers.get("Content-Type", "")

        if path == "/api/files/upload":
            body = self._read_body()
            fields = _parse_multipart(body, ctype)
            dest = str(fields.get("path", "/"))
            f = fields.get("file")
            if not isinstance(f, dict):
                self._send_json({"error": "file requerido"}, 400)
                return
            filename = f.get("filename") or "upload.bin"
            # si el browser manda path completo, quedarnos con el nombre
            filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
            c.upload(dest, filename, f["content"])
            self._send_json({"ok": True, "path": dest, "name": filename})
            return

        if path == "/api/roms/upload":
            body = self._read_body()
            fields = _parse_multipart(body, ctype)
            slot = int(str(fields.get("slot", "0")))
            slot_name = str(fields.get("slotname", "") or f"ROM{slot}")
            f = fields.get("file")
            if not isinstance(f, dict):
                self._send_json({"error": "file requerido"}, 400)
                return
            filename = (f.get("filename") or "rom.bin").replace("\\", "/").rsplit("/", 1)[-1]
            c.upload_rom(slot, slot_name, filename, f["content"])
            self._send_json({"ok": True, "slot": slot})
            return

        if path == "/api/roms/upload_cart":
            body = self._read_body()
            fields = _parse_multipart(body, ctype)
            f = fields.get("file")
            if not isinstance(f, dict):
                self._send_json({"error": "file requerido"}, 400)
                return
            filename = (f.get("filename") or "cart.cpr").replace("\\", "/").rsplit("/", 1)[-1]
            c.upload_cart(filename, f["content"])
            self._send_json({"ok": True})
            return

        data = self._read_json()

        if path == "/api/files/mkdir":
            c.mkdir(str(data.get("path", "")))
            self._send_json({"ok": True})
            return
        if path == "/api/files/delete":
            c.delete(str(data.get("path", "")))
            self._send_json({"ok": True})
            return
        if path == "/api/files/run":
            c.run(str(data.get("path", "")))
            self._send_json({"ok": True})
            return
        if path == "/api/files/cd":
            c.cd(str(data.get("path", "")))
            self._send_json({"ok": True})
            return
        if path == "/api/control":
            c.control(str(data.get("action", "")), str(data.get("value", "")))
            self._send_json({"ok": True})
            return
        if path == "/api/settings":
            c.set_settings(data)
            self._send_json({"ok": True, "settings": c.get_settings()})
            return
        if path == "/api/roms/config":
            c.set_rom_config(data)
            self._send_json({"ok": True, "roms": c.get_roms()})
            return
        if path == "/api/roms/remove":
            c.remove_rom(int(data.get("slot", -1)))
            self._send_json({"ok": True})
            return

        self._send_json({"error": "Not found"}, 404)


def run(
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    m4_host: str | None = None,
    open_browser: bool = True,
) -> None:
    client = M4Client(m4_host or DEFAULT_HOST)

    class BoundHandler(Handler):
        pass

    BoundHandler.client = client
    httpd = ThreadingHTTPServer((host, port), BoundHandler)
    url = f"http://{host}:{port}/"
    print(f"M4 Web Proxy en {url}")
    print(f"Destino M4: {client.base}")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrado.")
        httpd.server_close()
