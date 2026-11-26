"""Bounded public HTTPS ingestion; no proxies, redirects or private-address access."""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit

import collector_public as collector

MAX_BYTES = 1_000_000
MAX_TEXT = 12_000
TIMEOUT = 5
DEADLINE = 12


def validate_url(url):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url):
        raise ValueError('Enter a public HTTPS URL.')
    try:
        parsed = urlsplit(url)
        if (parsed.scheme.lower() != 'https' or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.port not in (None, 443) or parsed.fragment):
            raise ValueError()
        host = parsed.hostname.encode('idna').decode('ascii').lower().rstrip('.')
        if not host or '%' in host or host == 'localhost' or host.endswith(('.localhost', '.local')):
            raise ValueError()
        return host, (parsed.path or '/') + ('?' + parsed.query if parsed.query else '')
    except (ValueError, UnicodeError):
        raise ValueError('Enter a public HTTPS URL without credentials or a custom port.') from None


def public_addresses(host, resolver=socket.getaddrinfo):
    try:
        records = resolver(host, 443, type=socket.SOCK_STREAM)
        addresses = list(dict.fromkeys(record[4][0] for record in records))
        if not addresses or any(not ipaddress.ip_address(addr).is_global for addr in addresses):
            raise ValueError()
        return addresses
    except (ValueError, OSError):
        raise ValueError('The URL does not resolve exclusively to public addresses.') from None


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect to the checked address while validating TLS for the original host."""
    def __init__(self, host, address):
        super().__init__(host, 443, timeout=TIMEOUT, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def extract_public_url(url, *, resolver=socket.getaddrinfo, connection=PinnedHTTPSConnection):
    host, path = validate_url(url)
    address = public_addresses(host, resolver)[0]
    conn = connection(host, address)
    start = time.monotonic()
    try:
        conn.request('GET', path, headers={'User-Agent':'NextwisePublicIngestion/1.0',
                     'Accept':'text/html,text/plain', 'Accept-Encoding':'identity'})
        response = conn.getresponse()
        media = response.getheader('Content-Type', '').split(';', 1)[0].strip().lower()
        encoding = response.getheader('Content-Encoding', 'identity').lower()
        size = response.getheader('Content-Length')
        if response.status != 200 or media not in ('text/html','text/plain') or encoding not in ('','identity'):
            raise ValueError('The page is unavailable, redirected or not readable text.')
        if size and (not size.isdecimal() or int(size) > MAX_BYTES):
            raise ValueError('The page is too large.')
        raw = bytearray()
        while True:
            if time.monotonic() - start > DEADLINE:
                raise ValueError('The page took too long to read.')
            chunk = response.read(min(65536, MAX_BYTES + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
            if len(raw) > MAX_BYTES:
                raise ValueError('The page is too large.')
        text = raw.decode('utf-8', errors='replace')
        if media == 'text/html':
            text = collector.extract_page(text).text()
        text = ' '.join(text.split())
        if not text:
            raise ValueError('The page contains no readable text.')
        return {'url':url, 'text':text[:MAX_TEXT], 'truncated':len(text) > MAX_TEXT,
                'provenance':'untrusted_public_page'}
    except (OSError, http.client.HTTPException, ssl.SSLError):
        raise ValueError('The public page could not be fetched securely.') from None
    finally:
        conn.close()
