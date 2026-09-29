"""Read-only catalog reconciliation. No HTTP or production registry mutation."""
from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json
import re
from openpyxl import load_workbook
from product_tool.identity import ProductIdentity, VariantAttributes

VERSION = '7.1.0'
CONFIG_PATH = Path(__file__).parents[1] / 'config/identity_reconciliation.v1.json'

def rules():
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))

def normalized(value):
    return ' '.join(str(value).upper().split())

@dataclass(frozen=True)
class IdentityCandidate:
    raw_value: str
    normalized_value: str
    source_field: str
    role: str
    confidence: float
    extraction_rule: str
    significant_punctuation: str
    review_status: str = 'accepted'
    def to_dict(self):
        return asdict(self)

def candidate(value, field, role, confidence, rule, review='accepted'):
    return IdentityCandidate(value, normalized(value.replace('_', ' ') if role == 'marketing_model' else value), field, role, confidence, rule, ''.join(c for c in value if c in '/-._'), review).to_dict()

def load_rows(path, skus):
    """Preserve all cells, duplicates and alternative titles; never select a winner."""
    book = load_workbook(path, read_only=True, data_only=True)
    result = {sku: [] for sku in skus}
    try:
        sheet = book['\u0422\u043e\u0432\u0430\u0440\u044b']
        iterator = sheet.iter_rows(values_only=True)
        headers = next(iterator)
        for number, values in enumerate(iterator, 2):
            if len(values) < 5 or values[2] not in result:
                continue
            raw = dict(zip(headers, values))
            alternate = next((v for k, v in raw.items() if str(k).casefold() in {'alternate_code', 'alternate code', '\u0430\u043b\u044c\u0442\u0435\u0440\u043d\u0430\u0442\u0438\u0432\u043d\u044b\u0439 \u043a\u043e\u0434'}), None)
            result[values[2]].append({'row_reference': f'{sheet.title}!A{number}:H{number}', 'row_number': number, 'original_row': raw, 'brand_raw': values[0], 'category_raw': values[1], 'seller_sku_raw': values[2], 'wb_sku_raw': values[3], 'title_raw': values[4], 'alternate_titles_raw': values[5], 'alternate_code_raw': alternate})
    finally:
        book.close()
    return result

def variants(text, brand_rule, config):
    result = {}
    patterns = dict(config['variants'])
    if re.fullmatch(brand_rule.get('model', r'(?!)'), text, re.I):
        patterns.update({k: brand_rule[k] for k in ('region', 'service_index') if k in brand_rule})
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        if match:
            result[key] = match.group(1).upper().replace(',', '.')
    return result

