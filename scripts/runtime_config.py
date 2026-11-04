"""Shared runtime configuration. No network, persistence, or inference at import."""
from dataclasses import dataclass
import os
from pathlib import Path
import re
import socket
from urllib.parse import urlsplit

CODE_ROOT = Path(__file__).resolve().parents[1]


class ConfigError(ValueError):
    """Diagnostics name the setting, never its potentially secret value."""


def secret(name, *, required=False):
    value = os.environ.get(name, '').strip()
    filename = os.environ.get(name + '_FILE', '').strip()
    if value and filename:
        raise ConfigError(f'Set only {name} or {name}_FILE, not both.')
    if filename:
        try:
            with Path(filename).open('rb') as stream:
                raw = stream.read(16_385)
            if len(raw) > 16_384:
                raise ValueError()
            value = raw.decode('utf-8').strip()
        except (OSError, ValueError):
            raise ConfigError(f'{name}_FILE must be a readable UTF-8 secret of at most 16 KB.') from None
    if any(c in value for c in ('\r', '\n', '\x00')):
        raise ConfigError(f'{name} must contain one nonempty line.')
    if required and not value:
        raise ConfigError(f'{name} or {name}_FILE is required for unattended startup.')
    return value


def path(name, default):
    value = Path(os.environ.get(name, '').strip() or default).expanduser()
    if not value.is_absolute():
        value = CODE_ROOT / value
    return value.resolve()


def boolean(name, default=False):
    value = os.environ.get(name, 'true' if default else 'false').lower()
    if value not in ('1', '0', 'true', 'false'):
        raise ConfigError(f'{name} must be true or false.')
    return value in ('1', 'true')


def integer(name, default, minimum=1, maximum=65535):
    try:
        value = int(os.environ.get(name, str(default)))
        if not minimum <= value <= maximum:
            raise ValueError()
        return value
    except ValueError:
        raise ConfigError(f'{name} must be an integer between {minimum} and {maximum}.') from None


def url(name, default):
    value = os.environ.get(name, default).rstrip('/')
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or
                parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError()
        parsed.port
    except ValueError:
        raise ConfigError(f'{name} must be an HTTP(S) URL without credentials, query or fragment.') from None
    return value


@dataclass(frozen=True)
class Settings:
    artifact_root: Path
    memory_root: Path
    snapshot: Path
    host: str
    port: int
    public_origin: str
    zetaris_url: str
    zetaris_org: str
    meterless_url: str
    model: str
    node: str
    dependency_timeout: int
    require_meterless: bool

    @classmethod
    def from_env(cls):
        artifacts = path('NEXTWISE_ARTIFACT_ROOT', CODE_ROOT)
        origin = url('NEXTWISE_PUBLIC_ORIGIN', '') if os.environ.get('NEXTWISE_PUBLIC_ORIGIN') else ''
        if origin and urlsplit(origin).path:
            raise ConfigError('NEXTWISE_PUBLIC_ORIGIN must be an origin without a path.')
        org = os.environ.get('NEXTWISE_ZETARIS_ORG_ID', '1')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', org):
            raise ConfigError('NEXTWISE_ZETARIS_ORG_ID must be a simple organization identifier.')
        model = os.environ.get('NEXTWISE_MODEL', 'meterless/auto').strip()
        if not model or any(c in model for c in ('\r', '\n', '\x00')):
            raise ConfigError('NEXTWISE_MODEL must be a nonempty model identifier.')
        return cls(artifacts,
            path('NEXTWISE_MEMORY_ROOT', artifacts / 'data/memory/hmem'),
            path('NEXTWISE_ZETARIS_SNAPSHOT', artifacts / 'data/zetaris_exports/20261024T151413Z-fdf0c15b-csv-5fa0db458643'),
            os.environ.get('NEXTWISE_HOST', '127.0.0.1'), integer('NEXTWISE_PORT', 8765), origin,
            url('NEXTWISE_ZETARIS_URL', 'http://127.0.0.1:8888'), org,
            url('NEXTWISE_METERLESS_URL', 'http://127.0.0.1:8088'), model,
            os.environ.get('NEXTWISE_NODE', 'node'), integer('NEXTWISE_DEPENDENCY_TIMEOUT', 3, maximum=30),
            boolean('NEXTWISE_REQUIRE_METERLESS'))

    @property
    def completions_url(self):
        return self.meterless_url + '/v1/chat/completions'

    def meterless_probe(self):
        """TCP connectivity only. Never sends HTTP, credentials or a model request."""
        parsed = urlsplit(self.meterless_url)
        with socket.create_connection((parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80)),
                                      timeout=self.dependency_timeout):
            pass


def settings():
    return Settings.from_env()
