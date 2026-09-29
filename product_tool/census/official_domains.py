"""Stage 7 research registry; never imported by the production source registry."""
from dataclasses import dataclass,asdict
import json
from pathlib import Path
from urllib.parse import urlsplit
from .catalog import category_group
from .search_routes import safe_url

@dataclass(frozen=True)
class OfficialDomain:
    domain_id:str
    source_family:str
    brand:str
    url:str
    market:str
    locale:str
    market_scope:str
    division:str
    category_scope:tuple[str,...]
    ownership_evidence:tuple[dict,...]
    page_hosts:tuple[str,...]
    support_hosts:tuple[str,...]
    document_hosts:tuple[str,...]
    capabilities:dict
    priority:int
    route_order:int=1
    official_status:str='official_verified'
    enabled:bool=False
    research_enabled:bool=True
    access_status:str='not_checked'
    protection_status:str='not_checked'
    discovery_status:str='not_checked'
    last_checked_at:str=''

    def __post_init__(self):
        if not safe_url(self.url,self.page_hosts):raise ValueError('Unsafe domain URL')
        if self.official_status=='official_verified' and not self.ownership_evidence:raise ValueError('Ownership evidence required')
        if self.route_order not in {0,1,2} or self.market_scope not in {'global','regional'}:raise ValueError('Invalid domain routing')
    def supports(self,expected):
        if expected.brand_raw.casefold()!=self.brand.casefold():return False
        group=category_group(expected.category_raw)
        return '*' in self.category_scope or group in self.category_scope
    def to_dict(self):return asdict(self)


def load_domains(path=None):
    path=Path(path) if path else Path(__file__).resolve().parents[1]/'config/official_domains.v1.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    if data['schema_version']!=1:raise ValueError('Unknown official registry version')
    records=[]
    for raw in data['domains']:
        raw=dict(raw)
        for k in ['category_scope','ownership_evidence','page_hosts','support_hosts','document_hosts']:raw[k]=tuple(raw[k])
        records.append(OfficialDomain(**raw))
    if len({d.domain_id for d in records})!=len(records):raise ValueError('Duplicate official domain')
    return tuple(records)


def routed_domains(domains,expected,source_family,*,research=False):
    return tuple(sorted((d for d in domains if d.source_family==source_family and d.supports(expected) and d.official_status=='official_verified' and (d.enabled or research and d.research_enabled)),key=lambda d:(d.route_order,d.priority,d.domain_id)))
