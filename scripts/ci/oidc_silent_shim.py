#!/usr/bin/env python3
"""The journeys run's identity provider answers a silent try the way Entra ID does (BLD-A197; L-AUTH.rules/1).

The dev mock (navikt/mock-oauth2-server, interactive login) shows its own login form for every `GET /authorize`,
`prompt=none` included. A real provider never shows anything for `prompt=none`: a browser with no session there
is sent straight back to `redirect_uri` with `error=login_required` (OIDC Core 3.1.2.6), and the app shows S-02.
The journeys' browser is always new, so that is the answer it should get. This proxy sits where the browser and
the stack's health check reach the provider and gives that answer; every other request (discovery, the login
form, its post, sign-out) goes on to the mock unchanged, with the browser's Host header, so the mock's issuer
stays the one the app checks. The web container reaches the mock inside Docker and never comes through here.

Usage:  python3 scripts/ci/oidc_silent_shim.py --listen 8090 --upstream 8091

Only the journeys workflow runs it. The gates' end-to-end tests keep the mock's form for a silent try, which
stands in for single sign-on answering at once (e2e/landing.spec.ts, V-ACC.share/1). Standard library only. It
logs no request: addresses carry the sign-in state and codes.
"""

from __future__ import annotations

import argparse
import contextlib
import http.client
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

# Headers that belong to one connection, not to the request or response (RFC 9110 7.6.1).
HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "proxy-connection",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)


def silent_answer(method: str, path: str) -> str | None:
    """Where a provider with no session sends a `prompt=none` authorisation request, or None to pass it on."""
    parts = urlsplit(path)
    if method != "GET" or not parts.path.endswith("/authorize"):
        return None
    query = parse_qs(parts.query)
    if "none" not in " ".join(query.get("prompt", [])).split():
        return None
    redirect_uri = (query.get("redirect_uri") or [""])[0]
    if not redirect_uri:
        return None  # nowhere to send it back: the mock answers its own error
    back = {"error": "login_required"}
    if query.get("state"):
        back["state"] = query["state"][0]
    return f"{redirect_uri}{'&' if '?' in redirect_uri else '?'}{urlencode(back)}"


class _Handler(BaseHTTPRequestHandler):
    upstream_port = 0

    def _relay(self) -> None:
        location = silent_answer(self.command, self.path)
        if location is not None:
            self.send_response(302)
            self.send_header("Location", location)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        try:
            conn = http.client.HTTPConnection("127.0.0.1", self.upstream_port, timeout=30)
            conn.request(self.command, self.path, body=body, headers=headers)
            res = conn.getresponse()
            data = res.read()
            conn.close()
        except OSError as err:
            # While `make up` is still starting the mock, the health check retries on this answer.
            print(f"oidc-shim: upstream {type(err).__name__}", file=sys.stderr, flush=True)
            self.send_error(502)
            return
        self.send_response(res.status, res.reason)
        for name, value in res.getheaders():
            if name.lower() not in HOP_BY_HOP | {"content-length", "date", "server"}:
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    do_GET = do_POST = do_HEAD = do_OPTIONS = do_PUT = do_DELETE = _relay

    def log_message(self, format: str, *args: object) -> None:
        return  # no addresses in the log (they carry state and codes)


class _V6(ThreadingHTTPServer):
    address_family = socket.AF_INET6


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--listen", type=int, required=True)
    parser.add_argument("--upstream", type=int, required=True)
    args = parser.parse_args(argv)
    _Handler.upstream_port = args.upstream
    # Loopback only, on IPv4 and (where the runner has it) IPv6, since `localhost` may resolve to either.
    servers: list[ThreadingHTTPServer] = [ThreadingHTTPServer(("127.0.0.1", args.listen), _Handler)]
    with contextlib.suppress(OSError):
        servers.append(_V6(("::1", args.listen), _Handler))
    for server in servers:
        server.daemon_threads = True
    for server in servers[1:]:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"oidc-shim: localhost:{args.listen} -> 127.0.0.1:{args.upstream}", file=sys.stderr, flush=True)
    servers[0].serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
