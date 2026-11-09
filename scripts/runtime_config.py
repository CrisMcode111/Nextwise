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


def load_native_env(filename):
    """Load an explicit private runtime file without shell evaluation or logging.

    Compose uses host.docker.internal; native Python reaches those same published
    local ports over loopback. Existing process settings take precedence.
    """
    try:
        lines = Path(filename).read_text(encoding='utf-8-sig').splitlines()
    except OSError:
        raise ConfigError('The runtime env file must exist and be readable.') from None
    values = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, separator, value = line.partition('=')
        name, value = name.strip(), value.strip()
        if (not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*', name)
                or not (name.startswith('NEXTWISE_') or name in ('TAVILY_API_KEY', 'TAVILY_API_KEY_FILE'))):
            raise ConfigError('The runtime env file must contain Nextwise/Tavily assignments only.')
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ConfigError('The runtime env file contains an unmatched quote.')
            value = value[1:-1]
        values[name] = value
    for source, target in (
        ('NEXTWISE_ZETARIS_SECRET_FILE', 'NEXTWISE_ZETARIS_API_KEY_FILE'),
        ('NEXTWISE_TAVILY_SECRET_FILE', 'TAVILY_API_KEY_FILE'),
        ('NEXTWISE_METERLESS_SECRET_FILE', 'NEXTWISE_METERLESS_TOKEN_FILE'),
    ):
        if source in values:
            values.setdefault(target, values[source])
    for name, value in values.items():
        os.environ.setdefault(name, value)
    for name in ('NEXTWISE_ZETARIS_URL', 'NEXTWISE_METERLESS_URL'):
        value = os.environ.get(name)
        if value:
            try:
                parsed = urlsplit(value)
                if parsed.hostname == 'host.docker.internal' and not parsed.username and not parsed.password:
                    os.environ[name] = parsed._replace(netloc='127.0.0.1' + (':' + str(parsed.port) if parsed.port else '')).geturl()
            except ValueError:
                raise ConfigError(f'{name} must be a valid HTTP(S) service URL.') from None


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
        # Runtime cards may give a service root or an OpenAI-compatible /v1 base.
        base = self.meterless_url
        return base + ('/chat/completions' if base.endswith('/v1') else '/v1/chat/completions')

    def meterless_probe(self):
        """TCP connectivity only. Never sends HTTP, credentials or a model request."""
        parsed = urlsplit(self.meterless_url)
        with socket.create_connection((parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80)),
                                      timeout=self.dependency_timeout):
            pass


def settings():
    return Settings.from_env()
