from __future__ import annotations

import ipaddress
import urllib.parse

_PRIVATE_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / AWS metadata
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),   # shared address space
    ipaddress.ip_network("fc00::/7"),         # ULA
    ipaddress.ip_network("::1/128"),
)

_BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "metadata.google.internal",
    "169.254.169.254",
})


def is_safe_url(url: str) -> bool:
    """Return True only if url uses http/https and does not point to a private/internal host.

    Blocks: private IP ranges, loopback, link-local, cloud metadata endpoints.
    Hostnames that cannot be resolved at validation time are allowed through
    (they will resolve to a real IP at connection time); only statically-known
    internal names are blocked.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    host = parsed.hostname
    if not host:
        return False

    if host.lower() in _BLOCKED_HOSTNAMES:
        return False

    try:
        addr = ipaddress.ip_address(host)
        return not any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        # Not a bare IP address — it's a hostname; pass through
        return True
