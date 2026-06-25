from __future__ import annotations

import json
import mimetypes
import os
import re
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from src.cms_client import get_facility_snapshot
from src.pdf_report import generate_snapshot_pdf, sanitize_filename

ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"
MAX_BODY_BYTES = 2 * 1024 * 1024


def json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "FacilityAssessmentHTTP/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.getenv("QUIET_LOGS") != "1":
            super().log_message(fmt, *args)

    def send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_pdf(self, filename: str, body: bytes) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - inherited API
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/health":
            self.send_json(HTTPStatus.OK, {"ok": True})
            return

        if path.startswith("/api/facility"):
            self.handle_facility_lookup(path, parsed.query)
            return

        self.serve_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802 - inherited API
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") == "/api/pdf":
            self.handle_pdf_download()
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "Route not found."})

    def handle_facility_lookup(self, path: str, query: str) -> None:
        try:
            ccn = ""
            match = re.match(r"^/api/facility/(\d{6})$", path)
            if match:
                ccn = match.group(1)
            else:
                ccn = parse_qs(query).get("ccn", [""])[0]
            ccn = re.sub(r"\D", "", ccn or "")
            snapshot = get_facility_snapshot(ccn)
            self.send_json(HTTPStatus.OK, {"data": snapshot})
        except ValueError as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except LookupError as exc:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
        except Exception as exc:  # keep the browser useful, but avoid stack traces
            self.send_json(HTTPStatus.BAD_GATEWAY, {
                "error": "Unable to fetch CMS data right now. Please verify the CCN and try again.",
                "detail": str(exc),
            })

    def read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            raise ValueError("Request body is empty.")
        if length > MAX_BODY_BYTES:
            raise ValueError("Request body is too large.")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def handle_pdf_download(self) -> None:
        try:
            payload = self.read_json_body()
            pdf_bytes = generate_snapshot_pdf(payload)
            manual = payload.get("manual", {}) or {}
            provider = payload.get("provider", {}) or {}
            facility_name = manual.get("facilityNameOverride") or provider.get("officialName") or "facility"
            filename = f"{sanitize_filename(str(facility_name))}_assessment_snapshot.pdf"
            self.send_pdf(filename, pdf_bytes)
        except ValueError as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Unable to generate the PDF.", "detail": str(exc)})

    def serve_static(self, requested_path: str) -> None:
        safe_path = unquote(requested_path).split("?", 1)[0]
        if safe_path == "/":
            safe_path = "/index.html"
        file_path = (PUBLIC_DIR / safe_path.lstrip("/")).resolve()
        try:
            file_path.relative_to(PUBLIC_DIR.resolve())
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not file_path.exists() or not file_path.is_file():
            file_path = PUBLIC_DIR / "index.html"
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache" if file_path.name == "index.html" else "public, max-age=3600")
        self.end_headers()
        self.wfile.write(body)


def run() -> None:
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    httpd = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Facility Assessment Report Generator running on http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
