"""Resolve search input roles without changing supplier cells or claiming identity."""
import re,json


def structured_code(value):
    text=str(value or '').strip()
    parts=re.split(r'\s+\+\s+',text)
    return bool(text) and all(
        len(part)>=3 and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/#()+-]*',part)
        and re.search(r'\d',part) for part in parts)


def resolve_product_input(product):
    """A descriptive primary cell may use an explicit structured fallback.

    This is a query choice only. Every adapter still proves its own source identity.
    Valid primary codes and explicit kits retain their original priority.
    """
    result=dict(product)
    identity=result.get('identity_json') or {}
    if isinstance(identity,str):identity=json.loads(identity)
    parsed=identity.get('input_interpretation')
    if parsed:
        from .input_interpretation import adapter_name
        result.update(model=parsed['model'],supplier_article=parsed['supplier_article'],
                      configuration_hints=parsed['configuration_hints'],input_interpretation=parsed,
                      search_queries=parsed['search_queries'],discovery_name=adapter_name(parsed))
    primary=str(result.get('search_code') or '').strip()
    fallback=str(result.get('alternate_code') or '').strip()
    description=bool(re.search(r'\s',primary) and len(primary.split())>1)
    if description and not structured_code(primary) and structured_code(fallback):
        result['search_code']=fallback
        result['input_search_code']=primary
        result['input_resolution']={'primary_input':primary,'fallback_input':fallback,
            'effective_article':fallback,'name':result.get('name',''),
            'reason':'Primary cell contains descriptive text; explicit structured fallback used for discovery, source identity still unproven',
            'identity_claim':False}
    return result
