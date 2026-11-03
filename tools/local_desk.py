"""Local-only desk server.

Serves the docs site and lets the page pick a data file from this project.
Nothing here is published.
"""

from __future__ import annotations

import json
import sys
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
sys.path.insert(0, str(Path(__file__).resolve().parent))
SKIP_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    ".vercel",
    ".cache",
    "SNP data",
}
HOST = "127.0.0.1"
PORT = 8765


def safe_path(rel: str) -> Path:
    rel = (rel or "").replace("\\", "/").lstrip("/")
    if not rel or ".." in Path(rel).parts:
        raise ValueError("Path is empty or leaves the project folder.")
    path = (ROOT / rel).resolve()
    if ROOT not in path.parents and path != ROOT:
        raise ValueError(f"Path is outside the project: {rel}")
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {rel}")
    return path


def classify_json(payload) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise ValueError(
            "JSON root is not an object. Desk, distribution, and surface files are all objects."
        )
    keys = list(payload.keys())
    if "all_dates" in payload and "dates_data" in payload:
        n = len(payload.get("all_dates") or [])
        return "surface", f"Surface file with {n} dates."
    if "rows" in payload and "dates" in payload and isinstance(payload.get("meta"), dict):
        meta = payload["meta"]
        needed = [k for k in ("train_end", "test_date", "frozen_z") if k not in meta]
        if needed:
            raise ValueError(
                "Desk panel meta is missing "
                + ", ".join(needed)
                + f". Meta keys present: {list(meta.keys())}"
            )
        if not isinstance(payload["rows"], list) or not payload["rows"]:
            raise ValueError("Desk panel has no rows to analyse.")
        if not isinstance(payload["dates"], list) or not payload["dates"]:
            raise ValueError("Desk panel has no dates.")
        return "desk", f"Relative-value panel, {len(payload['dates'])} dates, {len(payload['rows'])} rows."
    if isinstance(payload.get("meta"), dict) and "primary_structure" in payload["meta"]:
        return "distribution", "Historical distribution file."
    raise ValueError(
        "Unrecognised JSON. A desk file needs meta, dates, and rows. "
        "A surface file needs all_dates and dates_data. "
        f"This file has keys: {keys[:12]}"
    )


def inspect_table(path: Path) -> tuple[str, str]:
    sys.path.insert(0, str(ROOT))
    try:
        from spx_butterfly.data_loader import load_raw_dataset, transform_to_long_form
        from spx_butterfly.data_validation import validate_surface_data
    except Exception as exc:
        raise RuntimeError(
            f"Could not import spx_butterfly.data_loader ({exc}). "
            "Run this server with the project virtualenv."
        ) from exc
    frame = load_raw_dataset(path)
    long_frame = transform_to_long_form(frame)
    report = validate_surface_data(long_frame)
    if report["errors"]:
        raise ValueError("validate_surface_data: " + "; ".join(report["errors"]))
    dates = long_frame["date"].nunique()
    warning = ""
    if report["warnings"]:
        warning = " Warnings: " + "; ".join(report["warnings"])
    raise ValueError(
        "The workbook itself loads "
        f"({dates} dates, {len(long_frame)} rows). "
        "The butterfly lab then reads DATA.dates_data in docs/surface/index.html, "
        "and this file has no dates_data object. "
        "Use a precalculated surface JSON for that lab, or a panel.json for the relative-value desk."
        + warning
    )


def inspect(rel: str) -> dict:
    try:
        path = safe_path(rel)
    except Exception as exc:
        return {"ok": False, "where": "tools/local_desk.py safe_path", "error": str(exc)}
    try:
        suffix = path.suffix.lower()
        if suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            kind, summary = classify_json(payload)
            return {"ok": True, "kind": kind, "summary": summary, "where": "json classification", "path": rel}
        if suffix in {".xlsx", ".xls", ".csv"}:
            inspect_table(path)
        return {
            "ok": False,
            "where": "tools/local_desk.py inspect",
            "error": f"Unsupported file type {suffix or '(none)'}. Use .json, .csv, or .xlsx.",
        }
    except Exception as exc:
        tb = traceback.extract_tb(exc.__traceback__)
        frame = tb[-1] if tb else None
        if frame:
            try:
                rel_file = Path(frame.filename).resolve().relative_to(ROOT).as_posix()
            except ValueError:
                rel_file = frame.filename
            where = f"{rel_file}:{frame.lineno} in {frame.name}"
        else:
            where = type(exc).__name__
        return {"ok": False, "where": where, "error": f"{type(exc).__name__}: {exc}"}


def catalog() -> list[dict]:
    from prepare_source import source_catalog
    return source_catalog()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCS), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/prepare":
            from prepare_source import prepare
            query = parse_qs(parsed.query)
            rel = query.get("path", [""])[0]
            tab = query.get("tab", ["strategy"])[0]
            try:
                body = json.dumps(prepare(rel, tab)).encode("utf-8")
            except Exception as exc:
                tb = traceback.extract_tb(exc.__traceback__)
                frame = tb[-1] if tb else None
                where = f"{Path(frame.filename).name}:{frame.lineno} in {frame.name}" if frame else type(exc).__name__
                body = json.dumps({"ok": False, "where": where, "error": f"{type(exc).__name__}: {exc}"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/catalog":
            body = json.dumps(catalog()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/inspect":
            rel = parse_qs(parsed.query).get("path", [""])[0]
            body = json.dumps(inspect(rel)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/raw":
            rel = parse_qs(parsed.query).get("path", [""])[0]
            try:
                path = safe_path(rel)
            except Exception as exc:
                message = str(exc).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(message)
                return
            data = path.read_bytes()
            kind = "application/json" if path.suffix.lower() == ".json" else "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.end_headers()
            self.wfile.write(data)
            return
        return super().do_GET()


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Local desk: http://{HOST}:{PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
