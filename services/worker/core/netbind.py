"""Where the worker's API listens (DEC-096 review, BLD-C017).

The worker shares two networks: the default one (Postgres, the store, the web app) and `speech`, an internal network
with the isolated speech service only. The API must not be reachable from the speech service, so instead of
0.0.0.0 it listens on 127.0.0.1 (the container's health check) and on its own address on the default network.
That address is found by resolving a peer that lives only on the default network (`WORKER_API_BIND_PEER`,
`postgres` in compose) and picking the local interface on the same subnet. Without a peer it listens on 0.0.0.0
(host-side runs and tests). If a peer is set but no interface matches, the worker refuses to start: binding
everywhere would quietly open the API to the speech network again.
"""

from __future__ import annotations

import ipaddress
import socket
import struct
import sys
import time

SIOCGIFADDR = 0x8915
SIOCGIFNETMASK = 0x891B


class BindError(RuntimeError):
    """No local address shares a subnet with the peer. `code` is safe to log."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def pick_address(peer_ip: str, interfaces: list[tuple[str, str]]) -> str | None:
    """The local IPv4 address whose subnet holds `peer_ip`, from (address, netmask) pairs; None if none does."""
    peer = ipaddress.IPv4Address(peer_ip)
    for address, mask in interfaces:
        net = ipaddress.IPv4Network(f"{address}/{mask}", strict=False)
        if net.prefixlen < 32 and peer in net and not ipaddress.IPv4Address(address).is_loopback:
            return address
    return None


def local_ipv4() -> list[tuple[str, str]]:
    """(address, netmask) for each interface that has an IPv4 address. Linux only (the worker's containers)."""
    if not sys.platform.startswith("linux"):
        return []
    import fcntl

    out = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        for _index, name in socket.if_nameindex():
            packed = struct.pack("256s", name[:15].encode())
            try:
                addr = socket.inet_ntoa(fcntl.ioctl(s.fileno(), SIOCGIFADDR, packed)[20:24])
                mask = socket.inet_ntoa(fcntl.ioctl(s.fileno(), SIOCGIFNETMASK, packed)[20:24])
            except OSError:
                continue  # an interface with no IPv4 address
            out.append((addr, mask))
    return out


def api_hosts(peer: str, wait_s: float = 60.0) -> list[str]:
    """The addresses to listen on: 0.0.0.0 without a peer; else 127.0.0.1 and the default-network address."""
    if not peer:
        return ["0.0.0.0"]  # noqa: S104 - host-side runs and tests only; compose always sets a peer
    deadline = time.monotonic() + wait_s
    while True:
        try:
            peer_ip = socket.gethostbyname(peer)
            break
        except OSError:
            if time.monotonic() > deadline:
                raise BindError("peer_unresolvable") from None
            time.sleep(1)
    address = pick_address(peer_ip, local_ipv4())
    if address is None:
        raise BindError("no_interface_on_peer_network")
    return ["127.0.0.1", address]
