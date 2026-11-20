"""Local server for the viewer with a "New day" button. Local use only.

Run:  .venv/bin/python server.py [--port 8000]   then open http://localhost:8000
Fake: SIM_FAKE=1 .venv/bin/python server.py      (sim runs in free fake mode)
"""
import argparse, json, os, subprocess, sys, threading, time
from urllib.parse import unquote
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = "events_live.json"
LOCK = threading.Lock()
SERVE = {"/", "/index.html", "/events.json", "/events_live.json", "/sample_events.json"}


def env_file():
    vals = {}
    try:
        with open(os.path.join(ROOT, ".env")) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    vals[k.strip().removeprefix("export ").strip()] = v.strip().strip("'\"")
    except OSError:
        pass
    return vals


def has_key():
    return bool(os.environ.get("ANTHROPIC_API_KEY") or env_file().get("ANTHROPIC_API_KEY"))


class Handler(SimpleHTTPRequestHandler):
    def send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def blocked(self):
        # allow list: serve only the files the game needs (macOS paths are case-insensitive, so no block lists)
        return unquote(self.path.split("?", 1)[0]) not in SERVE

    def bad_origin(self):
        # only this page may call the API: reject other Host headers (DNS rebinding) and cross-site Origins (CSRF)
        okhosts = {f"localhost:{self.server.server_port}", f"127.0.0.1:{self.server.server_port}"}
        origin = self.headers.get("Origin")
        return (self.headers.get("Host") not in okhosts
                or (origin is not None and origin.removeprefix("http://") not in okhosts))

    def do_GET(self):
        if self.bad_origin():
            return self.send_error(403)
        if self.path.split("?", 1)[0] == "/api/status":
            return self.send_json(200, {"available": True, "running": LOCK.locked(), "has_key": has_key()})
        if self.blocked():
            return self.send_error(404)
        super().do_GET()

    def do_HEAD(self):
        if self.bad_origin() or self.blocked():
            return self.send_error(404)
        super().do_HEAD()

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/new-day":
            return self.send_error(404)
        if self.bad_origin() or self.headers.get("X-Coffee-Shop") != "new-day":
            return self.send_error(403)  # custom header forces a CORS preflight, which this server never approves
        if not LOCK.acquire(blocking=False):
            return self.send_json(409, {"ok": False, "file": OUT, "exit_code": None, "summary": "A new day is already running."})
        try:
            started = time.time() - 1
            env = dict(os.environ)
            key = env_file().get("ANTHROPIC_API_KEY")
            if key and not env.get("ANTHROPIC_API_KEY"):
                env["ANTHROPIC_API_KEY"] = key
            p = subprocess.run([sys.executable, os.path.join(ROOT, "sim.py"), "--out", os.path.join(ROOT, OUT)],
                               cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            lines = [l for l in p.stdout.splitlines() if l.strip()]
            summary = lines[-1].replace(ROOT + os.sep, "") if lines else ("Run failed (exit %d)." % p.returncode)
            if p.returncode == 1 and not lines and not has_key():
                summary = "ANTHROPIC_API_KEY is not set. Add it to .env and try again."
            out = os.path.join(ROOT, OUT)
            ok = p.returncode == 0 and os.path.isfile(out) and os.path.getmtime(out) >= started
            self.send_json(200, {"ok": ok, "file": OUT, "exit_code": p.returncode, "summary": summary})
        finally:
            LOCK.release()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    port = ap.parse_args().port
    print(f"Serving http://localhost:{port} (127.0.0.1 only). Ctrl+C to stop.")
    ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=ROOT)).serve_forever()
