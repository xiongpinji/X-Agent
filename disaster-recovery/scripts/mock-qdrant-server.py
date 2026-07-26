#!/usr/bin/env python3
"""Mock Qdrant server for P1-17 restore drills (no real cluster available).

Implements the official snapshot API subset used by deployment/backup/backup.sh
and disaster-recovery/scripts/restore-qdrant.sh:

  GET    /collections                                   -> list collections
  GET    /collections/{name}                            -> info (points_count)
  POST   /collections/{name}/snapshots                  -> create snapshot
  GET    /collections/{name}/snapshots/{file}           -> download snapshot
  POST   /collections/{name}/snapshots/upload           -> restore (multipart field "snapshot")
  DELETE /collections/{name}                            -> delete collection
  GET    /healthz                                       -> liveness

State is kept in memory + snapshots persisted under --data-dir so that a
"disaster" (process restart / collection delete) followed by restore can be
verified by comparing points_count.

Usage: python mock-qdrant-server.py --port 16333 --data-dir <dir> --seed-points 42
"""
import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATE = {"collections": {}, "data_dir": Path(".")}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj=None, raw=None):
        body = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json" if raw is None else "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # quiet
        pass

    def do_GET(self):
        parts = [p for p in self.path.split("/") if p]
        if self.path == "/healthz":
            return self._send(200, {"status": "ok"})
        if parts == ["collections"]:
            names = [{"name": n} for n in STATE["collections"]]
            return self._send(200, {"result": {"collections": names}, "status": "ok"})
        if len(parts) == 2 and parts[0] == "collections":
            c = STATE["collections"].get(parts[1])
            if not c:
                return self._send(404, {"status": {"error": "not found"}})
            return self._send(200, {"result": {"status": "green", "points_count": c["points_count"]}, "status": "ok"})
        if len(parts) == 4 and parts[0] == "collections" and parts[2] == "snapshots":
            f = STATE["data_dir"] / parts[3]
            if not f.exists():
                return self._send(404, {"status": {"error": "snapshot not found"}})
            return self._send(200, raw=f.read_bytes())
        return self._send(404, {"status": {"error": "unknown route"}})

    def do_POST(self):
        parts = [p for p in self.path.split("?")[0].split("/") if p]
        if len(parts) == 3 and parts[0] == "collections" and parts[2] == "snapshots":
            c = STATE["collections"].get(parts[1])
            if not c:
                return self._send(404, {"status": {"error": "not found"}})
            snap_name = f"{parts[1]}-{time.strftime('%Y-%m-%d_%H-%M-%S')}.snapshot"
            payload = json.dumps({"collection": parts[1], "points_count": c["points_count"]}).encode()
            (STATE["data_dir"] / snap_name).write_bytes(payload)
            return self._send(200, {"result": {"name": snap_name, "size": len(payload)}, "status": "ok"})
        if len(parts) == 4 and parts[0] == "collections" and parts[2] == "snapshots" and parts[3] == "upload":
            # real Qdrant: POST /collections/{name}/snapshots/upload, multipart field "snapshot"
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            # extract JSON payload embedded in multipart (mock snapshots are JSON docs)
            start = body.find(b'{"collection"')
            end = body.rfind(b"}") + 1
            if start == -1 or end <= start:
                return self._send(400, {"status": {"error": "bad snapshot payload"}})
            data = json.loads(body[start:end].decode())
            STATE["collections"][parts[1]] = {"points_count": data["points_count"]}
            return self._send(200, {"result": {"name": parts[1]}, "status": "ok"})
        return self._send(404, {"status": {"error": "unknown route"}})

    def do_DELETE(self):
        parts = [p for p in self.path.split("/") if p]
        if len(parts) == 2 and parts[0] == "collections":
            if parts[1] not in STATE["collections"]:
                return self._send(404, {"status": {"error": "not found"}})
            del STATE["collections"][parts[1]]
            return self._send(200, {"result": True, "status": "ok"})
        return self._send(404, {"status": {"error": "unknown route"}})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=16333)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--seed-collection", default="xagent_memory")
    ap.add_argument("--seed-points", type=int, default=42)
    a = ap.parse_args()
    STATE["data_dir"] = Path(a.data_dir)
    STATE["data_dir"].mkdir(parents=True, exist_ok=True)
    if a.seed_points > 0:
        STATE["collections"][a.seed_collection] = {"points_count": a.seed_points}
    print(f"mock-qdrant listening on {a.port}, seeded {a.seed_collection}={a.seed_points} points", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
