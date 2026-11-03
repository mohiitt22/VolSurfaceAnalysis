"""Local-only desk server.

Serves the docs site and lets the page pick a data file from this project.
Nothing here is published.
"""

from __future__ import annotations

import cgi
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


def _err(exc: Exception) -> dict:
    tb = traceback.extract_tb(exc.__traceback__)
    frame = tb[-1] if tb else None
    where = f"{Path(frame.filename).name}:{frame.lineno} in {frame.name}" if frame else type(exc).__name__
    return {"ok": False, "where": where, "error": f"{type(exc).__name__}: {exc}"}


def _json_response(handler: SimpleHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()
    handler.wfile.write(body)


def fly_active_folder():
    import fly_source

    folder = fly_source.load_active_folder()
    if folder is None:
        discovered = fly_source.discover_folders()
        if discovered:
            folder = fly_source.resolve_folder(discovered[0]["path"])
            fly_source.save_active_folder(folder)
    return folder


def handle_fly_get(path: str, query: dict) -> dict:
    import fly_source

    if path == "/api/fly/folders":
        active = fly_source.load_active_folder()
        return {
            "ok": True,
            "folders": fly_source.discover_folders(),
            "active": None
            if active is None
            else (
                active.relative_to(ROOT).as_posix()
                if str(active).startswith(str(ROOT))
                else str(active)
            ),
        }
    if path == "/api/fly/set_folder":
        folder = fly_source.resolve_folder(query.get("path", [""])[0])
        fly_source.save_active_folder(folder)
        dates = fly_source.list_dates(folder)
        return {
            "ok": True,
            "path": query.get("path", [""])[0],
            "dates": dates,
            "count": len(dates),
            "first": dates[0] if dates else None,
            "last": dates[-1] if dates else None,
        }
    folder = fly_active_folder()
    if folder is None:
        return {"ok": False, "error": "No SNP parquet folder is selected yet."}
    if path == "/api/fly/dates":
        dates = fly_source.list_dates(folder)
        return {"ok": True, "path": str(folder), "dates": dates, "count": len(dates)}
    if path == "/api/fly/meta":
        day = query.get("date", [""])[0]
        target = float(query.get("target_dte", ["60"])[0] or 60)
        meta = fly_source.day_meta(folder, day, target_dte=target)
        meta["ok"] = True
        meta["path"] = str(folder)
        return meta
    if path == "/api/fly/compare":
        date_a = query.get("date_a", [""])[0]
        date_b = query.get("date_b", [""])[0]
        hour = query.get("hour", [None])[0] or None
        expiry_a = query.get("expiry_a", [None])[0] or None
        expiry_b = query.get("expiry_b", [None])[0] or None
        target = float(query.get("target_dte", ["60"])[0] or 60)
        wing = float(query.get("wing", ["100"])[0] or 100)
        spread = query.get("spread_width", [None])[0]
        spread_width = float(spread) if spread not in (None, "") else None
        return fly_source.compare(
            folder,
            date_a,
            date_b,
            hour=hour,
            expiry_a=expiry_a or None,
            expiry_b=expiry_b or None,
            target_dte=target,
            wing=wing,
            spread_width=spread_width,
        )
    if path == "/api/fly/hold":
        start = query.get("start_date", [""])[0]
        hold_days = int(query.get("hold_days", ["10"])[0] or 10)
        hour = query.get("hour", [None])[0] or None
        expiry = query.get("expiry", [None])[0] or None
        target = float(query.get("target_dte", ["60"])[0] or 60)
        wing = float(query.get("wing", ["100"])[0] or 100)
        spread = query.get("spread_width", [None])[0]
        spread_width = float(spread) if spread not in (None, "") else None
        return fly_source.hold_path(
            folder,
            start,
            hold_days=hold_days,
            hour=hour,
            expiry=expiry or None,
            target_dte=target,
            wing=wing,
            spread_width=spread_width,
        )
    return {"ok": False, "error": f"Unknown fly endpoint {path}"}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCS), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/fly/"):
            try:
                payload = handle_fly_get(parsed.path, parse_qs(parsed.query))
            except Exception as exc:
                payload = _err(exc)
            _json_response(self, payload)
            return
        if parsed.path == "/api/prepare":
            from prepare_source import prepare
            query = parse_qs(parsed.query)
            rel = query.get("path", [""])[0]
            tab = query.get("tab", ["strategy"])[0]
            try:
                body = prepare(rel, tab)
            except Exception as exc:
                body = _err(exc)
            _json_response(self, body)
            return
        if parsed.path == "/api/catalog":
            _json_response(self, catalog())
            return
        if parsed.path == "/api/inspect":
            rel = parse_qs(parsed.query).get("path", [""])[0]
            _json_response(self, inspect(rel))
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

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/fly/set_folder":
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
                import fly_source

                folder = fly_source.resolve_folder(payload.get("path"))
                fly_source.save_active_folder(folder)
                dates = fly_source.list_dates(folder)
                _json_response(
                    self,
                    {
                        "ok": True,
                        "path": payload.get("path"),
                        "dates": dates,
                        "count": len(dates),
                        "first": dates[0] if dates else None,
                        "last": dates[-1] if dates else None,
                    },
                )
            except Exception as exc:
                _json_response(self, _err(exc))
            return
        if parsed.path == "/api/fly/upload":
            try:
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={
                        "REQUEST_METHOD": "POST",
                        "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                    },
                )
                files = []
                label = None
                if "label" in form:
                    label = form.getvalue("label")
                items = form["file"] if "file" in form else []
                if not isinstance(items, list):
                    items = [items]
                for item in items:
                    if not getattr(item, "filename", None):
                        continue
                    files.append((item.filename, item.file.read()))
                import fly_source

                _json_response(self, fly_source.receive_uploads(files, label=label))
            except Exception as exc:
                _json_response(self, _err(exc))
            return
        self.send_response(404)
        self.end_headers()


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Local desk: http://{HOST}:{PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
