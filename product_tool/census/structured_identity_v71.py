"""Structured Product-only extraction for versioned catalog identities."""
import re
from bs4 import BeautifulSoup
from product_tool.identity import PageIdentity, IdentityVerifier, VariantAttributes
from .catalog_identity import rules, variants, normalized
from .discovery import json_ld_products


def structured_products(html):
    products = list(json_ld_products(html))
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup.select('[itemscope][itemtype]'):
        if not any(t.rstrip('/').endswith('/Product') for t in str(node.get('itemtype', '')).split()):
            continue
        fields = {}
        for child in node.select('[itemprop]'):
            if child.find_parent(attrs={'itemscope': True}) is not node:
                continue
            fields[child.get('itemprop')] = child.get('content') or child.get('value') or child.get_text(' ', strip=True)
        products.append(fields)
    return products


def verify_page(html, expected, domain):
    config = rules()
    rule = config['brands'].get(expected.brand_raw.casefold(), {})
    results = []
    for product in structured_products(html):
        def scalar(key):
            value = product.get(key, '')
            if isinstance(value, dict):
                value = value.get('name', '')
            return str(value) if isinstance(value, (str, int, float)) else ''
        name = scalar('name')
        category = scalar('category') + ' ' + name
        category_keys = config.get('catalog_categories', {})
        group = category_keys.get(expected.category_raw, '')
        compatible = any(re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', category, re.I) for word in config['categories'].get(group, []))
        var = variants(name, rule, config)
        named_codes = [m.group() for m in re.finditer(rule.get('model', r'(?!)'), name, re.I)]
        for code in named_codes:
            var.update(variants(code, rule, config))
        named_marketing = {normalized(m.group().replace('_', ' ')) for m in re.finditer(rule.get('marketing', r'(?!)'), name, re.I)}
        wanted_marketing = {normalized(x) for x in expected.marketing_models}
        if named_marketing & wanted_marketing and named_marketing - wanted_marketing:
            results.append({'level': 'conflict', 'reason': 'multiple_marketing_models_in_structured_name', 'evidence': [], 'structured_product_name': name})
            continue

        for field, keys in {'color': ['color'], 'screen_size': ['size'], 'ram': ['ram', 'memory'], 'storage': ['storage'], 'region': ['region'], 'service_index': ['serviceIndex'], 'hardware_revision': ['revision', 'hardwareRevision'], 'configuration': ['configuration']}.items():
            for key in keys:
                if scalar(key):
                    var[field] = scalar(key)
        for key in ('mpn', 'model'):
            var.update(variants(scalar(key), rule, config))
        observed = PageIdentity(seller_sku=scalar('sku'), manufacturer_sku=scalar('mpn'), model_code=scalar('model'), family=scalar('productGroupID'), structured_product_name=name, structured_brand=scalar('brand'), category_compatible=compatible, source_brand_verified=domain.official_status == 'official_verified' and domain.brand.casefold() == expected.brand_raw.casefold(), variant_attributes=VariantAttributes(var))
        result = IdentityVerifier().verify(expected, observed, source=domain.domain_id, extraction_method='structured_product').to_dict()
        result['structured_product_name'] = name
        results.append(result)
    if not results:
        return {'level': 'insufficient', 'reason': 'no_structured_Product_identity', 'evidence': []}
    # Multiple distinct Products are a listing, not a verified product page.
    if len(results) > 1:
        unique = {(x.get('structured_product_name'), x['level']) for x in results}
        if len(unique) > 1:
            return {'level': 'insufficient', 'reason': 'multiple_structured_products_require_review', 'evidence': [], 'product_checks': results}
    return results[0]
