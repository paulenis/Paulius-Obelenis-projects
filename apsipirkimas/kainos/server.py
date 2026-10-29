"""Local web server: the app page plus a small JSON API.

    python -m kainos.server            # http://localhost:8000, also reachable on the home Wi-Fi
    python -m kainos.server --port 8080
"""

import argparse
import json
import socket
import threading
from datetime import date, datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import collect, storage
from .chains import ALL

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
STALE_AFTER_DAYS = 8
AUTO_COLLECT_AFTER_DAYS = 6   # collect by itself when the newest data is older than this
AUTO_CHECK_EVERY_S = 6 * 3600

_conn = None
_collect_lock = threading.Lock()
_collect_state = {"running": False, "log": []}


def chain_status(conn):
    today = date.today()
    result = []
    for module in ALL:
        ok = storage.last_ok_run(conn, module.NAME)
        last = storage.last_run(conn, module.NAME)
        updated = ok["finished_at"] if ok else None
        age = (today - datetime.fromisoformat(updated).date()).days if updated else None
        failed = bool(last and last["status"] in ("failed", "rejected"))
        result.append({
            "chain": module.NAME,
            "label": module.LABEL,
            "updated_at": updated,
            "count": ok["product_count"] if ok else 0,
            "stale": age is None or age > STALE_AFTER_DAYS,
            "last_error": last["message"] if failed else None,
        })
    return result


def _run_collect():
    def log(line):
        _collect_state["log"].append(line)
        print(line)
    try:
        collect.collect(log=log)
    finally:
        _collect_state["running"] = False


def start_collect():
    with _collect_lock:
        if _collect_state["running"]:
            return False
        _collect_state.update(running=True, log=[])
        threading.Thread(target=_run_collect, daemon=True).start()
        return True


def _auto_collect_loop():
    """Weekly prices without any scheduler: check now and then while the app is running."""
    while True:
        dates = [s["updated_at"] for s in chain_status(_conn)]
        newest = max((d for d in dates if d), default=None)
        if newest is None or (date.today() - datetime.fromisoformat(newest).date()).days >= AUTO_COLLECT_AFTER_DAYS:
            print("Kainos senesnės nei savaitė – renkamos automatiškai...")
            start_collect()
        threading.Event().wait(AUTO_CHECK_EVERY_S)


class Handler(SimpleHTTPRequestHandler):
    # Explicit types: on some Windows machines the registry maps .js to text/plain.
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, fmt, *args):
        pass  # keep the console quiet; errors still surface as responses

    def end_headers(self):
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}") if length else {}

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/status":
            return self._json({"chains": chain_status(_conn), "collecting": _collect_state["running"]})
        if url.path == "/api/search":
            q = parse_qs(url.query).get("q", [""])[0]
            return self._json({"results": storage.search(_conn, q, today=date.today().isoformat())})
        if url.path == "/api/list":
            return self._json({"items": storage.list_items(_conn)})
        if url.path == "/api/collect":
            return self._json(_collect_state)
        return super().do_GET()

    def do_POST(self):
        url = urlparse(self.path)
        try:
            body = self._body()
        except json.JSONDecodeError:
            return self._json({"error": "netinkamas JSON"}, HTTPStatus.BAD_REQUEST)
        if url.path == "/api/list/sync":
            storage.merge_list_items(_conn, body.get("items") or [])
            return self._json({"items": storage.list_items(_conn)})
        if url.path == "/api/collect":
            start_collect()
            return self._json(_collect_state)
        return self._json({"error": "nežinomas adresas"}, HTTPStatus.NOT_FOUND)


def _lan_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.0.1", 80))  # no packet is sent; this only picks the Wi-Fi interface
            return s.getsockname()[0]
    except OSError:
        return None


def main(argv=None):
    global _conn
    parser = argparse.ArgumentParser(description="Paleisti apsipirkimo programą")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-auto", action="store_true", help="nerinkti kainų automatiškai")
    args = parser.parse_args(argv)
    _conn = storage.connect()
    if not args.no_auto:
        threading.Thread(target=_auto_collect_loop, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    lan = _lan_address()
    print(f"Programa veikia: http://localhost:{args.port}")
    if lan:
        print(f"Telefone (tas pats Wi-Fi): http://{lan}:{args.port}")
    print("Sustabdyti: Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSustabdyta.")


if __name__ == "__main__":
    main()
