#!/usr/bin/env python3
"""Brand Video Studio: a local web app over the skill.
usage: python3 app/server.py [--port 4410] [--no-open]

It listens only on this computer and runs your own Claude Code. Data lives in ~/BrandVideoStudio, or BVS_HOME."""
import argparse
import json
import mimetypes
import re
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, str(Path(__file__).parent))
import studio  # noqa: E402

WEB = Path(__file__).parent / "web"
FONTS = studio.SKILL / "assets" / "fonts"
mimetypes.add_type("video/mp4", ".m4v")
mimetypes.add_type("image/svg+xml", ".svg")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def local(self):
        # Blocks pages on other sites from reaching this server through the browser.
        host = self.headers.get("Host", "").rsplit(":", 1)[0]
        return host in ("127.0.0.1", "localhost")

    def reply(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_path(self, path, roots):
        path = Path(path).resolve()
        if not path.is_file() or not any(path.is_relative_to(r.resolve()) for r in roots):
            return self.reply({"error": "Not found"}, 404)
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        wanted = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if wanted and size:
            first, last = wanted.groups()
            start = int(first) if first else max(0, size - int(last or 0))
            end = min(int(last), size - 1) if first and last else end
            status = 206
        self.send_response(status)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as source:
            source.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    chunk = source.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True

    def body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def guarded(self, action):
        if not self.local():
            return self.reply({"error": "Forbidden"}, 403)
        if self.command != "GET" and self.headers.get("X-Studio") != "1":
            return self.reply({"error": "Forbidden"}, 403)
        try:
            action()
        except KeyError:
            self.reply({"error": "Not found"}, 404)
        except ValueError as error:
            self.reply({"error": str(error)}, 400)
        except Exception as error:
            self.reply({"error": str(error)}, 500)

    def do_GET(self):
        self.guarded(self.get)

    def do_POST(self):
        self.guarded(self.post)

    def do_PUT(self):
        self.guarded(self.put)

    def get(self):
        url = urlparse(self.path)
        parts = [unquote(p) for p in url.path.strip("/").split("/")]
        match parts:
            case [""]:
                self.send_path(WEB / "index.html", [WEB])
            case ["web", name]:
                self.send_path(WEB / name, [WEB])
            case ["fonts", name]:
                self.send_path(FONTS / name, [FONTS])
            case ["api", "health"]:
                self.reply(studio.health())
            case ["api", "brands"]:
                self.reply(studio.list_brands())
            case ["api", "projects"]:
                self.reply(studio.list_projects())
            case ["api", "projects", pid]:
                after = int(parse_qs(url.query).get("after", ["0"])[0])
                self.reply({**studio.detail(pid), "activity": studio.activity(pid, after)})
            case ["files", "brand", bid, "assets", name]:
                root = studio.brands_dir() / studio.safe_id(bid) / "assets"
                self.send_path(root / name, [root])
            case ["files", "project", pid, "renders", name]:
                root = studio.project_dir(pid) / "renders"
                self.send_path(root / name, [root])
            case _:
                self.reply({"error": "Not found"}, 404)

    def post(self):
        parts = [unquote(p) for p in urlparse(self.path).path.strip("/").split("/")]
        match parts:
            case ["api", "brands"]:
                self.reply(studio.save_brand(self.body()), 201)
            case ["api", "brands", bid]:
                self.reply(studio.save_brand(self.body(), bid))
            case ["api", "brands", bid, "palette"]:
                self.reply(studio.palette(bid))
            case ["api", "projects"]:
                self.reply(studio.create_project(self.body()), 201)
            case ["api", "brands-import"]:
                self.reply(studio.import_brand(self.body().get("folder")), 201)
            case ["api", "pick-folder"]:
                self.reply(studio.pick_folder())
            case ["api", "folder"]:
                data = self.body()
                self.reply(studio.describe_folder(data.get("path", ""), data.get("kind", "video")))
            case ["api", "projects", pid, action]:
                self.action(pid, action, self.body())
                self.reply(studio.detail(pid))
            case _:
                self.reply({"error": "Not found"}, 404)

    def action(self, pid, action, data):
        match action:
            case "propose":
                studio.start_propose(pid, data.get("changes", ""))
            case "build":
                studio.start_build(pid, data.get("names", []), data.get("first_only", True), data.get("answers", ""))
            case "rest":
                studio.make_rest(pid)
            case "revise":
                studio.revise(pid, data.get("name", ""), data.get("note", ""))
            case "resume":
                studio.resume(pid)
            case "stop":
                studio.jobs.stop(pid)
            case "edit":
                studio.update(pid, request=data.get("request", ""), format=data.get("format", "9:16"), count=data.get("count") or None)
            case _:
                raise KeyError(action)

    def put(self):
        parts = [unquote(p) for p in urlparse(self.path).path.strip("/").split("/")]
        length = int(self.headers.get("Content-Length", 0))
        match parts:
            case ["api", "projects", pid, "footage", name]:
                self.reply({"name": studio.add_footage(pid, name, self.rfile, length)}, 201)
            case ["api", "brands", bid, "logo", name]:
                self.reply(studio.set_logo(bid, name, self.rfile, length))
            case _:
                self.reply({"error": "Not found"}, 404)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=4410)
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    studio.recover()
    server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}"
    print(f"Brand Video Studio is running at {url}\nData: {studio.HOME}\nPress Ctrl+C to stop.")
    if not a.no_open:
        threading.Timer(0.4, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
