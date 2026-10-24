"""Unit tests for safe_http (SSRF guard, size caps, redirects) and feed XML hardening.

Pure unit tests: they start throw-away local HTTP servers and need no Mongo or running app.
"""
import asyncio
import gzip
import ipaddress
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "unit_test")
os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("MEDIA_DIR", "/tmp/podcast-producer-unit-media")

import safe_http  # noqa: E402
from safe_http import UnsafeURLError, safe_get  # noqa: E402


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "192.168.1.10", "172.16.5.4", "169.254.169.254",
                                "100.64.0.1", "0.0.0.0", "::1", "fc00::1", "fe80::1", "::ffff:127.0.0.1",
                                "224.0.0.1"])
def test_internal_addresses_are_blocked(ip):
    assert not safe_http._ip_allowed(ipaddress.ip_address(ip))


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"])
def test_public_addresses_are_allowed(ip):
    assert safe_http._ip_allowed(ipaddress.ip_address(ip))


class _Handler(BaseHTTPRequestHandler):
    other_port = 0

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/small":
            body = b"hello"
        elif self.path == "/big":
            body = b"x" * (2 * 1024 * 1024)
        elif self.path == "/gzip-bomb":
            body = gzip.compress(b"\0" * (50 * 1024 * 1024))
            self.send_response(200)
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        elif self.path == "/redirect-internal":
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.2:{self.other_port}/small")
            self.end_headers()
            return
        elif self.path == "/redirect-ok":
            self.send_response(302)
            self.send_header("Location", "/small")
            self.end_headers()
            return
        elif self.path == "/redirect-file":
            self.send_response(302)
            self.send_header("Location", "file:///etc/passwd")
            self.end_headers()
            return
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def servers():
    internal = ThreadingHTTPServer(("127.0.0.2", 0), _Handler)
    _Handler.other_port = internal.server_address[1]
    main = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    for s in (internal, main):
        threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{main.server_address[1]}"
    for s in (internal, main):
        s.shutdown()


def test_loopback_is_refused_by_default(servers):
    for url in (servers + "/small", servers.replace("127.0.0.1", "localhost") + "/small"):
        with pytest.raises(UnsafeURLError):
            run(safe_get(url, max_bytes=1024))


def test_non_http_schemes_are_refused():
    for url in ("file:///etc/passwd", "ftp://example.com/x", "gopher://example.com"):
        with pytest.raises(UnsafeURLError):
            run(safe_get(url, max_bytes=1024))


@pytest.fixture
def allow_only_127_0_0_1(monkeypatch):
    monkeypatch.setattr(safe_http, "_ip_allowed", lambda ip: str(ip) == "127.0.0.1")


def test_small_download_works(servers, allow_only_127_0_0_1):
    r = run(safe_get(servers + "/small", max_bytes=1024))
    assert r.status_code == 200 and r.content == b"hello"


def test_size_cap(servers, allow_only_127_0_0_1):
    with pytest.raises(UnsafeURLError):
        run(safe_get(servers + "/big", max_bytes=1024 * 1024))


def test_gzip_bomb_is_capped_after_decompression(servers, allow_only_127_0_0_1):
    with pytest.raises(UnsafeURLError):
        run(safe_get(servers + "/gzip-bomb", max_bytes=1024 * 1024))


def test_redirect_to_internal_address_is_blocked(servers, allow_only_127_0_0_1):
    with pytest.raises(UnsafeURLError):
        run(safe_get(servers + "/redirect-internal", max_bytes=1024))


def test_redirect_to_allowed_address_is_followed(servers, allow_only_127_0_0_1):
    assert run(safe_get(servers + "/redirect-ok", max_bytes=1024)).content == b"hello"


def test_redirect_to_file_scheme_is_refused(servers, allow_only_127_0_0_1):
    with pytest.raises(Exception):
        run(safe_get(servers + "/redirect-file", max_bytes=1024))


def test_feed_parser_rejects_entity_expansion():
    from defusedxml import DefusedXmlException
    from rss_import import parse_feed
    bomb = (b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>'
            b"<rss><channel><item><title>&b;</title></item></channel></rss>")
    with pytest.raises(DefusedXmlException):
        parse_feed(bomb)


def test_feed_parser_still_parses_normal_feeds():
    from rss_import import parse_feed
    xml = (b'<?xml version="1.0"?><rss version="2.0"><channel><item><title>Ep 1</title><guid>g1</guid>'
           b"<description>Hi</description></item></channel></rss>")
    items = parse_feed(xml)
    assert items[0]["title"] == "Ep 1" and items[0]["guid"] == "g1"
