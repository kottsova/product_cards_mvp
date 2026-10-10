"""Bounded public SSR JSON and two-column specification primitives; never execute JS."""
import json
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .common import RawAttribute


def embedded_objects(html):
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup.find_all('script'):
        text = script.get_text().strip()
        if len(text) > 2_000_000:
            continue
        if script.get('type') == 'application/ld+json':
            candidate = text
        else:
            match = re.fullmatch(r'(?:window\.)?__[A-Z_]+__\s*=\s*(\{.*\})\s*;?', text, re.S)
            if not match:
                continue
            candidate = match[1]
        try:
            yield json.loads(candidate)
        except ValueError:
            continue


def records(value, depth=0):
    if depth > 30:
        return
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from records(child, depth + 1)
    elif isinstance(value, list):
        for child in value[:5000]:
            yield from records(child, depth + 1)


def published_links(html, base):
    soup = BeautifulSoup(html, 'html.parser')
    found = [(urljoin(base, a['href']), a.get_text(' ', strip=True)) for a in soup.select('a[href]')]
    for obj in embedded_objects(html):
        for record in records(obj):
            for key in ('url', 'href', 'link', 'gotoUrl'):
                value = record.get(key)
                if isinstance(value, str) and value.startswith(('http://', 'https://', '//', '/')):
                    found.append((urljoin(base, value), str(record.get('text') or record.get('name') or record.get('content') or '')))
    return list(dict.fromkeys(found))[:10000]


def two_column_specs(html, *, text_selector, row_selector='div'):
    """Preserve raw labels, continuation lines and sections in a declared specs DOM."""
    soup = BeautifulSoup(html, 'html.parser')
    result, seen = [], set()
    leaves = {id(x) for x in soup.select(text_selector)}
    for row in soup.select(row_selector):
        if row.get('platform') == 'mobile' or row.find_parent(attrs={'platform': 'mobile'}):
            continue
        children = row.find_all(recursive=False)
        if len(children) != 2:
            continue
        parent_columns = row.parent.find_all(recursive=False) if row.parent else []
        if len(parent_columns) == 2 and parent_columns[1] is row:
            first = parent_columns[0]
            parent_labels = [first] if id(first) in leaves else first.select(text_selector)
            if len(parent_labels) == 1:
                # A two-line value is a continuation, not a new label/value fact.
                continue
        left, right = children
        labels = [left] if id(left) in leaves else left.select(text_selector)
        # The label column contains exactly one leaf; the value column can continue.
        if len(labels) != 1:
            continue
        name = labels[0].get_text(' ', strip=True).rstrip(':')
        values = [right] if id(right) in leaves else right.select(text_selector)
        value = '\n'.join(x.get_text(' ', strip=True) for x in values)
        if not name or not value or len(name) > 100 or name.startswith('*'):
            continue
        # A section containing further label/value rows is a parent group, not a fact.
        nested_pair = False
        for nested in right.select(row_selector):
            columns = nested.find_all(recursive=False)
            if len(columns) != 2:
                continue
            a, b = columns
            al = [a] if id(a) in leaves else a.select(text_selector)
            bl = [b] if id(b) in leaves else b.select(text_selector)
            if len(al) == 1 and bl:
                nested_pair = True
                break
        if nested_pair or re.match(r'^\d+(?:\.\d+)?\s*(?:mAh|mm|kg|g|W|V|GB|Hz)\b', name, re.I):
            continue
        section = ''
        for sibling in row.previous_siblings:
            if not hasattr(sibling, 'select'):
                continue
            texts = sibling.select(text_selector)
            if len(texts) == 1 and any(c in texts[0].get('class', []) for c in ('f-bold', 'f-medium')):
                section = texts[0].get_text(' ', strip=True)
                break
        for ancestor in row.parents:
            if section:
                break
            columns = ancestor.find_all(recursive=False) if hasattr(ancestor, 'find_all') else []
            if len(columns) == 2:
                a = columns[0]
                texts = [a] if id(a) in leaves else a.select(text_selector)
                if len(texts) == 1:
                    section = texts[0].get_text(' ', strip=True)
                    break
        signature = (name, value, section)
        if signature in seen:
            continue
        seen.add(signature)
        result.append(RawAttribute(name, value, section=section or name))
    return result
