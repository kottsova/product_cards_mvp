"""Declarative, first-party GET search routes; no script execution."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from typing import Any, Mapping
from urllib.parse import unquote, parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

SECRET = re.compile(r'csrf|xsrf|session|token|auth|password|cookie|nonce|credential|api.?key|(?:^|_)sid$', re.I)
PRIVATE_PARAMETERS = {'email', 'username', 'user', 'userid', 'user_id', 'customer', 'customerid', 'phone', 'address'}

def private_parameter(key):
    return bool(SECRET.search(key)) or key.lower() in PRIVATE_PARAMETERS

FLOW = re.compile(r'(?:^|[/_.-])(?:login|signin|signout|logout|account|cart|checkout|register|delete|remove)(?:[/_.-]|$)', re.I)
STATIC_PARAMETERS = {'lang', 'language', 'locale', 'country', 'type', 'category', 'scope', 'view', 'section', 'site', 'sort', 'options[prefix]', 'page', 'limit', 'count', 'filter', 'searchtype'}
QUERY_NAMES = {'q', 'query', 'search', 'searchterm', 'searchquery', 'keyword', 'keywords', 'text', 'term', 's', 'searchword'}


def now():
    return datetime.now(timezone.utc).isoformat()


def safe_url(url: str, allowed_hosts: tuple[str, ...]) -> bool:
    from .sitemap_strategy import _host_allowed
    try:
        p = urlsplit(url)
        return p.scheme in {'http', 'https'} and not p.username and not p.password and p.port in {None, 80, 443} and _host_allowed(p.hostname or '', allowed_hosts) and not SECRET.search(unquote(p.path)) and not any(private_parameter(k) for k, _ in parse_qsl(p.query))
    except ValueError:
        return False


def redact_url(url: str) -> str:
    try:
        p = urlsplit(url)
        if SECRET.search(unquote(p.path)):
            return urlunsplit((p.scheme, p.hostname or '', '/[redacted]', '', ''))
        return urlunsplit((p.scheme, p.hostname or '', p.path, urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not private_parameter(k)]), ''))
    except ValueError:
        return '[invalid URL]'


@dataclass(frozen=True)
class SearchRoute:
    action_url: str
    method: str
    query_parameter: str
    constant_parameters: tuple[tuple[str, str], ...]
    source: str
    originating_page: str
    allowed_host: str
    confidence: float
    rejection_reason: str = ''
    timestamp: str = ''

    @property
    def executable(self):
        return self.method == 'GET' and bool(self.query_parameter) and not self.rejection_reason

    def to_dict(self):
        value = asdict(self)
        value['constant_parameters'] = [list(x) for x in self.constant_parameters]
        value['disposition'] = 'safe_get' if self.executable else 'manual_or_future_strategy'
        # Compatibility for historical census evidence consumers.
        value['action'] = self.action_url
        value['type'] = 'search_form' if self.source == 'html_search_form' else 'search_path'
        return value

    def __getitem__(self, key):
        return self.to_dict()[key]

    @classmethod
    def from_dict(cls, value):
        return cls(**{k: (tuple(tuple(x) for x in v) if k == 'constant_parameters' else v) for k, v in value.items() if k in cls.__dataclass_fields__})

    def query_url(self, query):
        if not self.executable:
            raise ValueError('Unsafe search route')
        p = urlsplit(self.action_url)
        return urlunsplit((p.scheme, p.netloc, p.path, urlencode([*self.constant_parameters, (self.query_parameter, query)]), ''))


def make_route(action: str, *, base_url: str, allowed_hosts: tuple[str, ...], method='GET', query_parameter='', constants=(), source='html_search_form', rejection=''):
    action = urljoin(base_url, action)
    try:
        p = urlsplit(action)
    except ValueError:
        return SearchRoute('[invalid URL]', method.upper(), '', (), source, redact_url(base_url), '', 0.0, 'foreign_or_unsafe_action', now())
    params = [*parse_qsl(p.query, keep_blank_values=True), *constants]
    method = method.upper()
    if not safe_url(action, allowed_hosts):
        rejection = rejection or 'foreign_or_unsafe_action'
    if FLOW.search(unquote(p.path)):
        rejection = rejection or 'non_search_account_or_transaction_flow'
    if private_parameter(query_parameter) or any(private_parameter(k) for k, _ in params):
        rejection = 'csrf_or_session_requirement'
    if method != 'GET':
        rejection = rejection or 'non_get_method'
    if source != 'configured_endpoint' and re.search(r'/(?:api|graphql)(?:/|\.|$)', p.path, re.I):
        rejection = rejection or 'unconfigured_api_endpoint'
    if not query_parameter:
        rejection = rejection or 'query_parameter_not_declared'
    if source != 'configured_endpoint' and any(k != query_parameter and k.lower() not in STATIC_PARAMETERS for k, v in params):
        rejection = rejection or 'unreviewed_constant_parameter'
    clean = tuple(dict.fromkeys((k, v) for k, v in params if k != query_parameter and not private_parameter(k) and (source == 'configured_endpoint' or k.lower() in STATIC_PARAMETERS)))
    return SearchRoute(redact_url(urlunsplit((p.scheme, p.netloc, p.path, '', ''))), method, '' if private_parameter(query_parameter) else query_parameter, clean, source, redact_url(base_url), p.hostname or '', 1.0 if source == 'configured_endpoint' else 0.8, rejection, now())


class SearchHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.links = []
        self.form = None
        self.anchor = None
        self.scripts = []
        self.script = None
        self.ignored = 0
        self.nodes = 0
        self.card_stack = []

    def handle_starttag(self, tag, attrs):
        self.nodes += 1
        if self.nodes > 15000:
            return
        a = dict(attrs)
        classes = set((a.get('class') or '').lower().split())
        marker = next((name for name in ('data-product-id', 'data-product-handle', 'data-sku') if a.get(name)), '')
        if not marker and any(x.rstrip('/').lower() in {'https://schema.org/product', 'http://schema.org/product'} for x in (a.get('itemtype') or '').split()):
            marker = 'schema_org_product'
        if not marker:
            marker = next((x for x in ('product-card', 'product-item', 'product-result') if x in classes), '')
        boundary = tag in {'nav', 'header', 'footer', 'aside'} or bool(classes & {'search-results', 'search-result-container', 'results', 'navigation', 'layout'})
        if tag not in {'input', 'img', 'link', 'meta', 'br', 'hr', 'source'}:
            self.card_stack.append((tag, marker, boundary, self.nodes))
        if tag == 'script':
            self.script = {'attrs': a, 'text': ''}
            return
        if self.script is not None:
            return
        if tag == 'form':
            self.form = {'attrs': a, 'inputs': []}
            self.forms.append(self.form)
        elif tag in {'input', 'button', 'select', 'textarea'} and self.form is not None:
            self.form['inputs'].append(a)
        elif tag == 'a' and len(self.links) < 1000:
            local = None
            for frame in reversed(self.card_stack):
                if frame[2]:
                    break
                if frame[1]:
                    local = {'marker': frame[1], 'node': frame[3]}
                    break
            self.anchor = {'attrs': a, 'text': '', 'structured': bool(local), 'card_evidence': local}
            self.links.append(self.anchor)
        elif tag == 'link' and 'canonical' in (a.get('rel') or '').split() and len(self.links) < 1000:
            self.links.append({'attrs': a, 'text': '', 'canonical': True})

    def handle_endtag(self, tag):
        for index in range(len(self.card_stack) - 1, -1, -1):
            if self.card_stack[index][0] == tag:
                del self.card_stack[index:]
                break
        if tag == 'script':
            if self.script is not None and len(self.scripts) < 50:
                self.scripts.append(self.script)
            self.script = None
        elif self.script is None:
            if tag == 'form':
                self.form = None
            elif tag == 'a':
                self.anchor = None

    def handle_data(self, data):
        if self.script is not None:
            self.script['text'] = (self.script['text'] + data)[:200000]
        elif self.anchor is not None:
            self.anchor['text'] = (self.anchor['text'] + data)[:500]


def detect_routes(html: str, base_url: str, *, allowed_hosts=None, configured_endpoints=()):
    hosts = tuple(allowed_hosts or (urlsplit(base_url).hostname or '',))
    parser = SearchHTMLParser()
    parser.feed((html or '')[:1000000])
    routes = []
    for config in configured_endpoints[:20]:
        routes.append(make_route(config.get('action_url', config.get('url', '')), base_url=base_url, allowed_hosts=hosts, method=config.get('method', 'GET'), query_parameter=config.get('query_parameter', ''), constants=tuple(config.get('constant_parameters', ())), source='configured_endpoint'))
    for form in parser.forms[:50]:
        a, inputs = form['attrs'], form['inputs']
        fields = [i for i in inputs if i.get('name') and ('disabled' not in i) and ((i.get('type') or '').lower() == 'search' or (i.get('name') or '').lower() in QUERY_NAMES)]
        search_hint = fields or 'search' in str(a).lower()
        if not search_hint:
            continue
        rejection = ''
        if any((i.get('type') or '').lower() in {'password', 'file'} for i in inputs):
            rejection = 'password_or_file_input'
        if any(SECRET.search(i.get('name') or '') for i in inputs):
            rejection = 'csrf_or_session_requirement'
        if any(k in i for i in inputs for k in ('formaction', 'formmethod')):
            rejection = rejection or 'submission_override'
        if any(k.lower().startswith('on') for k in a) or any(any(k.lower().startswith('on') for k in i) for i in inputs):
            rejection = rejection or 'javascript_handler'
        if any(FLOW.search(str(v or '')) for v in a.values()):
            rejection = rejection or 'non_search_account_or_transaction_flow'
        if len(fields) != 1:
            rejection = rejection or 'ambiguous_query_parameter'
        if any(i.get('name') and i not in fields and (i.get('type') or '').lower() == 'hidden' and i['name'].lower() not in STATIC_PARAMETERS for i in inputs):
            rejection = rejection or 'unreviewed_hidden_parameter'
        constants = [(i['name'], i.get('value') or '') for i in inputs if i.get('name') and i not in fields and (i.get('type') or '').lower() == 'hidden' and 'disabled' not in i and i['name'].lower() in STATIC_PARAMETERS]
        routes.append(make_route(a.get('action') or base_url, base_url=base_url, allowed_hosts=hosts, method=a.get('method') or 'GET', query_parameter=fields[0]['name'] if len(fields) == 1 else '', constants=constants, rejection=rejection))
    for link in parser.links:
        href = link['attrs'].get('href') or ''
        if not href:
            continue
        try:
            parsed = urlsplit(urljoin(base_url, href))
        except ValueError:
            continue
        if not re.search(r'(?:search|/s$)', parsed.path, re.I):
            continue
        query_fields = [k for k, _ in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() in QUERY_NAMES]
        rejection = 'javascript_handler' if any(k.lower().startswith('on') for k in link['attrs']) else ''
        routes.append(make_route(href, base_url=base_url, allowed_hosts=hosts, query_parameter=query_fields[0] if len(set(query_fields)) == 1 else '', source='first_party_search_link', rejection=rejection))
    unique = {}
    for route in routes:
        key = (route.action_url, route.method, route.query_parameter, route.constant_parameters, route.rejection_reason)
        unique.setdefault(key, route)
    return tuple(unique.values())
