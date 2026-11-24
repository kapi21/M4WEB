"""Cliente HTTP hacia la API cruda de la M4 Board."""

from __future__ import annotations

import mimetypes
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_HOST = os.environ.get("M4_HOST", "http://cpc6128").rstrip("/")
TIMEOUT = float(os.environ.get("M4_TIMEOUT", "12"))


class M4Error(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class M4Client:
    def __init__(self, base: str | None = None, timeout: float = TIMEOUT):
        self.base = (base or DEFAULT_HOST).rstrip("/")
        self.timeout = timeout

    def _url(self, path: str, query: dict[str, str] | None = None) -> str:
        if not path.startswith("/"):
            path = "/" + path
        url = self.base + path
        if query:
            url += "?" + urllib.parse.urlencode(query, safe="/")
        return url

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        query: dict[str, str] | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes, str]:
        url = self._url(path, query)
        req = urllib.request.Request(url, data=data, method=method)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                return resp.status, body, ctype
        except urllib.error.HTTPError as e:
            body = e.read() if e.fp else b""
            raise M4Error(f"HTTP {e.code}: {e.reason}", e.code) from e
        except urllib.error.URLError as e:
            raise M4Error(f"Sin conexion a {self.base}: {e.reason}") from e
        except TimeoutError as e:
            raise M4Error(f"Timeout contactando {self.base}") from e

    def _get_text(self, path: str, query: dict[str, str] | None = None) -> str:
        _status, body, _ctype = self._request(path, query=query)
        return body.decode("latin-1", errors="replace")

    def status(self) -> dict[str, Any]:
        try:
            status, _body, _ctype = self._request("/")
            return {"ok": True, "host": self.base, "http_status": status}
        except M4Error as e:
            return {"ok": False, "host": self.base, "error": str(e)}

    def _normalize_dir(self, path: str) -> str:
        path = path.replace("\\", "/")
        if not path.startswith("/"):
            path = "/" + path
        if not path.endswith("/"):
            path += "/"
        # La M4 a veces usa // como raíz
        if path == "/":
            return "//"
        return path

    def list_dir(self, path: str = "/") -> dict[str, Any]:
        target = self._normalize_dir(path)
        # Forzar regeneración de dir.txt
        ls_path = target.rstrip("/")
        if not ls_path:
            ls_path = "/"
        try:
            self._request("/config.cgi", query={"ls": ls_path})
        except M4Error:
            pass
        text = self._get_text("/sd/m4/dir.txt")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip() != ""]
        if not lines:
            raise M4Error("dir.txt vacio")
        current = lines[0]
        entries: list[dict[str, Any]] = []
        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) < 2:
                continue
            name = parts[0]
            kind = parts[1]
            size = parts[2] if len(parts) > 2 else ""
            # kind 0 = carpeta; .dsk/.cpr se navegan como directorios virtuales
            is_dir = kind == "0" or name.lower().endswith((".dsk", ".cpr"))
            entries.append(
                {
                    "name": name,
                    "is_dir": is_dir,
                    "size": "" if is_dir and kind == "0" else size,
                    "raw_kind": kind,
                }
            )
        entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        return {"path": current, "entries": entries}

    def upload(self, dest_dir: str, filename: str, content: bytes) -> None:
        dest = self._normalize_dir(dest_dir)
        # Si estamos dentro de .dsk/.cpr, subir al padre (como la web original)
        lower = dest.lower()
        if lower.rstrip("/").endswith((".dsk", ".cpr")):
            dest = dest.rstrip("/").rsplit("/", 1)[0] + "/"
        remote_name = dest + filename
        boundary = "----M4WebBoundary7MA4YWxkTrZu0gW"
        disposition = (
            f'Content-Disposition: form-data; name="file"; filename="{remote_name}"'
        )
        parts = [
            f"--{boundary}\r\n{disposition}\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n".encode("ascii"),
            content,
            f"\r\n--{boundary}--\r\n".encode("ascii"),
        ]
        body = b"".join(parts)
        self._request(
            "/",
            method="POST",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        )

    def mkdir(self, path: str) -> None:
        self._request("/config.cgi", query={"mkdir": path})

    def delete(self, path: str) -> None:
        self._request("/config.cgi", query={"rm": path})

    def run(self, path: str) -> None:
        self._request("/config.cgi", query={"run2": path})

    def cd(self, path: str) -> None:
        self._request("/config.cgi", query={"cd": path})

    def cd2(self, path: str) -> None:
        self._request("/config.cgi", query={"cd2": path})

    def download(self, path: str) -> tuple[bytes, str]:
        path = path.replace("\\", "/")
        if not path.startswith("/"):
            path = "/" + path
        # /sd + path; raíz // → /sd/
        sd_path = "/sd" + path
        if path.startswith("//"):
            sd_path = "/sd/" + path.lstrip("/")
        status, body, ctype = self._request(sd_path)
        name = path.rstrip("/").rsplit("/", 1)[-1] or "download.bin"
        return body, name

    def control(self, action: str, value: str = "") -> None:
        key_map = {
            "m4_reset": "mres",
            "cpc_reset": "cres",
            "cpc_pause": "chlt",
            "hack_menu": "cnmi",
            "start_cart": "cctr",
            "run": "run",
            "cd": "cd2",
        }
        if action not in key_map:
            raise M4Error(f"Accion de control desconocida: {action}")
        key = key_map[action]
        if action in ("run", "cd"):
            if not value:
                raise M4Error("Falta ruta")
            self._request("/config.cgi", query={key: value})
        else:
            # botones: nombre=etiqueta
            labels = {
                "mres": "M4 Reset",
                "cres": "CPC Reset",
                "chlt": "CPC Pause",
                "cnmi": "Hack Menu",
                "cctr": "Start Cart",
            }
            self._request("/config.cgi", query={key: labels[key]})

    def get_settings(self) -> dict[str, Any]:
        html = self._get_text("/settings.shtml")
        def inp(name: str) -> str:
            m = re.search(
                rf'name="{name}"[^>]*value="([^"]*)"', html, re.I
            ) or re.search(
                rf'value="([^"]*)"[^>]*name="{name}"', html, re.I
            )
            return m.group(1) if m else ""

        def checked(name: str) -> bool:
            # input checked ... name="dhcp"
            m = re.search(rf'<input[^>]*name="{name}"[^>]*>', html, re.I)
            if not m:
                m = re.search(rf'<input[^>]*name="{name}"[^>]*/?>', html, re.I)
            if not m:
                return False
            return "checked" in m.group(0).lower()

        time_m = re.search(r"<!--#time-->([^<\n]+)", html)
        ver_m = re.search(r"<!--#ver-->([^<\n]+)", html)
        mac_m = re.search(r"<!--#mac-->([^<\n]+)", html)
        return {
            "time": (time_m.group(1).strip() if time_m else ""),
            "timezone": inp("zone"),
            "ntp": inp("ntp"),
            "netbios": inp("navn"),
            "ssid": inp("ssid"),
            "password": inp("pw"),
            "dhcp": checked("dhcp"),
            "ip": inp("ip"),
            "subnet": inp("nm"),
            "gateway": inp("gw"),
            "dns1": inp("dns1"),
            "dns2": inp("dns2"),
            "mac": (mac_m.group(1).strip() if mac_m else ""),
            "version": (ver_m.group(1).strip() if ver_m else ""),
        }

    def set_settings(self, patch: dict[str, Any]) -> None:
        if "timezone" in patch:
            self._request("/config.cgi", query={"zone": str(patch["timezone"])})
        if "ntp" in patch:
            self._request("/config.cgi", query={"ntp": str(patch["ntp"])})
        if "netbios" in patch:
            self._request("/config.cgi", query={"navn": str(patch["netbios"])})
        if "ssid" in patch or "password" in patch:
            # el form original envía ssid+pw juntos
            cur = self.get_settings()
            ssid = str(patch.get("ssid", cur["ssid"]))
            pw = str(patch.get("password", cur["password"]))
            self._request("/config.cgi", query={"ssid": ssid, "pw": pw})
        if "dhcp" in patch:
            q = {"dhcp": "on"} if patch["dhcp"] else {}
            self._request("/checkbox.cgi", query=q)
        if any(k in patch for k in ("ip", "subnet", "gateway")):
            cur = self.get_settings()
            self._request(
                "/config.cgi",
                query={
                    "ip": str(patch.get("ip", cur["ip"])),
                    "nm": str(patch.get("subnet", cur["subnet"])),
                    "gw": str(patch.get("gateway", cur["gateway"])),
                },
            )
        if "dns1" in patch or "dns2" in patch:
            cur = self.get_settings()
            self._request(
                "/config.cgi",
                query={
                    "dns1": str(patch.get("dns1", cur["dns1"])),
                    "dns2": str(patch.get("dns2", cur["dns2"])),
                },
            )

    def get_roms(self) -> dict[str, Any]:
        html = self._get_text("/roms.shtml")

        def inp(name: str) -> str:
            m = re.search(rf'name="{name}"[^>]*value="([^"]*)"', html, re.I) or re.search(
                rf'value="([^"]*)"[^>]*name="{name}"', html, re.I
            )
            return m.group(1) if m else ""

        def checked(name: str) -> bool:
            m = re.search(rf'<input[^>]*name="{name}"[^>]*>', html, re.I)
            if not m:
                return False
            return "checked" in m.group(0).lower()

        slots: list[dict[str, Any]] = []
        for m in re.finditer(
            r"Rom slot (\d+)</td><td[^>]*><!--#romn-->(.*?)</td>", html, re.I | re.S
        ):
            slots.append({"slot": int(m.group(1)), "name": m.group(2).strip()})
        # completar 0..31 si faltan
        by_slot = {s["slot"]: s for s in slots}
        slots = [by_slot.get(i, {"slot": i, "name": ""}) for i in range(32)]
        return {
            "m4_enabled": checked("m4en"),
            "m4_rom": inp("m4rm"),
            "romboard_start": inp("m4rb"),
            "lower_enabled": checked("lwen"),
            "lower_slot": inp("lwsl"),
            "only_16": checked("rs16"),
            "slots": slots,
        }

    def set_rom_config(self, patch: dict[str, Any]) -> None:
        if "m4_enabled" in patch:
            q = {"m4en": "on"} if patch["m4_enabled"] else {}
            self._request("/checkbox2.cgi", query=q)
        if "m4_rom" in patch:
            self._request("/config.cgi", query={"m4rm": str(patch["m4_rom"])})
        if "romboard_start" in patch:
            self._request("/config.cgi", query={"m4rb": str(patch["romboard_start"])})
        if "lower_enabled" in patch:
            q = {"lwen": "on"} if patch["lower_enabled"] else {}
            self._request("/checkbox3.cgi", query=q)
        if "lower_slot" in patch:
            self._request("/config.cgi", query={"lwsl": str(patch["lower_slot"])})
        if "only_16" in patch:
            q = {"rs16": "on"} if patch["only_16"] else {}
            self._request("/checkbox4.cgi", query=q)

    def remove_rom(self, slot: int) -> None:
        self._request("/roms.shtml", query={"rmsl": str(slot)})

    def upload_rom(self, slot: int, slot_name: str, filename: str, content: bytes) -> None:
        boundary = "----M4RomBoundary7MA4YWxkTrZu0gW"
        chunks: list[bytes] = []

        def add_field(name: str, value: str) -> None:
            chunks.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n"
                ).encode("latin-1", errors="replace")
            )

        add_field("slotnum", str(slot))
        add_field("slotname", slot_name)
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="uploadedfile"; filename="{filename}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n"
            ).encode("ascii")
        )
        chunks.append(content)
        chunks.append(f"\r\n--{boundary}--\r\n".encode("ascii"))
        body = b"".join(chunks)
        self._request(
            "/roms.shtml",
            method="POST",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        )

    def upload_cart(self, filename: str, content: bytes) -> None:
        boundary = "----M4CartBoundary7MA4YWxkTrZu0gW"
        chunks: list[bytes] = []
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="slotnum"\r\n\r\n'
                f"48\r\n"
            ).encode("ascii")
        )
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="uploadedfile"; filename="{filename}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n"
            ).encode("ascii")
        )
        chunks.append(content)
        chunks.append(f"\r\n--{boundary}--\r\n".encode("ascii"))
        body = b"".join(chunks)
        # uploadctr.shtml suele POST a roms o a sí mismo; probar uploadctr
        self._request(
            "/uploadctr.shtml",
            method="POST",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        )
