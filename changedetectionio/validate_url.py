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


def is_private_hostname(hostname):
    """Return True if hostname resolves to an IANA-restricted (private/reserved/non-global) IP address.

    Unresolvable hostnames return False (allow them) — DNS may be temporarily unavailable
    or the domain not yet live. The actual DNS rebinding attack is mitigated by fetch-time
    re-validation in requests.py, not by blocking unresolvable domains at add-time.
    Never cached — callers that need fresh DNS resolution (e.g. at fetch time) can call
    this directly without going through the lru_cached is_safe_valid_url().

    A hostname is refused if ANY of its A/AAAA records is off-limits: a name that answers
    with one public and one CGNAT address is still a route to the CGNAT address.
    """
    try:
        for info in socket.getaddrinfo(hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            blocked, why = is_special_purpose_ip(ip)
            if blocked:
                logger.warning(f"Hostname '{hostname}' resolves to {ip} which is {why} — refused.")
                return True
    except socket.gaierror as e:
        logger.warning(f"{hostname} error checking {str(e)}")
        return False
    except ValueError as e:
        # getaddrinfo handed back something ip_address() won't parse - fail closed.
        logger.warning(f"Hostname '{hostname}' produced an unparseable address ({e}) — refused.")
        return True
    logger.info(f"Hostname '{hostname}' is NOT private/IANA restricted.")
    return False


def extract_url_hostnames(url):
    """Return every hostname this URL could resolve to under different URL parsers.

    Why: urllib's urlparse() and urllib3's parse_url() disagree on URLs containing
    a backslash (e.g. http://INTERNAL:8888\\@PUBLIC/ — urlparse extracts PUBLIC, but
    urllib3/requests will actually connect to INTERNAL). Any SSRF check that trusts
    only one parser can be bypassed by the other. Callers should reject the fetch
    if ANY hostname returned here is private/reserved.

    See GHSA-rph4-96w6-q594.
    """
    hostnames = set()
    try:
        h = urlparse(url).hostname
        if h:
            hostnames.add(h)
    except Exception:
        pass
    try:
        from urllib3.util.url import parse_url as _u3_parse_url
        u3 = _u3_parse_url(url)
        if u3.host:
            # urllib3 keeps IPv6 brackets in `.host`; strip them so socket.getaddrinfo() accepts the literal.
            hostnames.add(u3.host.strip('[]'))
    except Exception:
        pass
    return hostnames


