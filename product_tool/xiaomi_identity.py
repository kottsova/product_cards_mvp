"""Xiaomi/Redmi/POCO identity boundaries; numeric model codes are not retail SKUs."""
import re
BRANDS = frozenset({'xiaomi', 'redmi', 'poco'})

def key(text):
    return re.sub(r'[^a-z0-9]', '', text.casefold().replace('+', 'plus'))

def model_name(name):
    return name.split('[', 1)[0].strip()

def requested_configuration(name):
    match = re.search(r'\[([^\]]+)\]', name)
    return dict(x.strip().split('=', 1) for x in match[1].split(';') if '=' in x) if match else {}

def lineage(name):
    return next((x for x in ('POCO', 'Redmi', 'Xiaomi') if name.casefold().startswith(x.casefold())), '')

def model_matches(wanted, title):
    title = re.sub(r'^All Specs, Features of\s+', '', title, flags=re.I)
    label = re.split(r'\s+(?:Specs|Specifications)\b|\s+[|–]\s+|\s+-\s+Xiaomi', title, maxsplit=1, flags=re.I)[0].strip()
    return bool(lineage(wanted) and lineage(wanted) == lineage(label) and key(wanted) == key(label))

def region(url):
    from urllib.parse import urlsplit
    parts = urlsplit(url).path.strip('/').split('/')
    return parts[0].casefold() if parts else ''

def region_matches(requested, source):
    # EEA is not interchangeable with Global or one unspecified EU market.
    return requested.casefold() == source.casefold()

def fact_scope(label):
    text = label.casefold()
    if text in {'display colours', 'display colors', 'color gamut', 'color depth'}:
        return 'model'
    if re.search(r'storage|\bram\b|memory|colour|color|package|contents|bundle|edition|sku|part number|комплект|цвет|памят', text):
        return 'configuration'
    if re.search(r'\bnfc\b|esim|network|connectivity|band|operating system|software|charger|wireless networks|прошив|диапазон|сим', text):
        return 'region'
    return 'model'