def reconcile(rows, config=None):
    config = config or rules()
    if not rows:
        return {'version': VERSION, 'rows': [], 'review_status': 'missing_catalog_row', 'candidates': [], 'queries': [], 'high_confidence_candidates': [], 'identity': None}
    titles = list(dict.fromkeys(str(x) for row in rows for x in (row['title_raw'], row.get('alternate_titles_raw')) if x))
    ambiguous = len(rows) != 1 or len(titles) != 1
    # A representative object is computational only; ambiguous records never finalize or run HTTP.
    row = rows[0]
    rule = config['brands'].get(row['brand_raw'].casefold(), {})
    values = []
    for title in titles:
        field = 'title_raw' if title == row['title_raw'] else 'alternate_titles_raw'
        for key, role in [('model', 'manufacturer_model'), ('marketing', 'marketing_model')]:
            for match in re.finditer(rule.get(key, r'(?!)'), title, re.I):
                raw = match.group()
                actual_role = 'possible_internal_code' if key == 'model' and rule.get('internal') else 'regional_model' if key == 'model' and rule.get('region') and re.search(rule['region'], raw) else role
                values.append(candidate(raw, field, actual_role, .65 if actual_role == 'possible_internal_code' else .98, f'brand.{row["brand_raw"].casefold()}.{key}' + ('.parentheses' if title[:match.start()].rstrip().endswith('(') and title[match.end():].lstrip().startswith(')') else ''), 'review' if ambiguous else 'accepted'))
    for source, role in [('seller_sku_raw', 'seller_sku'), ('alternate_code_raw', 'alternate_code')]:
        if row.get(source):
            values.append(candidate(row[source], source, role, .7, 'catalog_field', 'review' if ambiguous else 'accepted'))
    var = variants(row['title_raw'], rule, config)
    # Code suffixes are anchored to the code, not the surrounding title.
    for value in values:
        if value['role'] in {'manufacturer_model', 'regional_model'}:
            var.update(variants(value['raw_value'], rule, config))
    vc = [dict(candidate(str(v), 'title_raw', 'variant', .95, 'variant.' + k), variant_field=k) for k, v in var.items()]
    models = tuple(dict.fromkeys(v['raw_value'] for v in values if v['role'] in {'manufacturer_model', 'regional_model'}))
    marketing = tuple(dict.fromkeys(v['normalized_value'] for v in values if v['role'] == 'marketing_model'))
    identity = ProductIdentity(row['brand_raw'], row['brand_raw'].casefold(), row['category_raw'], 'generic', row['seller_sku_raw'], str(row['wb_sku_raw'] or ''), row['title_raw'], models, VariantAttributes(var), marketing_models=marketing, identity_semantics_version=VERSION, model_qualifiers=tuple(config.get('model_qualifiers', ())))
    planned = []
    priorities = {'manufacturer_model': 0, 'regional_model': 0, 'seller_sku': 1, 'marketing_model': 2, 'alternate_code': 2}
    for value in sorted(values, key=lambda v: (priorities.get(v['role'], 9), not v['extraction_rule'].endswith('.parentheses'))):
        role, raw = value['role'], value['raw_value']
        if role not in priorities:
            continue
        if role in {'seller_sku', 'alternate_code'} and not re.fullmatch(rule.get('model', r'(?!)'), raw, re.I):
            continue
        if value['normalized_value'] in {q['query'] for q in planned}:
            continue
        if len(planned) < 3:
            planned.append(dict(value, query=value['normalized_value'], normalization='uppercase_whitespace_only; marketing_underscore_as_space; punctuation_retained', reason='priority_' + str(priorities[role])))
    return {'version': VERSION, 'rows': rows, 'title_raw': row['title_raw'] if not ambiguous else None, 'titles_raw': titles, 'seller_sku_raw': row['seller_sku_raw'], 'alternate_code_raw': row.get('alternate_code_raw'), 'brand_raw': row['brand_raw'], 'category_raw': row['category_raw'], 'review_status': 'ambiguous_catalog_identity' if ambiguous else 'reconciled', 'candidates': values, 'variant_candidates': vc, 'queries': planned, 'high_confidence_candidates': sorted({v['normalized_value'] for v in values if v['confidence'] >= .9 and v['role'] in {'manufacturer_model', 'regional_model', 'marketing_model'}}), 'identity': identity.to_dict()}

def as_identity(record):
    data = dict(record['identity'])
    data['variant_attributes'] = VariantAttributes(data['variant_attributes'])
    for key in ('model_candidates', 'marketing_models', 'model_qualifiers'):
        data[key] = tuple(data[key])
    return ProductIdentity(**data)

def scope_key(record, domains, workbook_hash):
    return hashlib.sha256(json.dumps({'version': VERSION, 'record': record, 'domains': domains, 'workbook_hash': workbook_hash, 'rules': rules(), 'parser_version': VERSION, 'ranking_version': VERSION, 'implementation_sha256': {name: hashlib.sha256((Path(__file__).parents[1] / name).read_bytes()).hexdigest() for name in ('identity.py', 'census/catalog_identity.py', 'census/structured_identity_v71.py', 'census/runner_v71.py')}}, sort_keys=True).encode()).hexdigest()
