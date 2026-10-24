"""Outbound HTTP for URLs that come from untrusted data (RSS feeds, API responses).

Guards against server-side request forgery and runaway downloads:
- every TCP connection (including each redirect hop) resolves the host itself and refuses
  non-public addresses (loopback, private, link-local, cloud metadata, docker network, ...)
  and then connects to the address it just checked, so DNS rebinding cannot swap it afterwards;
- the response body is read with a hard size cap (measured after decompression);
- redirects are limited and total time is bounded.
"""
import asyncio
import ipaddress
import socket
from dataclasses import dataclass

import httpcore
import httpx

MAX_REDIRECTS = 5


class UnsafeURLError(httpx.HTTPError):
    """Raised for blocked addresses, oversized bodies and other policy failures."""


def _ip_allowed(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


async def _resolve_public(host: str, port: int) -> str:
    try:
        candidates = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as e:
            raise UnsafeURLError(f"Could not resolve {host}: {e}") from e
        candidates = [ipaddress.ip_address(i[4][0].split("%")[0]) for i in infos]
    if not candidates:
        raise UnsafeURLError(f"Could not resolve {host}")
    # One private answer is enough to refuse: a host that mixes public and internal records is a red flag.
    if not all(_ip_allowed(ip) for ip in candidates):
        raise UnsafeURLError("That address is not allowed (it points at a private or internal network).")
    return str(candidates[0])


class _GuardedBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, inner):
        self._inner = inner

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        ip = await _resolve_public(host, port)
        return await self._inner.connect_tcp(ip, port, timeout=timeout, local_address=local_address,
                                             socket_options=socket_options)

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise UnsafeURLError("Unix sockets are not allowed.")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


def _transport() -> httpx.AsyncHTTPTransport:
    transport = httpx.AsyncHTTPTransport(retries=0)
    pool = transport._pool
    backend = getattr(pool, "_network_backend", None)
    if backend is None:  # httpx internals changed: fail closed rather than fetch unguarded
        raise RuntimeError("safe_http cannot install its address guard with this httpx version")
    pool._network_backend = _GuardedBackend(backend)
    return transport


@dataclass
class FetchResult:
    status_code: int
    headers: httpx.Headers
    content: bytes
    encoding: str | None = None

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding or "utf-8", errors="replace")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise UnsafeURLError(f"The server answered HTTP {self.status_code}")


async def safe_get(url: str, *, max_bytes: int, headers: dict | None = None, timeout: float = 30,
                   total_timeout: float = 90) -> FetchResult:
    if not url.lower().startswith(("http://", "https://")):
        raise UnsafeURLError("Only http and https URLs are allowed.")
    async with httpx.AsyncClient(transport=_transport(), headers=headers, timeout=timeout,
                                 follow_redirects=True, max_redirects=MAX_REDIRECTS) as client:
        try:
            async with asyncio.timeout(total_timeout):
                async with client.stream("GET", url) as r:
                    declared = r.headers.get("content-length", "")
                    if declared.isdigit() and int(declared) > max_bytes:
                        raise UnsafeURLError(f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.")
                    body = bytearray()
                    async for chunk in r.aiter_bytes():
                        body += chunk
                        if len(body) > max_bytes:
                            raise UnsafeURLError(f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.")
                    return FetchResult(r.status_code, r.headers, bytes(body), r.encoding)
        except TimeoutError as e:
            raise UnsafeURLError("The request took too long.") from e
