from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


class HoneypotHandler(BaseHTTPRequestHandler):
    server_version = "CerberusHoneypot/0.1"

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
        parsed = urlparse(self.path)
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length) if length > 0 else b""
        print(
            f"[honeypot] method=POST path={parsed.path} length={len(body)} "
            f"client={self.client_address[0]}",
            flush=True,
        )
        if body:
            try:
                preview = body.decode("utf-8", errors="replace")
            except Exception:
                preview = repr(body[:256])
            print(f"[honeypot] body={preview[:512]}", flush=True)

        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"honeypot-ok\n")

    def log_message(self, fmt: str, *args: object) -> None:
        # Keep output focused on captured payloads and status checks.
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local exfiltration honeypot server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), HoneypotHandler)
    print(f"[honeypot] listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
