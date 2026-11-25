"""Keeps users' model requests on the public internet.

The server sits in a private network, and a user chooses the model address, so without this check a user
could make the server call its own neighbours. For anyone but an administrator, the host is resolved here,
every address must be public, and the connection is pinned to the checked address (Host header and TLS
name unchanged), so a second DNS answer cannot point it elsewhere. Redirects are never followed.
"""

from collections.abc import Callable
import ipaddress
import socket

import httpx

from backend.shared import scope as scopes
from backend.shared.errors import ModelConfigurationError

Resolver = Callable[[str, int], list[str]]


def resolve(host: str, port: int) -> list[str]:
    return list(dict.fromkeys(info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))


def parse_networks(text: str) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    return tuple(ipaddress.ip_network(part.strip()) for part in text.split(",") if part.strip())


def is_public(address: str, also_allowed=()) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (ip.is_global and not ip.is_multicast) or any(ip in network for network in also_allowed)


class PublicAddressTransport(httpx.BaseTransport):
    def __init__(self, inner: httpx.BaseTransport, resolver: Resolver = resolve, also_allowed=()):
        """`also_allowed`: extra networks treated as public, e.g. a proxy's fake-IP range (198.18.0.0/15)."""
        self.inner = inner
        self.resolver = resolver
        self.also_allowed = tuple(also_allowed)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        scope = scopes.current()
        if scope is not None and scope.is_admin:
            return self.inner.handle_request(request)
        host = request.url.host
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        try:
            addresses = self.resolver(host, port)
        except (OSError, UnicodeError) as error:
            raise httpx.ConnectError(f"无法解析模型地址 {host}", request=request) from error
        if not addresses or not all(is_public(address, self.also_allowed) for address in addresses):
            raise ModelConfigurationError("模型地址必须是公网地址，不能指向内网或本机")
        if request.url.scheme == "https":
            request.extensions = {**request.extensions, "sni_hostname": host}
        request.url = request.url.copy_with(host=addresses[0])
        return self.inner.handle_request(request)

    def close(self) -> None:
        self.inner.close()
