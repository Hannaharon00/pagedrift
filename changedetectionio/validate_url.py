import ipaddress
import socket
from functools import lru_cache
from loguru import logger
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, quote, unquote


def is_special_purpose_ip(ip):
    """Return (blocked: bool, why: str) for a single resolved IP address.

    THE one place that decides "is this address off-limits to the fetcher?". Everything
    that resolves a hostname must funnel through here so a newly-discovered range is
    added once, not once per call site.

    IPv6 addresses that embed an IPv4 address (IPv4-mapped, 6to4, Teredo) are unwrapped
    and re-checked, so e.g. ::ffff:100.64.0.1 cannot smuggle a blocked v4 address past a
    v6-only classification.
    """
    if isinstance(ip, str):
        ip = ipaddress.ip_address(ip)

    if ip.is_private:
        return True, 'private'
    if ip.is_loopback:
        return True, 'loopback'
    if ip.is_link_local:
        return True, 'link-local'
    if ip.is_reserved:
        return True, 'reserved'
    if ip.is_multicast:
        return True, 'multicast'
    if ip.is_unspecified:
        return True, 'unspecified'

    for net in _NON_GLOBAL_EXTRA_NETWORKS:
        if ip.version == net.version and ip in net:
            return True, f'in non-globally-reachable range {net}'

    # Catch-all for ranges this Python release knows are not globally reachable but which
    # none of the flags above expose (100.64.0.0/10 is such a case on CPython 3.12).
    if not ip.is_global:
        return True, 'not globally reachable'

    # An IPv6 address carrying an IPv4 payload is only as safe as that payload.
    for embedded in (getattr(ip, 'ipv4_mapped', None), getattr(ip, 'sixtofour', None), getattr(ip, 'teredo', None)):
        if embedded is None:
            continue
        # .teredo returns a (server, client) tuple; the others return a single address.
        for candidate in (embedded if isinstance(embedded, tuple) else (embedded,)):
            blocked, why = is_special_purpose_ip(candidate)
            if blocked:
                return True, f'embeds IPv4 address {candidate} ({why})'

    return False, ''


