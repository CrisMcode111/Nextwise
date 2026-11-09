"""Opt-in project transports. No credential reads or network during construction.

Reuse the bounded Tavily/page and Meterless transports. Credentials are resolved
only after the workflow journals an explicitly approved attempt. Never return
provider diagnostics, response envelopes, or credentials to persistence/UI.
"""
import ipaddress
import sys
from urllib.parse import urlsplit

import analyze_sources as analyzer
import runtime_config as config
import semantic_discovery as semantic
import project_assessment_output as output
import tavily_discovery as tavily


def search(query):
    key = config.secret('TAVILY_API_KEY', required=True)
    return tavily.search(query, key)


def assess(request):
    # Prepare the fail-closed generation contract before resolving credentials.
    messages = output.messages(request)
    response_schema = output.contract(request)
    settings = config.settings()
    parsed = urlsplit(settings.meterless_url)
    # Bearer tokens must travel over TLS or the loopback end of a private tunnel.
    try:
        loopback = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        loopback = parsed.hostname == 'localhost'
    if parsed.scheme != 'https' and not loopback:
        raise config.ConfigError('Project Meterless requires HTTPS or a loopback private tunnel.')
    token = config.secret('NEXTWISE_METERLESS_TOKEN', required=True)
    budget = {'max_price_usd': 0} if config.boolean('NEXTWISE_PROJECT_FREE_ONLY') else {}
    result = analyzer.request_claims(token, messages,
        max_tokens=4096, max_response_bytes=semantic.MAX_RESPONSE_BYTES,
        response_schema=response_schema,
        endpoint=settings.completions_url, model=settings.model, **budget)
    print('Project Meterless HTTP status: ' + str(result.get('http_status')) + '; one client dispatch.', file=sys.stderr, flush=True)
    # Accept one complete text answer only. No retries, schema fallback or tools.
    try:
        if result.get('ok') is not True or result.get('http_status') != 200:
            raise ValueError()
        choices = result['data']['choices']
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError()
        choice = choices[0]
        message = choice['message']
        content = message['content']
        if (choice.get('finish_reason') != 'stop' or message.get('role') != 'assistant'
                or message.get('tool_calls') or message.get('function_call')
                or message.get('refusal') or not isinstance(content, str)
                or not content.strip() or len(content.encode('utf-8')) > semantic.MAX_RESPONSE_BYTES
                or token in content):
            raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError('Meterless did not return a complete assessment; no result accepted.') from None
    return output.materialize(content, request)


def configured_services():
    if not config.boolean('NEXTWISE_PROJECT_PROVIDERS_ENABLED'):
        return {}
    search_enabled = config.boolean('NEXTWISE_PROJECT_SEARCH_ENABLED', True)
    return {'searcher': search if search_enabled else None,
            'fetcher': tavily.public_page if search_enabled else None, 'assessor': assess,
            'external_limits': {
                'discover': config.integer('NEXTWISE_PROJECT_SEARCH_LIMIT', 2, maximum=100),
                'assess': config.integer('NEXTWISE_PROJECT_ASSESSMENT_LIMIT', 4, maximum=100)}}
